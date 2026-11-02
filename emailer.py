"""Hardened email dispatch module with XSS protection, idempotency tracking, and retry resilience."""

import base64
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

from config import config, clean_email_address, get_recipient_profile
from orchestration.retry_handler import retry_with_backoff
from security.logging_filter import SensitiveDataRedactor
from security.sandbox import validate_safe_path
from security.sanitizer import safe_escape_html

RESEND_API_URL = "https://api.resend.com/emails"
SENDER = "AI Tech Agent <onboarding@resend.dev>"


def compose_email_payload(
    report_data: Dict[str, Any],
    pdf_path: Optional[Path] = None,
    recipient_email: Optional[str] = None,
    recipient_name: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a secure email JSON payload with full HTML escaping and base64 attachment."""
    raw_date = report_data.get("date", "Today")
    raw_headline = report_data.get("top_headline", "Frontier AI Releases & Breakthroughs")
    highlights = report_data.get("highlights", [])

    date_str = safe_escape_html(raw_date)
    top_headline = safe_escape_html(raw_headline)

    h1_raw = highlights[0] if len(highlights) > 0 else "Frontier model launches and industry shifts."
    h2_raw = highlights[1] if len(highlights) > 1 else "Developer frameworks and tooling optimizations."
    h3_raw = highlights[2] if len(highlights) > 2 else "High-signal practitioner insights and trending repositories."

    h1 = safe_escape_html(h1_raw)
    h2 = safe_escape_html(h2_raw)
    h3 = safe_escape_html(h3_raw)

    raw_target = recipient_email or config.recipient_email
    target_email = clean_email_address(raw_target.split(",")[0] if "," in raw_target else raw_target)
    profile = get_recipient_profile(target_email)
    first_name_raw = recipient_name or profile.get("first_name", "there")
    first_name = safe_escape_html(first_name_raw)

    subject = f"⚡ Daily AI & Tech Brief — {raw_date}: {raw_headline}"

    body_text = f"""Hi {first_name_raw},

Attached is your precision AI & Tech Intelligence Brief for {raw_date}.

Top 3 Highlights Today:
1. {h1_raw}
2. {h2_raw}
3. {h3_raw}

Full breakdown across all 5 intelligence pillars is available in the attached publication-grade PDF.
"""

    body_html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #0f172a; margin-bottom: 8px;">⚡ Daily AI &amp; Tech Intelligence Brief</h2>
  <p style="color: #64748b; font-size: 14px; margin-top: 0;">Date: {date_str} &bull; Delivery: 07:00 AM</p>
  <h3 style="color: #1e293b; margin: 12px 0 6px 0; font-size: 16px;">{top_headline}</h3>
  <p>Hi {first_name},</p>
  <p>Attached is your precision AI &amp; Tech Intelligence Brief for <strong>{date_str}</strong>.</p>
  <div style="background-color: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
    <h3 style="margin: 0 0 8px 0; font-size: 15px; color: #1e293b;">Top 3 Highlights Today:</h3>
    <ol style="margin: 0; padding-left: 20px; color: #334155;">
      <li style="margin-bottom: 6px;">{h1}</li>
      <li style="margin-bottom: 6px;">{h2}</li>
      <li style="margin-bottom: 6px;">{h3}</li>
    </ol>
  </div>
  <p style="font-size: 14px; color: #475569;">Full breakdown across all 5 intelligence pillars is available in the attached PDF.</p>
</div>"""

    payload: Dict[str, Any] = {
        "from": SENDER,
        "to": [target_email],
        "subject": subject,
        "text": body_text,
        "html": body_html,
    }

    if idempotency_key:
        payload["headers"] = {"Idempotency-Key": idempotency_key}

    attachments = []
    if pdf_path:
        safe_path = validate_safe_path(pdf_path, config.get_allowed_directories())
        if safe_path.exists():
            with open(safe_path, "rb") as f:
                pdf_bytes = f.read()
            encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
            attachments.append({
                "filename": safe_path.name,
                "content": encoded_pdf,
            })
        else:
            print(f"[Emailer Warning] PDF attachment not found at {safe_path}")

    if attachments:
        payload["attachments"] = attachments

    return payload


compose_email = compose_email_payload


@retry_with_backoff(max_retries=3, initial_delay=2.0, max_delay=15.0)
def _dispatch_gmail_smtp(msg: MIMEMultipart, recipients: List[str]) -> None:
    """Internal SMTP dispatch with exponential backoff and strict SSL verification."""
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=config.request_timeout_seconds) as server:
        server.login(config.gmail_user, config.gmail_app_password)
        for to_addr in recipients:
            server.sendmail(config.gmail_user, to_addr, msg.as_string())


def send_email_via_gmail_smtp(
    report_data: Dict[str, Any],
    pdf_path: Optional[Path] = None,
    recipient_email: Optional[str] = None,
    recipient_name: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> bool:
    """Dispatch briefing email directly via Gmail SMTP with safety validation."""
    if not config.has_gmail_smtp():
        return False

    payload = compose_email_payload(
        report_data,
        pdf_path,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        idempotency_key=idempotency_key,
    )
    recipients = payload.get("to", [])
    recipient_display = ", ".join(recipients)
    subject = payload.get("subject", "")
    from_header = f"{config.sender_name} <{config.gmail_user}>"

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_header
    msg["To"] = recipient_display
    if idempotency_key:
        msg["X-Entity-Ref-ID"] = idempotency_key

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(payload.get("text", ""), "plain", "utf-8"))
    alt_part.attach(MIMEText(payload.get("html", ""), "html", "utf-8"))
    msg.attach(alt_part)

    if pdf_path:
        safe_path = validate_safe_path(pdf_path, config.get_allowed_directories())
        if safe_path.exists():
            with open(safe_path, "rb") as f:
                pdf_part = MIMEApplication(f.read(), _subtype="pdf")
                pdf_part.add_header("Content-Disposition", "attachment", filename=safe_path.name)
                msg.attach(pdf_part)

    try:
        print(f"\n[Emailer - Gmail SMTP] Connecting to smtp.gmail.com:465 (SSL)...")
        print(f"  • To: {recipient_display}")
        print(f"  • Subject: {subject}")
        _dispatch_gmail_smtp(msg, recipients)
        print(f"[Emailer Success] Intelligence brief successfully delivered via Gmail SMTP to {recipient_display}!")
        return True
    except Exception as e:
        redacted_err = SensitiveDataRedactor.redact(str(e))
        print(f"[Emailer Error] Gmail SMTP dispatch failed for {recipient_display}: {redacted_err}")
        return False


def send_daily_brief_email(
    report_data: Dict[str, Any],
    pdf_path: Optional[Path] = None,
    recipient_email: Optional[str] = None,
    recipient_name: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> bool:
    """Dispatch briefing email via Gmail SMTP or Resend HTTP API with idempotency and retries."""
    # 1. Primary: Use Gmail SMTP if configured
    if config.has_gmail_smtp():
        sent = send_email_via_gmail_smtp(
            report_data=report_data,
            pdf_path=pdf_path,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            idempotency_key=idempotency_key,
        )
        if sent:
            return True
        print("[Emailer] Gmail SMTP dispatch did not succeed; checking Resend API fallback...")

    # 2. Resend HTTP API fallback
    payload = compose_email_payload(
        report_data,
        pdf_path,
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        idempotency_key=idempotency_key,
    )
    recipient_display = ", ".join(payload.get("to", []))
    subject = payload.get("subject", "")

    if not config.has_resend_key():
        print("[Emailer Error] Neither Gmail SMTP nor RESEND_API_KEY is configured!")
        return False

    headers = {
        "Authorization": f"Bearer {config.resend_api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    try:
        print(f"[Emailer] Submitting POST request to Resend API...")
        response = requests.post(
            RESEND_API_URL,
            headers=headers,
            json=payload,
            timeout=config.request_timeout_seconds,
        )

        if 200 <= response.status_code < 300:
            print(f"[Emailer Success] Intelligence brief successfully delivered via Resend API to {recipient_display}!")
            return True

        if response.status_code == 403 and "only send testing emails to your own email address" in response.text:
            print(f"[Emailer Notice] Resend sandbox restriction for {recipient_display}.")
            if config.has_gmail_smtp():
                return send_email_via_gmail_smtp(
                    report_data=report_data,
                    pdf_path=pdf_path,
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    idempotency_key=idempotency_key,
                )
            return False

        redacted_resp = SensitiveDataRedactor.redact(response.text[:200])
        print(f"[Emailer Error] Resend API rejected delivery (HTTP {response.status_code}): {redacted_resp}")
        return False

    except Exception as e:
        redacted_err = SensitiveDataRedactor.redact(str(e))
        print(f"[Emailer Error] Exception during email dispatch: {redacted_err}")
        return False


def send_failure_alert(
    error_message: str, log_snippet: str = "", recipient_email: Optional[str] = None
) -> bool:
    """Send an automated failure notification with sensitive data redaction."""
    raw_target = recipient_email or config.recipient_email
    target_email = clean_email_address(raw_target.split(",")[0] if "," in raw_target else raw_target)
    if not target_email:
        return False

    # Redact error details before transmitting
    safe_error = SensitiveDataRedactor.redact(error_message)
    safe_snippet = SensitiveDataRedactor.redact(log_snippet)

    subject = "⚠️ Alert: Daily AI & Tech Briefing Pipeline Encountered an Error"
    text_content = f"The daily briefing pipeline failed.\n\nError:\n{safe_error}\n\nLog Details:\n{safe_snippet}"
    html_content = f"""<div style="font-family: sans-serif; line-height: 1.5; color: #1e293b;">
      <h2 style="color: #b91c1c;">⚠️ Daily AI &amp; Tech Briefing Failed</h2>
      <p>The daily briefing pipeline encountered an error during automated execution.</p>
      <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px; margin: 12px 0;">
        <p><strong>Error:</strong> {safe_escape_html(safe_error)}</p>
      </div>
      {f'<pre style="background: #f1f5f9; padding: 10px; font-size: 12px; overflow-x: auto;">{safe_escape_html(safe_snippet)}</pre>' if safe_snippet else ''}
      <p style="font-size: 13px; color: #64748b;">Execution logs have been sanitized of API keys and credentials.</p>
    </div>"""

    if config.has_gmail_smtp():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{config.sender_name} <{config.gmail_user}>"
            msg["To"] = target_email
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            _dispatch_gmail_smtp(msg, [target_email])
            return True
        except Exception:
            pass

    if config.has_resend_key():
        headers = {
            "Authorization": f"Bearer {config.resend_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": SENDER,
            "to": [target_email],
            "subject": subject,
            "text": text_content,
            "html": html_content,
        }
        try:
            resp = requests.post(RESEND_API_URL, headers=headers, json=payload, timeout=15)
            return 200 <= resp.status_code < 300
        except Exception:
            return False

    return False
