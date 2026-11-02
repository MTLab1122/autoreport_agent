"""Fault-tolerant retry handler with exponential backoff and jitter."""

import functools
import random
import time
from typing import Callable, Any, Tuple, Type, Optional
import requests


class TransientError(Exception):
    """Exception denoting a transient error eligible for retry."""
    pass


def is_transient_http_error(exc: Exception) -> bool:
    """Classify whether an exception is transient (429, 5xx, timeout, connection drop)."""
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code in (429, 500, 502, 503, 504)
    # Generic transient error class
    if isinstance(exc, TransientError):
        return True
    return False


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 15.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[Callable[[str], None]] = None,
):
    """Decorator implementing full-jitter exponential backoff for resilient API interactions."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            while True:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    if attempt > max_retries:
                        if logger:
                            logger(f"[Retry Failure] Function '{func.__name__}' failed after {attempt} attempts: {exc}")
                        raise

                    # Check transient status if requested
                    if not is_transient_http_error(exc) and not isinstance(exc, TransientError):
                        # If it's a non-transient error (e.g. 401 Unauthorized or ValueError), do not retry
                        if isinstance(exc, (ValueError, KeyError, TypeError, PermissionError)):
                            raise

                    # Exponential backoff with full jitter
                    calculated_delay = min(max_delay, initial_delay * (backoff_factor ** (attempt - 1)))
                    jittered_delay = random.uniform(0.5 * calculated_delay, calculated_delay)
                    
                    if logger:
                        logger(
                            f"[Retry Notice] '{func.__name__}' caught {type(exc).__name__} ({exc}). "
                            f"Retrying in {jittered_delay:.2f}s (Attempt {attempt}/{max_retries})..."
                        )
                    time.sleep(jittered_delay)

        return wrapper
    return decorator

