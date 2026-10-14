"""Main entrypoint for the AI & Tech Intelligence Briefing Agent."""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from config import config
from synthesizer import generate_intelligence_brief
from pdf_generator import build_brief_pdf
from emailer import send_daily_brief_email


def run_pipeline() -> Path:
    """Execute the full 4-step intelligence briefing pipeline."""
    print("=" * 70)
    print("🚀 LAUNCHING AI & TECH INTELLIGENCE BRIEFING PIPELINE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # STEP 1 & STEP 2: Search, Aggregate & Synthesize via Gemini API
    print("\n[STEP 1 & 2] Executing 24-hour sweep and synthesis across 5 pillars...")
    brief_data = generate_intelligence_brief()
    date_str = brief_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # STEP 3: Generate High-Precision PDF
    pdf_filename = f"Daily_AI_Tech_Brief_{date_str}.pdf"
    pdf_path = config.reports_dir / pdf_filename
    print(f"\n[STEP 3] Compiling briefing into publication-grade PDF: {pdf_path.name}...")
    build_brief_pdf(brief_data, pdf_path)
    print(f"✓ PDF generated successfully: {pdf_path} ({pdf_path.stat().st_size} bytes)")

    # STEP 4: Send Email with PDF Attachment
    print(f"\n[STEP 4] Dispatching briefing to {config.recipient_email}...")
    sent = send_daily_brief_email(brief_data, pdf_path)

    print("\n" + "=" * 70)
    print("✓ DAILY BRIEFING PIPELINE COMPLETE")
    print(f"  • Report: {pdf_path}")
    print(f"  • Destination: {config.recipient_email}")
    print("=" * 70)

    return pdf_path


def start_scheduler():
    """Start continuous daemon schedule to trigger every day at 07:00 AM."""
    import schedule

    target_time = config.schedule_time
    print(f"🕒 AI & Tech Briefing Agent daemon started.")
    print(f"Configured to run daily at {target_time} (Current target: {config.recipient_email}).")
    print("Press Ctrl+C to stop.")

    schedule.every().day.at(target_time).do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI & Tech Intelligence Briefing Agent")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the 24-hour sweep, generate PDF, and email immediately",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run as a daemon and execute daily at 07:00 AM",
    )

    args = parser.parse_args()

    if args.run_now or not sys.argv[1:]:
        run_pipeline()
    elif args.schedule:
        start_scheduler()


if __name__ == "__main__":
    main()
