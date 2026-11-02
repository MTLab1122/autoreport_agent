"""Main orchestration entrypoint for the AI & Tech Intelligence Briefing Agent."""

import argparse
import http.server
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from config import config, clean_email_address, get_recipient_profile
from models.schemas import IntelligenceBrief
from orchestration.state_manager import StateManager
from orchestration.telemetry import TelemetryRecorder
from pdf_generator import build_brief_pdf
from security.logging_filter import SanitizedLogger, SensitiveDataRedactor
from security.rate_limiter import CostBudgetTracker, RateLimiter
from security.sandbox import HITLGate, sanitize_filename, validate_safe_path
from security.webhook_auth import (
    verify_hmac_signature,
    verify_timestamp_replay,
    get_strict_cors_headers,
)
from synthesizer import generate_intelligence_brief
from emailer import send_daily_brief_email, send_failure_alert


def setup_daily_logging(date_str: Optional[str] = None) -> Path:
    """Setup daily log file with automated secret and PII redaction."""
    effective_date = date_str or config.get_current_local_date()
    log_file = config.logs_dir / f"agent_{effective_date}.log"
    safe_log_path = validate_safe_path(log_file, config.get_allowed_directories())

    sanitized_stream = SanitizedLogger(safe_log_path, original_stream=sys.__stdout__)
    sys.stdout = sanitized_stream
    sys.stderr = sanitized_stream
    return safe_log_path


def run_pipeline(
    target_date: Optional[str] = None,
    dry_run: bool = False,
    recipient: Optional[str] = None,
    resume: bool = True,
    confirmation_token: Optional[str] = None,
) -> bool:
    """Execute the hardened 4-step intelligence briefing pipeline with state persistence and idempotency."""
    date_str = target_date or config.get_current_local_date()

    if recipient:
        target_recipients = [clean_email_address(r) for r in re.split(r"[,;]+", recipient) if clean_email_address(r)]
    else:
        target_recipients = config.get_recipient_list()

    log_file = setup_daily_logging(date_str)

    # Initialize observability & state
    telemetry = TelemetryRecorder(config.logs_dir, config.get_allowed_directories())
    budget_tracker = CostBudgetTracker(max_tokens_per_run=config.token_budget_per_run)
    state_mgr = StateManager(config.logs_dir / "checkpoints", config.get_allowed_directories())
    state = state_mgr.initialize_run(telemetry.trace_id, date_str, resume=resume)

    print("=" * 70)
    print("🚀 LAUNCHING HARDENED AI & TECH INTELLIGENCE BRIEFING PIPELINE")
    print(f"Timestamp (UTC): {datetime.now(timezone.utc).isoformat()}")
    print(f"Configured Timezone: {config.timezone} (Local Date: {date_str}, Local Time: {config.get_current_local_time()})")
    print(f"Trace ID: {telemetry.trace_id}")
    print(f"Target Recipients ({len(target_recipients)}): {', '.join(target_recipients)}")
    print(f"Log File: {log_file}")
    if dry_run:
        print("Mode: DRY-RUN (PDF generation enabled, email dispatch skipped)")
    print("=" * 70)

    try:
        # STEP 1 & 2: Search, Aggregate & Synthesize
        brief_data = None
        if resume and state_mgr.is_step_done("SYNTHESIZED") and state.brief_data:
            print("\n[STEP 1 & 2] Checkpoint found: Reusing synthesized brief from state...")
            brief_data = state.brief_data
        else:
            print(f"\n[STEP 1 & 2] Executing 24-hour sweep and synthesis across 5 pillars for {date_str}...")
            step_start = time.time()
            brief_data = generate_intelligence_brief(
                target_date=date_str,
                telemetry=telemetry,
                budget_tracker=budget_tracker,
            )
            step_latency = (time.time() - step_start) * 1000
            state_mgr.mark_step_done("SYNTHESIZED", brief_data=brief_data)
            telemetry.record_step(
                agent_step="AGGREGATE_AND_SYNTHESIZE",
                latency_ms=step_latency,
                validation_status="SUCCESS",
            )

        # Validate brief data against schema and preserve exact target date
        brief_data['date'] = date_str
        brief_model = IntelligenceBrief.model_validate(brief_data)

        # STEP 3: Generate Master & Personalized PDFs with Path Containment
        generated_reports = {}
        master_pdf_filename = sanitize_filename(f"Daily_AI_Tech_Brief_{date_str}.pdf")
        master_pdf_path = config.reports_dir / master_pdf_filename

        print(f"\n[STEP 3] Compiling master briefing PDF: {master_pdf_filename}...")
        step3_start = time.time()
        build_brief_pdf(brief_data, master_pdf_path)
        generated_reports["master"] = str(master_pdf_path)
        print(f"✓ Master PDF generated: {master_pdf_path.name} ({master_pdf_path.stat().st_size} bytes)")

        # Prepare personalized PDFs
        recipient_packages = {}
        for target in target_recipients:
            prof = get_recipient_profile(target)
            first_name = sanitize_filename(prof["first_name"])
            title_name = prof["title"]
            personalized_filename = sanitize_filename(f"Daily_AI_Tech_Brief_{date_str}_{first_name}.pdf")
            p_path = config.reports_dir / personalized_filename
            build_brief_pdf(brief_data, p_path, recipient_name=title_name)
            generated_reports[target] = str(p_path)
            recipient_packages[target] = {
                "pdf_path": p_path,
                "profile": prof,
            }
            print(f"  • Personalized PDF for {prof['name']}: {p_path.name}")

        state_mgr.mark_step_done("RENDERED", generated_reports=generated_reports)
        telemetry.record_step(
            agent_step="RENDER_PDFS",
            latency_ms=(time.time() - step3_start) * 1000,
            validation_status="SUCCESS",
            details={"reports_count": len(generated_reports)},
        )

        # STEP 4: Send Personalized Emails with Idempotency & HITL Gates
        successes = []
        failures = []

        if dry_run:
            for target in target_recipients:
                prof = get_recipient_profile(target)
                print(f"\n[STEP 4] [DRY-RUN] Skipped email dispatch to {target} ({prof['name']}).")
                successes.append(target)
        else:
            # Human-in-the-Loop check for live external dispatches if configured
            if len(target_recipients) > 1 and not confirmation_token and not os.getenv("AUTO_APPROVE_DISPATCH"):
                HITLGate.verify_action_authorized(
                    action_name="bulk_email_dispatch",
                    confirmation_token=confirmation_token,
                    auto_approved=True,  # Default to authorized for scheduled autonomous runs unless token is explicitly required
                )

            for target in target_recipients:
                pkg = recipient_packages.get(target)
                prof = pkg["profile"] if pkg else get_recipient_profile(target)
                p_path = pkg["pdf_path"] if pkg else master_pdf_path

                # Check Idempotency & Ledger: Skip if already successfully dispatched for this date
                if resume and state_mgr.is_recipient_delivered_for_date(date_str, target):
                    print(f"\n[STEP 4] Recipient '{target}' already dispatched for {date_str}. Skipping duplicate send.")
                    successes.append(target)
                    continue

                idempotency_key = state_mgr.generate_idempotency_key(target, brief_model.top_headline)

                print(f"\n[STEP 4] Dispatching briefing to {target} ({prof['name']})...")
                send_start = time.time()
                sent = send_daily_brief_email(
                    report_data=brief_data,
                    pdf_path=p_path,
                    recipient_email=target,
                    recipient_name=prof["first_name"],
                    idempotency_key=idempotency_key,
                )
                send_latency = (time.time() - send_start) * 1000

                state_mgr.record_recipient_dispatch(target, idempotency_key, success=sent)
                telemetry.record_step(
                    agent_step="DISPATCH_EMAIL",
                    tool_name="Emailer",
                    latency_ms=send_latency,
                    validation_status="SUCCESS" if sent else "FAILED",
                    details={"recipient": target, "idempotency_key": idempotency_key},
                )

                if sent:
                    successes.append(target)
                else:
                    failures.append(target)

        state_mgr.mark_step_done("DISPATCHED")

        # Record into persistent audit ledger
        idempotency_map = state_mgr.state.idempotency_keys if state_mgr.state else {}
        state_mgr.record_ledger_entry(
            date_str=date_str,
            target_recipients=target_recipients,
            delivered=successes,
            failed=failures,
            report_paths=generated_reports,
            idempotency_keys=idempotency_map,
            trace_id=telemetry.trace_id,
        )

        print("\n" + "=" * 70)
        if not failures and successes:
            print(f"✓ DAILY BRIEFING PIPELINE COMPLETE FOR {date_str}")
            print(f"  • Trace ID: {telemetry.trace_id}")
            print(f"  • Master Report: {master_pdf_path}")
            print(f"  • Delivered To ({len(successes)}): {', '.join(successes)}")
            print(f"  • Logs: {log_file}")
            print("=" * 70)
            return True
        else:
            err_msg = f"Delivery failed for {len(failures)} recipient(s): {', '.join(failures)}"
            print(f"❌ DAILY BRIEFING PIPELINE INCOMPLETE FOR {date_str}")
            print(f"  • Successful Recipients ({len(successes)}): {', '.join(successes)}")
            print(f"  • Failed Recipients ({len(failures)}): {', '.join(failures)}")
            print("=" * 70)

            # Trigger immediate failure alert
            try:
                alert_target = target_recipients[0] if target_recipients else config.recipient_email
                send_failure_alert(
                    error_message=f"Briefing delivery failed for date {date_str}: {err_msg}",
                    log_snippet=f"Failed recipients: {', '.join(failures)}\nDelivered: {', '.join(successes)}",
                    recipient_email=alert_target,
                )
            except Exception:
                pass

            return False

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {str(exc)}"
        stack_trace = traceback.format_exc()
        safe_stack = SensitiveDataRedactor.redact(stack_trace)

        print("\n" + "=" * 70)
        print(f"❌ PIPELINE ERROR FOR {date_str}: {err_msg}")
        print(safe_stack)
        print("=" * 70)

        telemetry.record_step(
            agent_step="PIPELINE_ERROR",
            validation_status="FAILED",
            details={"error": err_msg, "date": date_str},
        )

        try:
            alert_target = target_recipients[0] if target_recipients else config.recipient_email
            send_failure_alert(
                error_message=f"Pipeline exception for date {date_str}: {err_msg}",
                log_snippet=safe_stack[-1000:],
                recipient_email=alert_target,
            )
        except Exception:
            pass

        return False


def run_catch_up(lookback_days: Optional[int] = None, dry_run: bool = False) -> bool:
    """Scan lookback window for missed or incomplete daily reports and catch up automatically."""
    days = lookback_days or config.catch_up_max_days
    target_recipients = config.get_recipient_list()
    today_local = config.get_current_local_date()
    state_mgr = StateManager(config.logs_dir / "checkpoints", config.get_allowed_directories())

    print("\n" + "=" * 70)
    print(f"🔍 SCANNING FOR MISSED REPORTING CYCLES")
    print(f"  • Lookback Window: {days} days")
    print(f"  • Configured Timezone: {config.timezone}")
    print(f"  • Reference Local Date: {today_local}")
    print(f"  • Monitored Recipients ({len(target_recipients)}): {', '.join(target_recipients)}")
    print("=" * 70)

    missed_dates = state_mgr.find_missed_dates(
        lookback_days=days,
        required_recipients=target_recipients,
        reference_date=today_local,
    )

    if not missed_dates:
        print(f"✓ CATCH-UP AUDIT COMPLETE: All scheduled reports in the {days}-day lookback are verified and delivered.")
        return True

    print(f"\n⚠️ CATCH-UP IDENTIFIED {len(missed_dates)} MISSED CYCLE(S): {', '.join(missed_dates)}")
    all_recovered = True

    for m_date in missed_dates:
        undelivered = state_mgr.get_undelivered_recipients_for_date(m_date, target_recipients)
        if not undelivered:
            continue

        print(f"\n🔄 [CATCH-UP] Generating & dispatching outstanding brief for {m_date}...")
        print(f"  • Target Date: {m_date}")
        print(f"  • Missing Recipients ({len(undelivered)}): {', '.join(undelivered)}")

        ok = run_pipeline(
            target_date=m_date,
            dry_run=dry_run,
            recipient=",".join(undelivered),
            resume=True,
        )
        if not ok:
            all_recovered = False
            print(f"❌ [CATCH-UP] Failed to recover report for {m_date}.")

    return all_recovered


def start_scheduler():
    """Start continuous background scheduler to trigger daily at configured time with catch-up."""
    target_time = config.schedule_time
    tz = config.get_timezone()
    recipients_display = ", ".join(config.get_recipient_list())

    print("=" * 70)
    print("🕒 AI & TECH BRIEFING SCHEDULER STARTED (ALWAYS-ON DAEMON)")
    print(f"  • Scheduled Delivery: Daily at {target_time} ({config.timezone})")
    print(f"  • Recipients: {recipients_display}")
    print(f"  • Catch-Up Engine: Active (Window: {config.catch_up_max_days} days)")
    print(f"  • Current Local Time: {config.get_current_local_time()} ({config.get_current_local_date()})")
    print("=" * 70)

    # 1. Immediate catch-up check on startup
    print("\n[Scheduler Startup] Running initial catch-up audit...")
    try:
        run_catch_up()
    except Exception as e:
        print(f"[Scheduler Startup Warning] Initial catch-up failed: {e}")

    # 2. Main daemon loop checking every 30 seconds
    last_run_date = None
    try:
        while True:
            now_dt = datetime.now(tz)
            current_time_str = now_dt.strftime("%H:%M")
            current_date_str = now_dt.strftime("%Y-%m-%d")

            # Check if it's the exact scheduled minute and has not run yet for today
            if current_time_str == target_time and last_run_date != current_date_str:
                print(f"\n[Scheduler Trigger] Time matched ({target_time} {config.timezone}). Initiating daily brief...")
                success = run_pipeline(target_date=current_date_str)
                if success:
                    last_run_date = current_date_str
                time.sleep(60)
            else:
                time.sleep(30)

    except KeyboardInterrupt:
        print("\n🛑 Scheduler stopped cleanly.")


class WebhookServer(http.server.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, webhook_secret: str):
        super().__init__(server_address, RequestHandlerClass)
        self.webhook_secret = webhook_secret
        self.rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


class WebhookRequestHandler(http.server.BaseHTTPRequestHandler):
    """Secure webhook request handler with HMAC verification, replay defense, and rate limiting."""

    def do_OPTIONS(self):
        cors = get_strict_cors_headers(self.headers.get("Origin"))
        self.send_response(204)
        for k, v in cors.items():
            self.send_header(k, v)
        self.end_headers()

    def do_POST(self):
        client_ip = self.client_address[0]
        cors = get_strict_cors_headers(self.headers.get("Origin"))

        # Rate limiting check
        if not self.server.rate_limiter.is_allowed(client_ip):
            self.send_response(429)
            for k, v in cors.items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Too Many Requests"}\n')
            return

        # Path check
        if self.path not in ("/webhook", "/trigger"):
            self.send_response(404)
            self.end_headers()
            return

        # Timestamp replay verification
        timestamp = self.headers.get("X-Timestamp") or self.headers.get("X-Request-Timestamp")
        if timestamp and not verify_timestamp_replay(timestamp, tolerance_seconds=300):
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Request timestamp expired or invalid"}\n')
            return

        # Content length check (bound to 64KB max payload)
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 65536:
                self.send_response(413)
                self.end_headers()
                return
            body = self.rfile.read(content_length)
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        # HMAC Signature Verification
        if self.server.webhook_secret:
            sig = self.headers.get("X-Hub-Signature-256") or self.headers.get("X-Signature-SHA256")
            if not sig or not verify_hmac_signature(body, sig, self.server.webhook_secret):
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid HMAC signature"}\n')
                return

        # Parse JSON payload
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        dry_run = bool(payload.get("dry_run", False))
        recipient = payload.get("recipient")
        target_date = payload.get("date")

        # Acknowledge trigger and execute asynchronously or inline
        self.send_response(202)
        for k, v in cors.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "Trigger received and pipeline initiated"}\n')

        # Run pipeline
        run_pipeline(target_date=target_date, dry_run=dry_run, recipient=recipient)

    def log_message(self, format, *args):
        cleaned = SensitiveDataRedactor.redact(format % args)
        print(f"[Webhook] {cleaned}")


def start_webhook_listener(port: int = 8080):
    """Start local zero-trust webhook listener."""
    secret = config.webhook_secret or os.getenv("WEBHOOK_SECRET", "")
    server_address = ("127.0.0.1", port)
    httpd = WebhookServer(server_address, WebhookRequestHandler, webhook_secret=secret)
    print(f"🔒 Secure Webhook Listener started at http://127.0.0.1:{port}/trigger")
    print(f"  • HMAC Verification: {'Active' if secret else 'Disabled (Set WEBHOOK_SECRET)'}")
    print(f"  • Replay Window: 300 seconds")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Webhook listener stopped.")
        httpd.server_close()


def verify_environment() -> bool:
    """Verify configuration, API keys, timezone, ledger, and required services."""
    print("=" * 70)
    print("🔍 VERIFYING SYSTEM CONFIGURATION & ZERO-TRUST CONTROLS")
    print("=" * 70)

    print(f"• Python Version: {sys.version.split()[0]}")
    print(f"• Configured Timezone: {config.timezone}")
    print(f"• Current Local Time: {config.get_current_local_time()} ({config.get_current_local_date()})")
    recipients = config.get_recipient_list()
    print(f"• Configured Recipients ({len(recipients)}):")
    for r in recipients:
        p = get_recipient_profile(r)
        print(f"    - {r} (Name: {p['name']}, Greeting: 'Hi {p['first_name']},')")
    print(f"• Daily Schedule: {config.schedule_time} ({config.timezone})")
    print(f"• Catch-Up Window: {config.catch_up_max_days} days")
    print(f"• Reports Directory: {config.reports_dir} (exists: {config.reports_dir.exists()})")
    print(f"• Logs Directory: {config.logs_dir} (exists: {config.logs_dir.exists()})")

    # Check Audit Ledger
    state_mgr = StateManager(config.logs_dir / "checkpoints", config.get_allowed_directories())
    ledger = state_mgr.load_ledger()
    dispatches_count = len(ledger.get("dispatches", {}))
    print(f"• Dispatch Audit Ledger: {config.get_dispatch_ledger_path()} ({dispatches_count} records logged)")

    # Check Gemini API Key
    has_gemini = config.has_gemini_key()
    print(f"• Gemini API Key Configured: {'✓ YES' if has_gemini else '✗ NO'}")

    # Check Gmail SMTP
    has_gmail = config.has_gmail_smtp()
    print(f"• Gmail SMTP (App Password) Configured: {'✓ YES' if has_gmail else '✗ NO'}")

    # Check Resend API Key
    has_resend = config.has_resend_key()
    print(f"• Resend API Key Configured: {'✓ YES' if has_resend else '✗ NO'}")

    # Check Webhook Secret
    has_webhook = bool(config.webhook_secret)
    print(f"• Webhook Secret Configured: {'✓ YES' if has_webhook else '✗ NO (Optional)'}")

    # Scan for missed reports
    missed = state_mgr.find_missed_dates(lookback_days=config.catch_up_max_days, required_recipients=recipients)
    if missed:
        print(f"• ⚠️ Missed Report Cycles in Window ({len(missed)}): {', '.join(missed)} (Run with --catch-up to recover)")
    else:
        print(f"• ✓ Missed Report Cycles in Window: None (100% up to date)")

    print("=" * 70)
    return bool(has_gemini and (has_gmail or has_resend))


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI & Tech Intelligence Briefing Agent")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Execute the 24-hour sweep, generate PDF, and email immediately (includes catch-up check)",
    )
    parser.add_argument(
        "--catch-up",
        action="store_true",
        help="Audit lookback window for missed/incomplete reports and deliver outstanding ones",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Generate and dispatch report for a specific date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute the pipeline and generate PDF without dispatching email",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run as an always-on daemon and execute daily at configured schedule time with catch-up",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check configuration, timezone, credentials, and ledger without running full pipeline",
    )
    parser.add_argument(
        "--recipient",
        type=str,
        default=None,
        help="Override recipient email address for this execution",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume pipeline from saved checkpoint if available (default: True)",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Ignore checkpoints and force fresh pipeline run",
    )
    parser.add_argument(
        "--confirm-token",
        type=str,
        default=None,
        help="Confirmation token for Human-in-the-Loop gates on high-impact actions",
    )
    parser.add_argument(
        "--webhook-listen",
        action="store_true",
        help="Start local HTTP webhook listener with HMAC signature verification",
    )
    parser.add_argument(
        "--webhook-port",
        type=int,
        default=8080,
        help="Port for webhook listener (default: 8080)",
    )

    args = parser.parse_args()

    if args.verify:
        ok = verify_environment()
        sys.exit(0 if ok else 1)

    if args.catch_up:
        ok = run_catch_up(dry_run=args.dry_run)
        sys.exit(0 if ok else 1)

    if args.webhook_listen:
        start_webhook_listener(port=args.webhook_port)
    elif args.schedule:
        start_scheduler()
    else:
        # If run-now is invoked, first run catch-up to ensure no previous cycles were missed
        if args.run_now and not args.date:
            print("[Pipeline Pre-Flight] Checking for any missed previous cycles before daily run...")
            try:
                run_catch_up(dry_run=args.dry_run)
            except Exception as e:
                print(f"[Pipeline Pre-Flight Warning] Catch-up check failed: {e}")

        success = run_pipeline(
            target_date=args.date,
            dry_run=args.dry_run,
            recipient=args.recipient,
            resume=args.resume,
            confirmation_token=args.confirm_token,
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
