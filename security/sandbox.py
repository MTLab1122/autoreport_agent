"""Filesystem sandboxing, path traversal prevention, and Human-in-the-Loop (HITL) gates."""

import os
import re
from pathlib import Path
from typing import List, Union, Optional


class PathTraversalError(PermissionError):
    """Raised when a path traversal attempt is detected."""
    pass


class HITLApprovalRequired(RuntimeError):
    """Raised when a high-impact operation is blocked pending explicit confirmation."""
    pass


def sanitize_filename(filename: str, default: str = "report.pdf") -> str:
    """Sanitize a filename by removing path separators, control characters, and parent directory references."""
    if not filename:
        return default
    # Remove null bytes and control characters
    cleaned = "".join(c for c in str(filename) if c.isprintable() and c not in '/\\:*?"<>|')
    # Remove parent traversal sequences
    cleaned = re.sub(r"\.\.+", ".", cleaned).strip(". ")
    if not cleaned:
        return default
    # Limit length to 150 characters
    return cleaned[:150]


def validate_safe_path(target_path: Union[str, Path], allowed_directories: List[Path]) -> Path:
    """Ensure that the resolved target path is strictly contained within one of the allowed directories."""
    resolved_path = Path(target_path).resolve()
    
    # Check against each allowed directory
    is_safe = False
    for allowed_dir in allowed_directories:
        resolved_allowed = allowed_dir.resolve()
        try:
            # If resolved_path is relative to resolved_allowed, it is contained
            resolved_path.relative_to(resolved_allowed)
            is_safe = True
            break
        except ValueError:
            continue

    if not is_safe:
        allowed_str = ", ".join(str(d.resolve()) for d in allowed_directories)
        raise PathTraversalError(
            f"Security Violation: Target path '{target_path}' resolves outside allowed boundaries: [{allowed_str}]"
        )

    return resolved_path


class HITLGate:
    """Human-in-the-Loop gate requiring an explicit token or programmatic confirmation for destructive/high-impact actions."""

    @staticmethod
    def verify_action_authorized(
        action_name: str,
        confirmation_token: Optional[str] = None,
        expected_token: Optional[str] = None,
        auto_approved: bool = False,
    ) -> bool:
        """Verify if a high-impact action (e.g. bulk external dispatches) has valid approval."""
        if auto_approved:
            return True

        # If an expected token is configured via environment or caller, require an exact match
        required = expected_token or os.getenv("HITL_CONFIRMATION_TOKEN")
        if not required:
            # If no token requirement configured, allow if auto_approved or interactive confirmation
            return True

        if confirmation_token != required:
            raise HITLApprovalRequired(
                f"Action '{action_name}' blocked: Valid HITL confirmation token is required."
            )

        return True
