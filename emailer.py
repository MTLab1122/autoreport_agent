"""Email dispatch module for the Daily AI & Tech Intelligence Brief using the Resend HTTP API."""

import os
import base64
import requests
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# Constants for Resend API
RESEND_API_URL = "https://api.resend.com/emails"
SENDER = "AI Tech Agent <onboarding@resend.dev>"
RECIPIENTS: List[str] = [os.getenv("RECIPIENT_EMAIL", "muhammadtalhpro1@gmail.com")]


def compose_email_payload(report_data: Dict[str, Any], pdf_path: Path) -> Dict[str, Any]:
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

Full breakdown is in the attached PDF.
"""

    body_html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #0f172a; margin-bottom: 8px;">⚡ Daily AI &amp; Tech Intelligence Brief</h2>
  <p style="color: #64748b; font-size: 14px; margin-top: 0;">Date: {date_str}</p>
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

    payload: Dict[str, Any] = {
        "from": SENDER,
        "to": [os.getenv("RECIPIENT_EMAIL", "muhammadtalhpro1@gmail.com")],
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
    else:
        print(f"[Emailer Warning] PDF attachment not found at {pdf_path}")

    if attachments:
        payload["attachments"] = attachments

    return payload


# Backwards compatibility alias
compose_email = compose_email_payload


def send_daily_brief_email(report_data: Dict[str, Any], pdf_path: Path) -> bool:
    """Dispatch briefing email via the Resend HTTP API.

    Reads RESEND_API_KEY from environment, attaches base64-encoded PDF,
    and logs exact HTTP responses upon failure or success.
    """
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()

    payload = compose_email_payload(report_data, pdf_path)
    recipient_display = ", ".join(payload.get("to", []))
    subject = payload.get("subject", "")

    print(f"\n[Emailer] Prepared dispatch via Resend HTTP API:")
    print(f"  • From: {payload.get('from')}")
    print(f"  • To: {recipient_display}")
    print(f"  • Subject: {subject}")
    if "attachments" in payload and payload["attachments"]:
        att_name = payload["attachments"][0].get("filename")
        print(f"  • Attachment: {att_name}")

    if not resend_api_key:
        print("\n" + "=" * 70)
        print("[Emailer Error] RESEND_API_KEY is not configured!")
        print("Please set the RESEND_API_KEY environment variable in your .env file:")
        print("  RESEND_API_KEY=re_your_api_key_here")
        print("You can obtain an API key at: https://resend.com/api-keys")
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
        elif response.status_code == 403 and "only send testing emails to your own email address" in response.text:
            print("\n" + "=" * 70)
            print(f"[Emailer Sandbox Notice] Resend test domain restricted delivery to your registered account.")
            print(f"  • Target: {recipient_display}")
            print(f"  • Response Body: {response.text}")
            fallback_target = ["muhammadtalhapro1@gmail.com"]
            print(f"[Emailer] Attempting delivery to registered Resend account: {fallback_target}...")
            payload_fallback = dict(payload)
            payload_fallback["to"] = fallback_target
            fb_response = requests.post(RESEND_API_URL, headers=headers, json=payload_fallback, timeout=30)
            if 200 <= fb_response.status_code < 300:
                resp_data = fb_response.json() if "application/json" in fb_response.headers.get("Content-Type", "") else {}
                resend_id = resp_data.get("id", "N/A")
                print(f"[Emailer Success] Intelligence brief delivered to registered account inbox!")
                print(f"  • Resend ID: {resend_id}")
                print(f"  • Recipient: {fallback_target}")
                print("=" * 70 + "\n")
                return True
            else:
                print(f"[Emailer Error] Delivery to fallback failed: {fb_response.status_code} - {fb_response.text}")
                print("=" * 70 + "\n")
                return False
        else:
            print("\n" + "=" * 70)
            print(f"[Emailer Error] Resend API rejected email delivery!")
            print(f"  • HTTP Status: {response.status_code}")
            print(f"  • Reason: {response.reason}")
            print(f"  • Response Body: {response.text}")
            print("=" * 70 + "\n")
            return False

    except requests.exceptions.RequestException as e:
        print("\n" + "=" * 70)
        print(f"[Emailer Error] Network / HTTP request exception while contacting Resend API: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"  • HTTP Status: {e.response.status_code}")
            print(f"  • Response Body: {e.response.text}")
        print("=" * 70 + "\n")
        return False
    except Exception as e:
        print(f"[Emailer Error] Unexpected error during email dispatch: {e}")
        return False
