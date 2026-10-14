"""Configuration loader for the AI & Tech Intelligence Briefing Agent."""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

# Load .env if present
load_dotenv(dotenv_path=ENV_FILE)

@dataclass
class AgentConfig:
    # Gemini API
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    # Resend API & Email
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    recipient_email: str = os.getenv("RECIPIENT_EMAIL", "muhammadtalhpro1@gmail.com")
    sender_name: str = os.getenv("SENDER_NAME", "AI & Tech Briefing Agent")

    # Schedule
    schedule_time: str = os.getenv("SCHEDULE_TIME", "07:00")

    # Paths
    reports_dir: Path = BASE_DIR / "reports"

    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here")

    def has_resend_key(self) -> bool:
        return bool(self.resend_api_key and self.resend_api_key.strip())

config = AgentConfig()
config.reports_dir.mkdir(parents=True, exist_ok=True)
