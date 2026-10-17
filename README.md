# ⚡ Autonomous AI & Tech Intelligence Briefing Agent

An autonomous intelligence agent that executes a daily 24-hour sweep of the global artificial intelligence and technology landscape, filters exclusively for high-signal updates with zero fluff, formats a structured executive PDF brief, and emails it daily at **07:00 AM PKT (02:00 UTC)** to configured recipients.

---

## 🏛 The 5 Pillars of Intelligence

1. **New Model Launches & Research Breakthroughs:** Frontier LLMs, SLMs, multimodal, open-weights (OpenAI, Anthropic, Google DeepMind, Meta, Mistral, Qwen, DeepSeek). Specs, benchmarks, access tiers.
2. **Developer Tools, Frameworks & SDK Updates:** IDEs, agent architectures, and infra (Cursor, Windsurf, LangChain, vLLM, Hugging Face, Supabase, Docker).
3. **Major Tech & Industry Moves:** Hardware/silicon (NVIDIA, AMD, Groq, Apple), $50M+ funding, major acquisitions, and critical AI policy shifts.
4. **High-Level Practitioner & Thought Leader Insights:** Architectural patterns, benchmarks, and workflows shared by leading researchers and practitioners (Karpathy, Altman, Amodei, LeCun, Willison, Swyx).
5. **Top 3 "Must-Try" Repos / Tools of the Day:** Trending GitHub repositories, viral AI developer tools, and Hugging Face spaces from the last 24 hours.

---

## ⚙️ Architecture & File Structure

```
Updates_Agent/
│
├── .github/workflows/
│   └── daily-agent.yml        # GitHub Actions workflow (Daily 7:00 AM PKT cron + manual dispatch)
│
├── .env.example               # Template for Gemini API and Resend API credentials
├── .env                       # Local secrets (GEMINI_API_KEY, RESEND_API_KEY)
├── requirements.txt           # Python dependencies (google-genai, reportlab, requests, etc.)
├── config.py                  # Dataclass config & environment variable loader
│
├── sources.py                 # Live parallel 24h aggregator (Hacker News, Hugging Face, GitHub)
├── synthesizer.py             # Multi-tier Gemini synthesis engine with JSON mode & offline fallback
├── pdf_generator.py           # Publication-grade ReportLab PDF compiler with XML sanitization
├── emailer.py                 # Resend HTTP API email dispatcher & failure alert notifier
├── main.py                    # Unified CLI entrypoint (--run-now, --dry-run, --verify, --schedule)
│
├── run_agent.bat              # Batch runner used by Windows Task Scheduler
├── setup_task_scheduler.ps1   # PowerShell automation script for local Windows Task Scheduler
│
├── reports/                   # Generated daily PDF briefs (Daily_AI_Tech_Brief_YYYY-MM-DD.pdf)
└── logs/                      # Dual execution logs for each morning run
```

---

## 🔑 Configuration (`.env` & GitHub Secrets)

Copy `.env.example` to `.env` or edit `.env` directly:

```env
# 1. Gemini API Key (Gemini API with Google Search & JSON mode)
# Obtain from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# 2. Email Delivery Option A: Gmail SMTP (Direct delivery to any external recipient)
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password

# 3. Email Delivery Option B: Resend API (HTTP API dispatch)
RESEND_API_KEY=re_your_api_key_here

# 4. Email Recipients (comma-separated or distinct variables)
OWNER_EMAIL=your_email@gmail.com
FORWARD_EMAIL=partner@example.com
RECIPIENT_EMAIL=your_email@gmail.com,partner@example.com

# 5. Schedule Time (24h format, default 07:00 AM)
SCHEDULE_TIME=07:00

# 6. Model Selection (defaults to gemini-3.8-flash, with automatic fallback)
GEMINI_MODEL=gemini-3.8-flash
```

### GitHub Repository Secrets
When hosting on GitHub Actions, add these repository secrets under **Settings > Secrets and variables > Actions**:

| Secret Name | Description | Example / Default |
|-------------|-------------|-------------------|
| `GEMINI_API_KEY` | Google AI Studio Gemini API Key | Required |
| `GMAIL_USER` | (Option A) Gmail Address for SMTP delivery | `your_email@gmail.com` |
| `GMAIL_APP_PASSWORD` | (Option A) Google 16-character App Password | `xxxx xxxx xxxx xxxx` |
| `RESEND_API_KEY` | (Option B) Resend API Key for sending emails | `re_...` |
| `RECIPIENT_EMAIL` | Destination email addresses (comma-separated) | `your_email@gmail.com,partner@example.com` |
| `GEMINI_MODEL` | (Optional) Primary Gemini model | `gemini-3.8-flash` |

*(Note: `GITHUB_TOKEN` is automatically provided by GitHub Actions to grant 1,000 requests/hr for GitHub Trending aggregation).*

---

## 🚀 Usage

### 1. Verify Configuration & Credentials
```powershell
.\.venv\Scripts\python.exe main.py --verify
```

### 2. Run a Dry-Run (Full Pipeline without sending live email)
```powershell
.\.venv\Scripts\python.exe main.py --dry-run
```

### 3. Execute Immediate Live Sweep, Generate PDF, and Send Email
```powershell
.\.venv\Scripts\python.exe main.py --run-now
```
Or double-click `run_agent.bat`.

### 4. Continuous In-Process Python Daemon (Local Alternative)
```powershell
.\.venv\Scripts\python.exe main.py --schedule
```

### 5. Local Windows Task Scheduler (07:00 AM Daily)
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1
```

---

## ⏰ GitHub Actions Automation

The workflow file [`.github/workflows/daily-agent.yml`](.github/workflows/daily-agent.yml) is fully configured:
- **Schedule**: Every day at **07:00 AM PKT** (`02:00 UTC`), cron: `0 2 * * *`.
- **Manual Trigger**: Go to **Actions > Daily AI & Tech Intelligence Brief > Run workflow** (supports dry-run and recipient override).
- **Persistent Storage**: Utilizes `actions/cache@v4` to accumulate prior PDF briefs.
- **Artifact Downloads**: Automatically uploads `reports/*.pdf` and `logs/*.log` to GitHub Actions run artifacts (retained for 30 days).
- **Failure Notification**: If any step encounters an error, an automated failure email alert is immediately sent via Resend.

