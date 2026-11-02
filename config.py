"""Configuration loader and schema validator for the AI & Tech Intelligence Briefing Agent."""

import datetime
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
import zoneinfo
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

# Load .env if present
load_dotenv(dotenv_path=ENV_FILE)

DEFAULT_RECIPIENTS = ""

# Known recipient profiles dictionary (can be augmented via RECIPIENT_PROFILES JSON env var)
RECIPIENT_PROFILES: Dict[str, Dict[str, str]] = {}

_custom_profiles_env = os.getenv("RECIPIENT_PROFILES", "").strip()
if _custom_profiles_env:
    try:
        RECIPIENT_PROFILES.update(json.loads(_custom_profiles_env))
    except Exception:
        pass


def clean_email_address(raw_email: str) -> str:
    """Normalize and clean email address, fixing common typos like accidental double '@@'."""
    if not raw_email:
        return ""
    email = raw_email.strip().lower()
    # Normalize multiple '@' characters (e.g. user@@gmail.com -> user@gmail.com)
    email = re.sub(r"@+", "@", email)
    # Sanitize characters allowed in email addresses
    email = re.sub(r"[^\w\.\-\+@]", "", email)
    return email


def get_recipient_profile(raw_email: str) -> Dict[str, str]:
    """Retrieve or generate recipient profile metadata (name, first_name, title)."""
    email = clean_email_address(raw_email)
    if email in RECIPIENT_PROFILES:
        return RECIPIENT_PROFILES[email]

    lower_email = email.lower()

    if "kashmala" in lower_email:
        return {
            "name": "Kashmala Tariq",
            "first_name": "Kashmala",
            "title": "KASHMALA TARIQ",
        }
    if "talha" in lower_email or "muhammad" in lower_email:
        return {
            "name": "Muhammad Talha",
            "first_name": "Muhammad",
            "title": "MUHAMMAD TALHA",
        }

    # Dynamic fallback for arbitrary email addresses (e.g. first.last@domain.com -> First Last)
    local_part = email.split("@")[0] if "@" in email else email
    parts = re.split(r"[._\-+]+", local_part)
    first_name = parts[0].capitalize() if parts and parts[0] else "there"
    full_name = " ".join(p.capitalize() for p in parts if p) or "Subscriber"
    return {
        "name": full_name,
        "first_name": first_name,
        "title": full_name.upper(),
    }


def resolve_timezone(tz_string: str) -> datetime.tzinfo:
    """Robust timezone resolver supporting IANA names, UTC offsets, and standard abbreviations."""
    tz_clean = (tz_string or "Asia/Karachi").strip()

    # 1. Try ZoneInfo directly
    try:
        return zoneinfo.ZoneInfo(tz_clean)
    except Exception:
        pass

    # 2. Known aliases
    aliases = {
        "PKT": datetime.timezone(datetime.timedelta(hours=5), name="PKT"),
        "Asia/Karachi": datetime.timezone(datetime.timedelta(hours=5), name="PKT"),
        "UTC": datetime.timezone.utc,
        "GMT": datetime.timezone.utc,
        "EST": datetime.timezone(datetime.timedelta(hours=-5), name="EST"),
        "EDT": datetime.timezone(datetime.timedelta(hours=-4), name="EDT"),
        "CST": datetime.timezone(datetime.timedelta(hours=-6), name="CST"),
        "PST": datetime.timezone(datetime.timedelta(hours=-8), name="PST"),
    }
    if tz_clean in aliases:
        return aliases[tz_clean]

    # 3. Match numeric offset e.g. UTC+5, +05:00, -0400
    match = re.search(r"([+-])(\d{1,2})(?::?(\d{2}))?", tz_clean)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        hours = int(match.group(2))
        minutes = int(match.group(3) or 0)
        return datetime.timezone(datetime.timedelta(hours=sign * hours, minutes=sign * minutes))

    # Default fallback to Asia/Karachi (PKT UTC+5)
    return datetime.timezone(datetime.timedelta(hours=5), name="PKT")


class AgentConfig(BaseModel):
    """Hardened, validated configuration schema for the briefing agent."""
    model_config = ConfigDict(arbitrary_types_allowed=True, str_strip_whitespace=True)

    # Gemini API
    gemini_api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip())

    # Resend API & Email
    resend_api_key: str = Field(default_factory=lambda: os.getenv("RESEND_API_KEY", "").strip())
    recipient_email: str = Field(
        default_factory=lambda: os.getenv("RECIPIENT_EMAIL", os.getenv("RECIPIENT_EMAILS", DEFAULT_RECIPIENTS)).strip()
    )
    sender_name: str = Field(default_factory=lambda: os.getenv("SENDER_NAME", "AI & Tech Briefing Agent").strip())

    # Gmail SMTP Settings
    gmail_user: str = Field(default_factory=lambda: os.getenv("GMAIL_USER", "").strip())
    gmail_app_password: str = Field(
        default_factory=lambda: os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    )

    # Multi-Recipient & Forwarding Settings
    owner_email: str = Field(default_factory=lambda: os.getenv("OWNER_EMAIL", "").strip())
    forward_email: str = Field(default_factory=lambda: os.getenv("FORWARD_EMAIL", "").strip())

    # Schedule & Automation
    schedule_time: str = Field(default_factory=lambda: os.getenv("SCHEDULE_TIME", "07:00").strip())
    timezone: str = Field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Karachi").strip())
    catch_up_max_days: int = Field(default_factory=lambda: int(os.getenv("CATCH_UP_MAX_DAYS", "7")))

    # Resilience & Limits
    request_timeout_seconds: int = Field(default=30, ge=5, le=120)
    max_retries: int = Field(default=3, ge=1, le=10)
    max_iterations: int = Field(default=5, ge=1, le=20)
    token_budget_per_run: int = Field(default=150_000, ge=10_000, le=1_000_000)

    # Security & Sandboxing
    reports_dir: Path = Field(default_factory=lambda: BASE_DIR / "reports")
    logs_dir: Path = Field(default_factory=lambda: BASE_DIR / "logs")
    webhook_secret: str = Field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", "").strip())
    hitl_confirmation_token: str = Field(default_factory=lambda: os.getenv("HITL_CONFIRMATION_TOKEN", "").strip())

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            return "07:00"
        hours, minutes = map(int, v.split(":"))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            return "07:00"
        return v

    def get_timezone(self) -> datetime.tzinfo:
        """Return the resolved datetime tzinfo object."""
        return resolve_timezone(self.timezone)

    def get_current_local_date(self) -> str:
        """Return today's date string (YYYY-MM-DD) in the configured local timezone."""
        return datetime.datetime.now(self.get_timezone()).strftime("%Y-%m-%d")

    def get_current_local_time(self) -> str:
        """Return current time string (HH:MM:SS) in the configured local timezone."""
        return datetime.datetime.now(self.get_timezone()).strftime("%H:%M:%S")

    def get_dispatch_ledger_path(self) -> Path:
        """Return the safe path to the dispatch audit ledger."""
        return self.logs_dir / "dispatch_ledger.json"

    def get_allowed_directories(self) -> List[Path]:
        """Return the list of safe directories allowed for file operations."""
        return [BASE_DIR, self.reports_dir, self.logs_dir]

    def get_recipient_list(self) -> List[str]:
        """Return a sanitized list of recipient email addresses."""
        raw_items = []
        if self.recipient_email:
            raw_items.extend(re.split(r"[,;]+", self.recipient_email))
        if self.owner_email:
            raw_items.append(self.owner_email)
        if self.forward_email:
            raw_items.append(self.forward_email)

        recipients = []
        for item in raw_items:
            cleaned = clean_email_address(item)
            if cleaned and cleaned not in recipients:
                recipients.append(cleaned)
        return recipients

    def has_gemini_key(self) -> bool:
        key = self.gemini_api_key
        return bool(key and key != "your_gemini_api_key_here" and len(key) > 10)

    def has_resend_key(self) -> bool:
        key = self.resend_api_key
        return bool(key and key != "re_your_api_key_here" and key.startswith("re_"))

    def has_gmail_smtp(self) -> bool:
        return bool(self.gmail_user and self.gmail_app_password and len(self.gmail_app_password) >= 16)


# Instantiate and ensure directories exist safely
config = AgentConfig()
config.reports_dir.mkdir(parents=True, exist_ok=True)
config.logs_dir.mkdir(parents=True, exist_ok=True)
