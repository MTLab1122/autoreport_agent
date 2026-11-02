"""Rate limiting, iteration guards, and token budget cost caps to prevent Denial of Wallet."""

import time
from collections import defaultdict
from typing import Dict, List, Optional


class RateLimitExceeded(RuntimeError):
    """Raised when request rate exceeds configured thresholds."""
    pass


class BudgetExceeded(RuntimeError):
    """Raised when token or cost budget is exceeded."""
    pass


class IterationLimitExceeded(RuntimeError):
    """Raised when an agent loop exceeds the hard maximum iterations cap."""
    pass


class RateLimiter:
    """Sliding-window rate limiter per client/action key."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.history: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, key: str, current_time: Optional[float] = None) -> bool:
        now = current_time or time.time()
        window_start = now - self.window_seconds
        
        # Purge timestamps older than the sliding window
        self.history[key] = [t for t in self.history[key] if t > window_start]
        
        if len(self.history[key]) >= self.max_requests:
            return False
        
        self.history[key].append(now)
        return True

    def acquire(self, key: str) -> None:
        if not self.is_allowed(key):
            raise RateLimitExceeded(
                f"Rate limit exceeded for key '{key}': Max {self.max_requests} requests per {self.window_seconds}s."
            )


class CostBudgetTracker:
    """Tracks token consumption and enforces a hard token/cost budget cap per run."""

    def __init__(self, max_tokens_per_run: int = 150_000, max_usd_per_run: float = 1.00):
        self.max_tokens_per_run = max_tokens_per_run
        self.max_usd_per_run = max_usd_per_run
        self.total_prompt_tokens = 0
        self.total_candidates_tokens = 0

    def record_usage(self, prompt_tokens: int, candidates_tokens: int) -> None:
        self.total_prompt_tokens += prompt_tokens
        self.total_candidates_tokens += candidates_tokens
        
        total_tokens = self.total_prompt_tokens + self.total_candidates_tokens
        if total_tokens > self.max_tokens_per_run:
            raise BudgetExceeded(
                f"Denial of Wallet Guard: Run token usage ({total_tokens}) exceeded budget ({self.max_tokens_per_run})."
            )

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_candidates_tokens


class IterationGuard:
    """Enforces strict loop bounds to guarantee termination and prevent infinite agent execution."""

    def __init__(self, max_iterations: int = 5, loop_name: str = "AgentLoop"):
        self.max_iterations = max_iterations
        self.loop_name = loop_name
        self.iteration = 0

    def step(self) -> int:
        self.iteration += 1
        if self.iteration > self.max_iterations:
            raise IterationLimitExceeded(
                f"Loop '{self.loop_name}' exceeded maximum allowed iterations ({self.max_iterations}). Terminating."
            )
        return self.iteration

    def reset(self) -> None:
        self.iteration = 0

