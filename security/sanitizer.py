"""Prompt injection defense, context isolation, input sanitization, and output validation."""

import html
import re
import unicodedata
from typing import Optional


# Invisible Unicode & Bidi Override characters
INVISIBLE_UNICODE_CHARS = [
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\u200e",  # Left-to-right mark
    "\u200f",  # Right-to-left mark
    "\u202a",  # Left-to-right embedding
    "\u202b",  # Right-to-left embedding
    "\u202c",  # Pop directional formatting
    "\u202d",  # Left-to-right override
    "\u202e",  # Right-to-left override
    "\u2060",  # Word joiner
    "\u2066",  # Left-to-right isolate
    "\u2067",  # Right-to-left isolate
    "\u2068",  # First strong isolate
    "\u2069",  # Pop directional isolate
    "\ufeff",  # Zero-width no-break space (BOM)
]

# Known adversarial prompt injection / jailbreak patterns
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|directives)", re.IGNORECASE),
    re.compile(r"system\s+(prompt|override|directive)", re.IGNORECASE),
    re.compile(r"(you\s+are\s+now|act\s+as)\s+(DAN|unrestricted|jailbroken|an\s+evil|chaos)", re.IGNORECASE),
    re.compile(r"(bypass|disable)\s+(all\s+)?(safety|security|content\s+filters)", re.IGNORECASE),
    re.compile(r"<\s*\|?\s*(im_start|im_end|endoftext|system)\s*\|?\s*>", re.IGNORECASE),
    re.compile(r"\[\s*/?\s*(INST|SYS)\s*\]", re.IGNORECASE),
]


def strip_invisible_unicode(text: str) -> str:
    """Strip zero-width spaces, bidi overrides, and unprintable control characters."""
    if not text:
        return ""
    # Normalize unicode to NFKC
    text = unicodedata.normalize("NFKC", text)
    # Remove known invisible characters
    for char in INVISIBLE_UNICODE_CHARS:
        text = text.replace(char, "")
    # Remove control characters except tab, newline, carriage return
    text = "".join(c for c in text if c in ("\n", "\r", "\t") or not unicodedata.category(c).startswith("C"))
    return text


def sanitize_untrusted_text(text: str, max_length: int = 5000) -> str:
    """Sanitize external untrusted text by stripping invisible characters and defanging injection payloads."""
    if not text:
        return ""
    
    cleaned = strip_invisible_unicode(str(text))
    
    # Neutralize prompt injection phrases by replacing with neutral safe placeholders
    for pattern in INJECTION_PATTERNS:
        cleaned = pattern.sub("[FILTERED_DIRECTIVE]", cleaned)
    
    # Truncate to bound memory and context window
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length] + " [TRUNCATED]"
    
    return cleaned.strip()


def wrap_untrusted_context(content: str, source_label: str) -> str:
    """Strictly delimit external untrusted data using XML tagging to isolate context."""
    sanitized = sanitize_untrusted_text(content)
    clean_label = re.sub(r"[^a-zA-Z0-9_\-]", "", source_label) or "external_source"
    return f'<untrusted_context source="{clean_label}">\n{sanitized}\n</untrusted_context>'


def safe_escape_html(text: Optional[str]) -> str:
    """Escape text for safe HTML rendering to prevent XSS and template injection."""
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def safe_escape_xml(val: Optional[str]) -> str:
    """Sanitize text for ReportLab XML parser to prevent syntax crashes on &, <, >."""
    if val is None:
        return ""
    return html.escape(str(val), quote=True)


def validate_model_output_safety(text: str) -> bool:
    """Verify that model output does not attempt to emit malicious executable scripts or raw shell commands."""
    if not text:
        return True
    
    dangerous_signatures = [
        re.compile(r"<\s*script\b", re.IGNORECASE),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"data\s*:\s*text/html", re.IGNORECASE),
        re.compile(r"__import__\s*\(", re.IGNORECASE),
        re.compile(r"eval\s*\(", re.IGNORECASE),
        re.compile(r"exec\s*\(", re.IGNORECASE),
        re.compile(r"subprocess\.", re.IGNORECASE),
        re.compile(r"os\.system\s*\(", re.IGNORECASE),
    ]
    for sig in dangerous_signatures:
        if sig.search(text):
            return False
    return True
