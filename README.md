# ⚡ Autonomous AI & Tech Intelligence Briefing Agent (Zero-Trust & Production-Grade)

An autonomous, resilient, zero-trust intelligence agent that executes a daily 24-hour sweep of the global artificial intelligence and technology landscape, filters exclusively for high-signal updates with zero fluff, formats a structured executive PDF brief, and emails it daily at **07:00 AM PKT (02:00 UTC)** to configured recipients.

---

## 🏛 The 5 Pillars of Intelligence

1. **New Model Launches & Research Breakthroughs:** Frontier LLMs, SLMs, multimodal, open-weights (OpenAI, Anthropic, Google DeepMind, Meta, Mistral, Qwen, DeepSeek). Specs, benchmarks, access tiers.
2. **Developer Tools, Frameworks & SDK Updates:** IDEs, agent architectures, and infra (Cursor, Windsurf, LangChain, vLLM, Hugging Face, Supabase, Docker).
3. **Major Tech & Industry Moves:** Hardware/silicon (NVIDIA, AMD, Groq, Apple), $50M+ funding, major acquisitions, and critical AI policy shifts.
4. **High-Level Practitioner & Thought Leader Insights:** Architectural patterns, benchmarks, and workflows shared by leading researchers and practitioners (Karpathy, Altman, Amodei, LeCun, Willison, Swyx).
5. **Top 3 "Must-Try" Repos / Tools of the Day:** Trending GitHub repositories, viral AI developer tools, and Hugging Face spaces from the last 24 hours.

---

## 🛡️ Zero-Trust Security Architecture

1. **Prompt Injection & Context Isolation (`security/sanitizer.py`)**:
   - Strips invisible Unicode characters, zero-width joiners, and bidirectional overrides.
   - Defangs prompt injection, system overrides, and jailbreak directives from untrusted feeds.
   - Enforces context isolation by delimiting untrusted external data within `<untrusted_context source="...">` XML blocks.
   - Validates model output safety against script injection and command execution attempts.
2. **Output Sanitization & Stored XSS Prevention (`security/sanitizer.py`, `emailer.py`)**:
   - Escapes all dynamic titles, summaries, and headlines into HTML entities before interpolating into email templates.
3. **Filesystem Sandboxing & Path Traversal Guards (`security/sandbox.py`)**:
   - Enforces strict directory allowlists (`reports/`, `logs/`, project root) for all file reads and writes.
   - Sanitizes dynamic filenames to prevent path traversal (`../`) and boundary escapes.
4. **Credential & Secret Redaction (`security/logging_filter.py`)**:
   - Automated regex redactor dynamically masks Gemini API keys, Resend keys, GitHub tokens, Bearer headers, and Gmail app passwords across stdout, stderr, and log files.
5. **Webhook & API Boundary Security (`security/webhook_auth.py`, `security/rate_limiter.py`)**:
   - HMAC-SHA256 signature verification (`X-Hub-Signature-256`).
   - Timestamp replay protection with a 300-second drift tolerance window.
   - Sliding-window rate limiter and Denial of Wallet (DoW) token budget caps.
   - Human-in-the-Loop (HITL) confirmation token gate for high-impact actions.

---

## ⚡ Functional & Agentic Reliability

1. **Deterministic Structured Outputs & Self-Correction (`models/schemas.py`, `synthesizer.py`)**:
   - Strict Pydantic v2 schemas (`IntelligenceBrief`, `PillarItem`, `ToolInputs`).
   - **Self-Correction Feedback Loop**: If an LLM response fails validation, the exact schema validation error is fed back to the model (up to $N=2$ retries) to self-correct before failing.
2. **Resilient Orchestration & Multi-Model Fallbacks (`orchestration/retry_handler.py`)**:
   - Exponential backoff with full jitter for all external HTTP requests and SMTP dispatches.
   - Dynamic model fallback cascade across Gemini models (`gemini-3.8-flash`, `gemini-3-flash-preview`, `gemini-flash-latest`, `gemini-3.5-flash`).
3. **State Checkpointing & Idempotency (`orchestration/state_manager.py`)**:
   - Atomic state saves at key step boundaries (`INIT`, `SYNTHESIZED`, `RENDERED`, `DISPATCHED`).
   - Resumes interrupted workflows without re-running completed steps or wasting LLM tokens.
   - Deterministic SHA-256 idempotency keys prevent duplicate email deliveries to subscribers.
4. **Automated Catch-Up & Ledger Tracking (`orchestration/state_manager.py`)**:
   - Audit ledger records daily dispatch history.
   - Automatically detects missed reporting dates and delivers outstanding reports upon service recovery without duplicating.
5. **Structured JSON Telemetry (`orchestration/telemetry.py`)**:
   - Lifecycle JSONL telemetry logs capturing `trace_id`, `agent_step`, `tool_name`, `latency_ms`, `token_usage`, and `validation_status`.

---

## ⚙️ Project File Structure

```
Updates_Agent/
│
├── security/                  # Zero-Trust Security Module
│   ├── sanitizer.py           # Prompt injection defense, invisible unicode strip, HTML/XML escaping
│   ├── logging_filter.py      # Automated secret & PII redactor and sanitized stream logger
│   ├── sandbox.py             # Path traversal guards, filename sanitizer, HITL gates
│   ├── webhook_auth.py        # HMAC-SHA256 verification, replay protection, CORS headers
│   └── rate_limiter.py        # Sliding-window rate limiter, token budget caps, iteration guards
│
├── models/                    # Pydantic Schemas & State Types
│   └── schemas.py             # IntelligenceBrief, PillarItem, CheckpointState, TelemetryEvent
│
├── orchestration/             # Agentic Resilience & Observability
│   ├── retry_handler.py       # Full-jitter exponential backoff & HTTP transient error classifier
│   ├── state_manager.py       # Resumable atomic checkpointing, catch-up & idempotency ledger
│   └── telemetry.py           # Structured JSONL telemetry recorder
│
├── .github/workflows/
│   └── daily-agent.yml        # GitHub Actions cloud workflow (Daily 7:00 AM PKT cron + catch-up)
│
├── config.py                  # Validated Pydantic configuration loader & timezone handler
├── sources.py                 # Live parallel aggregator with schema validation & prompt isolation
├── synthesizer.py             # Gemini synthesis with self-correction & candidate model fallbacks
├── pdf_generator.py           # Sandboxed publication-grade ReportLab PDF compiler
├── emailer.py                 # Multi-recipient email dispatcher with Gmail SMTP & Resend fallback
├── main.py                    # Unified CLI entrypoint, catch-up runner & webhook listener
├── test_agent.py              # Verification suite covering security, catch-up & reliability
│
├── reports/                   # Generated daily PDF briefs (Daily_AI_Tech_Brief_YYYY-MM-DD.pdf)
└── logs/                      # Redacted daily logs, checkpoints, ledger, and telemetry JSONL files
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

# 5. Schedule & Timezone
SCHEDULE_TIME=07:00
TIMEZONE=Asia/Karachi

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
| `OWNER_EMAIL` | Primary owner recipient email | `your_email@gmail.com` |
| `FORWARD_EMAIL` | Secondary forward recipient email | `partner@example.com` |
| `RECIPIENT_EMAIL` | Comma-separated recipient emails | `your_email@gmail.com,partner@example.com` |
| `TIMEZONE` | Local timezone identifier | `Asia/Karachi` |
| `GEMINI_MODEL` | (Optional) Primary Gemini model | `gemini-3.8-flash` |

*(Note: `GITHUB_TOKEN` is automatically provided by GitHub Actions to grant 1,000 requests/hr for GitHub Trending aggregation and committing daily artifacts).*

---

## 🚀 Usage & Commands

### 1. Verify Configuration & Security Controls
```powershell
.\.venv\Scripts\python.exe main.py --verify
```

### 2. Run Comprehensive Verification Test Suite
```powershell
.\.venv\Scripts\python.exe test_agent.py
```

### 3. Run Dry-Run (Full Pipeline with PDF generation, skip live email)
```powershell
.\.venv\Scripts\python.exe main.py --dry-run
```

### 4. Execute Immediate Live Sweep, Generate PDF, and Send Email
```powershell
.\.venv\Scripts\python.exe main.py --run-now
```

### 5. Execute Automated Catch-Up for Missed Reports
```powershell
.\.venv\Scripts\python.exe main.py --catch-up
```

### 6. Start Local Webhook Listener with HMAC Authentication
```powershell
.\.venv\Scripts\python.exe main.py --webhook-listen --webhook-port 8080
```

### 7. Run Local Daemon Scheduler (07:00 AM Daily)
```powershell
.\.venv\Scripts\python.exe main.py --schedule
```

---

## ⏰ Cloud Background Automation (GitHub Actions)

The workflow file [`.github/workflows/daily-agent.yml`](.github/workflows/daily-agent.yml) provides 100% cloud-hosted automation independent of personal computer status:
- **Cloud-Native**: Executes on GitHub's hosted cloud runners (`ubuntu-latest`) 24/7/365.
- **Timing**: Scheduled for **07:00 AM PKT (02:00 UTC)** with pre-execution window so delivery completes by 07:00 AM.
- **Automated Catch-Up**: Checks for any missed dates from previous cycles upon trigger and recovers them automatically.
- **Deduplication**: SHA-256 idempotency ledger guarantees zero duplicate deliveries.
- **Artifacts & Archival**: Reports and execution logs are uploaded to run artifacts and persisted.
- **Failure Alerting**: Dispatches automated email notifications immediately if any job step encounters an error.
