"""Security hardening package for Updates_Agent."""

from .sanitizer import (
    sanitize_untrusted_text,
    wrap_untrusted_context,
    safe_escape_html,
    safe_escape_xml,
    validate_model_output_safety,
)
from .logging_filter import SensitiveDataRedactor, SanitizedLogger
from .sandbox import (
    validate_safe_path,
    sanitize_filename,
    HITLGate,
)
from .webhook_auth import (
    verify_hmac_signature,
    verify_timestamp_replay,
    get_strict_cors_headers,
)
from .rate_limiter import (
    RateLimiter,
    CostBudgetTracker,
    IterationGuard,
)

__all__ = [
    "sanitize_untrusted_text",
    "wrap_untrusted_context",
    "safe_escape_html",
    "safe_escape_xml",
    "validate_model_output_safety",
    "SensitiveDataRedactor",
    "SanitizedLogger",
    "validate_safe_path",
    "sanitize_filename",
    "HITLGate",
    "verify_hmac_signature",
    "verify_timestamp_replay",
    "get_strict_cors_headers",
    "RateLimiter",
    "CostBudgetTracker",
    "IterationGuard",
]

