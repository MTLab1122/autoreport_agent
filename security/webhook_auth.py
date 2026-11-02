"""Webhook authentication, HMAC signature verification, timestamp replay protection, and CORS policies."""

import hmac
import hashlib
import time
from typing import Dict, Union, Optional


def verify_hmac_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret_key: str,
    algorithm: str = "sha256",
) -> bool:
    """Validate an HMAC signature using constant-time comparison to prevent timing attacks."""
    if not signature_header or not secret_key:
        return False

    # Extract signature without 'sha256=' prefix if present
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig[len("sha256=") :]

    # Compute expected signature
    computed = hmac.new(
        secret_key.encode("utf-8"),
        payload_bytes,
        getattr(hashlib, algorithm, hashlib.sha256),
    ).hexdigest()

    return hmac.compare_digest(sig.lower(), computed.lower())


def verify_timestamp_replay(
    timestamp_header: Union[str, int, float],
    tolerance_seconds: int = 300,
    current_time: Optional[float] = None,
) -> bool:
    """Enforce timestamp replay protection. Rejects requests older than tolerance_seconds or in the future."""
    if not timestamp_header:
        return False

    try:
        req_time = float(timestamp_header)
    except (ValueError, TypeError):
        return False

    now = current_time if current_time is not None else time.time()
    
    # Reject if in the future by more than 10 seconds (clock skew buffer)
    if req_time > now + 10:
        return False
    
    # Reject if older than tolerance window
    if now - req_time > tolerance_seconds:
        return False

    return True


def get_strict_cors_headers(origin: Optional[str] = None, allowed_origins: Optional[list] = None) -> Dict[str, str]:
    """Generate strict, zero-trust CORS headers (no wildcards allowed when credentials exist)."""
    headers = {
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Hub-Signature-256, X-Timestamp",
        "Access-Control-Max-Age": "600",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    allowed = allowed_origins or []
    if origin and (origin in allowed or not allowed):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    else:
        # Deny or restrict origin
        headers["Access-Control-Allow-Origin"] = "null"

    return headers

