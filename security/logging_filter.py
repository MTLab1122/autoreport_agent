"""Sensitive data and secret redaction filter for safe logging and telemetry."""

import io
import re
import sys
from pathlib import Path
from typing import Optional, TextIO


class SensitiveDataRedactor:
    """Regex-based secret, API key, and PII redactor."""

    PATTERNS = [
        # Gemini / Google AI Studio Keys
        (re.compile(r"AQ\.[A-Za-z0-9_\-]{15,}", re.IGNORECASE), "AQ.[REDACTED_GEMINI_KEY]"),
        (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "AIza[REDACTED_GOOGLE_KEY]"),
        # Resend API Keys
        (re.compile(r"re_[A-Za-z0-9_\-]{20,}", re.IGNORECASE), "re_[REDACTED_RESEND_KEY]"),
        # GitHub Tokens
        (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}"), "ghp_[REDACTED_GITHUB_TOKEN]"),
        (re.compile(r"github_pat_[A-Za-z0-9_]{60,255}"), "github_pat_[REDACTED_TOKEN]"),
        # HTTP Bearer Tokens
        (re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
        # 16-character Gmail App Passwords (with or without spaces)
        (re.compile(r"\b[a-z]{4}\s+[a-z]{4}\s+[a-z]{4}\s+[a-z]{4}\b"), "[REDACTED_APP_PASSWORD]"),
        # Common key-value secrets
        (
            re.compile(r"""(?i)(["']?(?:password|secret|api_key|token|auth_key|app_password)["']?\s*[:=]\s*["']?)([^"'\s,}{]+)(["']?)"""),
            r"\g<1>[REDACTED]\g<3>",
        ),
    ]

    @classmethod
    def redact(cls, text: str) -> str:
        """Apply all redaction rules to input text."""
        if not text:
            return ""
        result = str(text)
        for pattern, replacement in cls.PATTERNS:
            result = pattern.sub(replacement, result)
        return result


class SanitizedLogger:
    """Dual-output stream tee that applies automated secret redaction before writing to stdout/file."""

    def __init__(self, log_path: Optional[Path] = None, original_stream: Optional[TextIO] = None):
        self.terminal = original_stream or sys.__stdout__
        self.log_file = None
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file = open(log_path, "a", encoding="utf-8")

    def write(self, message: str) -> int:
        if not message:
            return 0
        cleaned = SensitiveDataRedactor.redact(message)
        if self.terminal:
            self.terminal.write(cleaned)
        if self.log_file and not self.log_file.closed:
            self.log_file.write(cleaned)
            self.log_file.flush()
        return len(cleaned)

    def flush(self) -> None:
        if self.terminal and hasattr(self.terminal, "flush"):
            self.terminal.flush()
        if self.log_file and not self.log_file.closed:
            self.log_file.flush()

    def close(self) -> None:
        if self.log_file and not self.log_file.closed:
            self.log_file.close()

