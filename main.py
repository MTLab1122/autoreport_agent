"""Main entrypoint for the AI & Tech Intelligence Briefing Agent."""

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from config import config
from synthesizer import generate_intelligence_brief
from pdf_generator import build_brief_pdf
from emailer import send_daily_brief_email, send_failure_alert


class DualLogger:
    """Tee logger to write output simultaneously to stdout and the daily log file."""

    def __init__(self, log_path: Path):
        self.terminal = sys.stdout
        self.log_file = open(log_path, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        if not self.log_file.closed:
            self.log_file.close()


def setup_daily_logging() -> Path:
    """Setup daily log file in the logs directory."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = config.logs_dir / f"agent_{date_str}.log"
    sys.stdout = DualLogger(log_file)
    sys.stderr = sys.stdout
    return log_file


def run_pipeline(dry_run: bool = False, recipient: str = None) -> bool:
    """Execute the full 4-step intelligence briefing pipeline."""
    target_recipient = (recipient or config.recipient_email).strip()
    log_file = setup_daily_logging()

    print("=" * 70)
    print("🚀 LAUNCHING AI & TECH INTELLIGENCE BRIEFING PIPELINE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target Recipient: {target_recipient}")
    print(f"Log File: {log_file}")
    if dry_run:
        print("Mode: DRY-RUN (PDF generation enabled, email dispatch skipped)")
    print("=" * 70)

    try:
        # STEP 1 & STEP 2: Search, Aggregate & Synthesize
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
        if dry_run:
            print(f"\n[STEP 4] [DRY-RUN] Skipped email dispatch to {target_recipient}.")
            email_success = True
        else:
            print(f"\n[STEP 4] Dispatching briefing to {target_recipient}...")
            email_success = send_daily_brief_email(
                brief_data, pdf_path, recipient_email=target_recipient
            )

        print("\n" + "=" * 70)
        if email_success:
            print("✓ DAILY BRIEFING PIPELINE COMPLETE")
            print(f"  • Report: {pdf_path}")
            print(f"  • Destination: {target_recipient}")
            print(f"  • Logs: {log_file}")
            print("=" * 70)
            return True
        else:
            print("❌ DAILY BRIEFING PIPELINE FAILED AT EMAIL DELIVERY")
            print("=" * 70)
            return False

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {str(exc)}"
        stack_trace = traceback.format_exc()
        print("\n" + "=" * 70)
        print(f"❌ PIPELINE ERROR: {err_msg}")
        print(stack_trace)
        print("=" * 70)

        # Attempt failure alert notification
        try:
            print(f"[Alert] Attempting failure notification to {target_recipient}...")
            send_failure_alert(
                error_message=err_msg,
                log_snippet=stack_trace[-1000:],
                recipient_email=target_recipient,
            )
        except Exception:
            pass

        return False


def start_scheduler():
    """Start continuous daemon schedule to trigger every day at 07:00 AM."""
    import schedule

    target_time = config.schedule_time
    print(f"🕒 AI & Tech Briefing Agent daemon started.")
    print(f"Configured to run daily at {target_time} (Target: {config.recipient_email}).")
    print("Press Ctrl+C to stop.")

    schedule.every().day.at(target_time).do(run_pipeline)

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n🛑 Scheduler stopped cleanly.")


def verify_environment() -> bool:
    """Verify configuration, API keys, and required services."""
    print("=" * 70)
    print("🔍 VERIFYING SYSTEM CONFIGURATION & CONNECTIVITY")
    print("=" * 70)

    print(f"• Python Version: {sys.version.split()[0]}")
    print(f"• Recipient Email: {config.recipient_email}")
    print(f"• Reports Directory: {config.reports_dir} (exists: {config.reports_dir.exists()})")
    print(f"• Logs Directory: {config.logs_dir} (exists: {config.logs_dir.exists()})")

    # Check Gemini API Key
    has_gemini = config.has_gemini_key()
    print(f"• Gemini API Key Configured: {'✓ YES' if has_gemini else '✗ NO'}")

    # Check Resend API Key
    has_resend = config.has_resend_key()
    print(f"• Resend API Key Configured: {'✓ YES' if has_resend else '✗ NO'}")

    print("=" * 70)
    return bool(has_gemini and has_resend)


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI & Tech Intelligence Briefing Agent")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the 24-hour sweep, generate PDF, and email immediately",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute the pipeline and generate PDF without dispatching email",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run as a daemon and execute daily at 07:00 AM",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check configuration and credentials without running full pipeline",
    )
    parser.add_argument(
        "--recipient",
        type=str,
        default=None,
        help="Override recipient email address for this execution",
    )

    args = parser.parse_args()

    if args.verify:
        ok = verify_environment()
        sys.exit(0 if ok else 1)

    if args.schedule:
        start_scheduler()
    else:
        # Default action is --run-now
        success = run_pipeline(dry_run=args.dry_run, recipient=args.recipient)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
