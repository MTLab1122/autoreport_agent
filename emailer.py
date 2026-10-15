"""Email dispatch module for the Daily AI & Tech Intelligence Brief using the Resend HTTP API."""

import os
import base64
import requests
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from config import config

# Constants for Resend API
RESEND_API_URL = "https://api.resend.com/emails"
SENDER = "AI Tech Agent <onboarding@resend.dev>"


def compose_email_payload(
    report_data: Dict[str, Any], pdf_path: Path = None, recipient_email: str = None
) -> Dict[str, Any]:
    """Construct the Resend email JSON payload with briefing highlights and PDF attachment."""
    date_str = report_data.get("date", "Today")
    top_headline = report_data.get("top_headline", "Frontier AI Releases & Breakthroughs")
    highlights = report_data.get("highlights", [])

    subject = f"⚡ Daily AI & Tech Brief — {date_str}: {top_headline}"

    h1 = highlights[0] if len(highlights) > 0 else "Frontier model launches and industry shifts."
    h2 = highlights[1] if len(highlights) > 1 else "Developer frameworks and tooling optimizations."
    h3 = highlights[2] if len(highlights) > 2 else "High-signal practitioner insights and trending repositories."

    body_text = f"""Hi Muhammad,

Attached is your precision AI & Tech Intelligence Brief for {date_str}.

Top 3 Highlights Today:
1. {h1}
2. {h2}
3. {h3}

Full breakdown across all 5 intelligence pillars is available in the attached publication-grade PDF.
"""

    body_html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #0f172a; margin-bottom: 8px;">⚡ Daily AI &amp; Tech Intelligence Brief</h2>
  <p style="color: #64748b; font-size: 14px; margin-top: 0;">Date: {date_str} &bull; Delivery: 07:00 AM</p>
  <p>Hi Muhammad,</p>
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

    target_email = (recipient_email or config.recipient_email).strip()

    payload: Dict[str, Any] = {
        "from": SENDER,
        "to": [target_email],
        "subject": subject,
        "text": body_text,
        "html": body_html,
    }

    # Attach the generated PDF encoded as Base64 string
    attachments = []
    pdf_path_obj = Path(pdf_path) if pdf_path else None
    if pdf_path_obj and pdf_path_obj.exists():
        with open(pdf_path_obj, "rb") as f:
            pdf_bytes = f.read()
        encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        attachments.append({
            "filename": pdf_path_obj.name,
            "content": encoded_pdf,
        })
    elif pdf_path:
        print(f"[Emailer Warning] PDF attachment not found at {pdf_path}")

    if attachments:
        payload["attachments"] = attachments

    return payload


# Backwards compatibility alias
compose_email = compose_email_payload


def send_daily_brief_email(
    report_data: Dict[str, Any], pdf_path: Path = None, recipient_email: str = None
) -> bool:
    """Dispatch briefing email via the Resend HTTP API."""
    resend_api_key = config.resend_api_key

    payload = compose_email_payload(report_data, pdf_path, recipient_email)
    recipient_display = ", ".join(payload.get("to", []))
    subject = payload.get("subject", "")

    print(f"\n[Emailer] Prepared dispatch via Resend HTTP API:")
    print(f"  • From: {payload.get('from')}")
    print(f"  • To: {recipient_display}")
    print(f"  • Subject: {subject}")
    if "attachments" in payload and payload["attachments"]:
        att_name = payload["attachments"][0].get("filename")
        print(f"  • Attachment: {att_name}")

    if not config.has_resend_key():
        print("\n" + "=" * 70)
        print("[Emailer Error] RESEND_API_KEY is not configured or invalid!")
        print("Please configure RESEND_API_KEY in your .env or GitHub Secrets.")
        print("=" * 70 + "\n")
        return False

    headers = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
    }

    try:
        print(f"[Emailer] Submitting POST request to {RESEND_API_URL}...")
        response = requests.post(
            RESEND_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if 200 <= response.status_code < 300:
            resp_data = response.json() if "application/json" in response.headers.get("Content-Type", "") else {}
            resend_id = resp_data.get("id", "N/A")
            print(f"[Emailer Success] Intelligence brief successfully delivered via Resend API!")
            print(f"  • Resend ID: {resend_id}")
            print(f"  • Recipient: {recipient_display}")
            return True

        # Handle Resend sandbox restriction (when using onboarding@resend.dev with unverified domain)
        if response.status_code == 403 and "only send testing emails to your own email address" in response.text:
            print(f"[Emailer Sandbox Notice] Resend sandbox restriction: {response.text}")
            fallback_target = "muhammadtalhapro1@gmail.com"
            if recipient_display != fallback_target:
                print(f"[Emailer] Retrying dispatch to verified account address ({fallback_target})...")
                payload_fallback = dict(payload)
                payload_fallback["to"] = [fallback_target]
                fb_response = requests.post(RESEND_API_URL, headers=headers, json=payload_fallback, timeout=30)
                if 200 <= fb_response.status_code < 300:
                    resp_data = fb_response.json() if "application/json" in fb_response.headers.get("Content-Type", "") else {}
                    resend_id = resp_data.get("id", "N/A")
                    print(f"[Emailer Success] Brief delivered to verified account inbox ({fallback_target})! Resend ID: {resend_id}")
                    return True
                else:
                    print(f"[Emailer Error] Fallback dispatch failed: {fb_response.status_code} - {fb_response.text}")
                    return False

        print("\n" + "=" * 70)
        print(f"[Emailer Error] Resend API rejected email delivery!")
        print(f"  • HTTP Status: {response.status_code}")
        print(f"  • Reason: {response.reason}")
        print(f"  • Response Body: {response.text}")
        print("=" * 70 + "\n")
        return False

    except requests.exceptions.RequestException as e:
        print(f"[Emailer Error] Network / HTTP request exception while contacting Resend API: {e}")
        return False
    except Exception as e:
        print(f"[Emailer Error] Unexpected error during email dispatch: {e}")
        return False


def send_failure_alert(
    error_message: str, log_snippet: str = "", recipient_email: str = None
) -> bool:
    """Send an automated failure notification when the briefing pipeline fails."""
    if not config.has_resend_key():
        return False

    target_email = (recipient_email or config.recipient_email).strip()
    headers = {
        "Authorization": f"Bearer {config.resend_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "from": SENDER,
        "to": [target_email],
        "subject": "⚠️ Alert: Daily AI & Tech Briefing Pipeline Encountered an Error",
        "text": f"The daily briefing pipeline failed.\n\nError:\n{error_message}\n\nLog Details:\n{log_snippet}",
        "html": f"""<div style="font-family: sans-serif; line-height: 1.5; color: #1e293b;">
          <h2 style="color: #b91c1c;">⚠️ Daily AI &amp; Tech Briefing Failed</h2>
          <p>The daily briefing pipeline encountered an error during automated execution.</p>
          <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px; margin: 12px 0;">
            <p><strong>Error:</strong> {error_message}</p>
          </div>
          {f'<pre style="background: #f1f5f9; padding: 10px; font-size: 12px; overflow-x: auto;">{log_snippet}</pre>' if log_snippet else ''}
          <p style="font-size: 13px; color: #64748b;">Check the GitHub Actions artifacts and logs for full stack traces.</p>
        </div>""",
    }

    try:
        resp = requests.post(RESEND_API_URL, headers=headers, json=payload, timeout=15)
        return 200 <= resp.status_code < 300
    except Exception:
        return False
