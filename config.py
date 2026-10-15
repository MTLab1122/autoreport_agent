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
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()

    # Resend API & Email
    resend_api_key: str = os.getenv("RESEND_API_KEY", "").strip()
    recipient_email: str = os.getenv("RECIPIENT_EMAIL", "muhammadtalhapro1@gmail.com").strip()
    sender_name: str = os.getenv("SENDER_NAME", "AI & Tech Briefing Agent").strip()

    # Schedule
    schedule_time: str = os.getenv("SCHEDULE_TIME", "07:00").strip()

    # Paths
    reports_dir: Path = BASE_DIR / "reports"
    logs_dir: Path = BASE_DIR / "logs"

    def has_gemini_key(self) -> bool:
        key = self.gemini_api_key
        return bool(key and key != "your_gemini_api_key_here" and len(key) > 10)

    def has_resend_key(self) -> bool:
        key = self.resend_api_key
        return bool(key and key != "re_your_api_key_here" and key.startswith("re_"))

config = AgentConfig()
config.reports_dir.mkdir(parents=True, exist_ok=True)
config.logs_dir.mkdir(parents=True, exist_ok=True)
