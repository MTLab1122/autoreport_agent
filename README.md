# ⚡ Autonomous AI & Tech Intelligence Briefing Agent

An autonomous intelligence agent that executes a daily 24-hour sweep of the global artificial intelligence and technology landscape, filters exclusively for high-signal updates with zero fluff, formats a structured executive PDF brief, and emails it daily at **07:00 AM** to `muhammadtalhpro1@gmail.com`.

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
c:\Users\muham\Desktop\Updates_Agent\
│
├── .env.example               # Template for Gemini API and Resend API credentials
├── .env                       # Local secrets (GEMINI_API_KEY, RESEND_API_KEY)
├── requirements.txt           # Python dependencies (google-genai, reportlab, requests, etc.)
├── config.py                  # Dataclass config & environment variable loader
│
├── sources.py                 # Live 24-hour aggregator (Hacker News, Hugging Face, GitHub)
├── synthesizer.py             # Gemini 3.8 Flash + Google Search Grounding engine
├── pdf_generator.py           # Publication-grade ReportLab PDF compiler
├── emailer.py                 # Resend HTTP API email dispatcher with base64 PDF attachment
├── main.py                    # Unified CLI entrypoint (--run-now, --schedule)
│
├── run_agent.bat              # Batch runner used by Windows Task Scheduler
├── setup_task_scheduler.ps1   # PowerShell automation script for Task Scheduler
│
├── reports/                   # Generated daily PDF briefs
│   └── AI_Tech_Brief_YYYY-MM-DD.pdf
└── logs/                      # Execution logs for scheduled morning runs
```

---

## 🔑 Configuration (`.env`)

Copy `.env.example` to `.env` or edit `.env` directly:

```env
# 1. Gemini API Key (Gemini 3.8 Flash with Google Search Grounding)
# Get a key from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here

# 2. Resend API Key (Required for email delivery via Resend HTTP API)
# Get your API key from: https://resend.com/api-keys
RESEND_API_KEY=re_your_api_key_here

# 3. Schedule Time (24h format, default 07:00 AM)
SCHEDULE_TIME=07:00
```

---

## 🚀 Usage

### 1. Execute an Immediate Sweep & Generate PDF
Run the complete pipeline right now:
```powershell
.\.venv\Scripts\python.exe main.py --run-now
```
Or double-click `run_agent.bat`.

### 2. Daily Autonomous Schedule (07:00 AM)
- **Windows Task Scheduler (Active & Recommended):** The task `AITechIntelligenceBrief` is already registered and configured to execute daily at `07:00 AM` in the background.
  To re-register or adjust:
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\setup_task_scheduler.ps1
  ```
- **In-Process Python Daemon (Alternative):**
  ```powershell
  .\.venv\Scripts\python.exe main.py --schedule
  ```

---

## 📄 Sample Generated Brief
The report compiler strictly satisfies all styling rules:
- Clean 1–2 page executive layout with subtle borders and dividers.
- Executive summary callout box with the top 3 headlines of the day.
- Every item formatted as `**[Product/Model Name] ([Company/Creator]):** [Summary]. (Source)` with clickable citations.
- Dynamic page numbering (`Page X of Y`) and running header/footer.
