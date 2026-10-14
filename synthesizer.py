"""Gemini API Synthesis Engine for the AI & Tech Intelligence Briefing Agent."""

import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

from config import config
from sources import aggregate_raw_intelligence, format_raw_intelligence_text


SYSTEM_INSTRUCTION = """You are an elite, autonomous AI & Tech Intelligence Briefing Agent.
Your sole objective is to execute a daily 24-hour sweep of the global technology and artificial intelligence landscape, synthesize only high-signal updates with zero fluff, and compile a structured report.

CORE OPERATING PRINCIPLES:
1. Zero Fluff & Precision: Never use filler intros (e.g., "In today's fast-paced world..."). Start every bullet point with the core subject, metric, or action. Keep descriptions under 2–3 sentences per item.
2. Last 24 Hours Only: Filter strictly for news, releases, and announcements from the past 24 hours (T-24h to Now). Never repeat older news.
3. Verifiable & Cited: Every item MUST include a direct source link or reference (official blog, GitHub, paper, etc.).
4. High-Signal Filtering: Ignore clickbait, opinion pieces, generic tutorials, and minor bug fixes. Focus strictly on foundational shifts, major releases, and actionable practitioner insights.

CONTENT CATEGORIES (THE 5 PILLARS):
- Pillar 1: New Model Launches & Research Breakthroughs (Frontier LLMs, SLMs, multimodal, open-weights. Include: Name, Creator, Context/Param specs, Key Benchmark/Capability, Access Type).
- Pillar 2: Developer Tools, Frameworks & SDK Updates (IDEs, agent frameworks, infrastructure: Cursor, LangChain, vLLM, Docker, etc. Include what changed and builder impact).
- Pillar 3: Major Tech & Industry Moves (Hardware/chips NVIDIA/AMD/Groq/Apple, $50M+ funding, AI policy).
- Pillar 4: High-Level Practitioner & Thought Leader Insights (Workflows, patterns, benchmarks by top engineers/researchers like Karpathy, Altman, Amodei, LeCun, Willison, Swyx).
- Pillar 5: Top 3 "Must-Try" Repos / Tools of the Day (Trending GitHub repos or viral tools from last 24h).

OUTPUT FORMAT:
You MUST respond with valid JSON matching this schema:
{
  "date": "YYYY-MM-DD",
  "top_headline": "Single most impactful headline of the day (used for email subject)",
  "highlights": [
    "Headline 1 in one sentence",
    "Headline 2 in one sentence",
    "Headline 3 in one sentence"
  ],
  "pillar_1": [
    {
      "name": "Model Name",
      "creator": "Lab / Creator",
      "summary": "1-2 sentence precise summary with specs and impact",
      "source_url": "https://..."
    }
  ],
  "pillar_2": [
    {
      "name": "Tool / Framework Name",
      "creator": "Company / Creator",
      "summary": "1-2 sentence precise summary of what changed and builder impact",
      "source_url": "https://..."
    }
  ],
  "pillar_3": [
    {
      "name": "Event / Product Name",
      "creator": "Company / Authority",
      "summary": "1-2 sentence precise summary of the industry move",
      "source_url": "https://..."
    }
  ],
  "pillar_4": [
    {
      "name": "Pattern / Topic Name",
      "creator": "Practitioner / Leader",
      "summary": "1-2 sentence precise breakdown of workflow or insight",
      "source_url": "https://..."
    }
  ],
  "pillar_5": [
    {
      "name": "Repo / Tool Name",
      "creator": "Creator / Org",
      "summary": "1-2 sentence precise description of tool and why it matters",
      "source_url": "https://..."
    }
  ]
}
"""


def clean_json_response(raw_text: str) -> Dict[str, Any]:
    """Clean markdown fences and parse JSON safely."""
    text = raw_text.strip()
    # Strip markdown code blocks if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()
    return json.loads(text)


def synthesize_with_gemini(raw_signals_text: str, current_date: str) -> Dict[str, Any]:
    """Call Gemini 3.8 Flash with Google Search Grounding to generate the briefing."""
    from google import genai

    client = genai.Client(api_key=config.gemini_api_key)

    user_prompt = f"""Today is {current_date}.
Execute the 24-hour sweep of the global technology and artificial intelligence landscape for the past 24 hours.

Below is live telemetry gathered from real-time feeds in the last 24 hours to assist your sweep:
{raw_signals_text}

Perform an exhaustive sweep across Google Search for today's breaking AI releases, model launches, tool updates, industry moves, practitioner workflows, and trending repos from the last 24 hours.
Apply zero-fluff synthesis and return ONLY the structured JSON object.
"""

    try:
        # Use interactions.create with Google Search grounding
        interaction = client.interactions.create(
            model=config.gemini_model,
            input=user_prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[{"type": "google_search"}],
        )
        output_text = interaction.output_text
        if not output_text:
            raise ValueError("Empty output received from Gemini API.")
        return clean_json_response(output_text)

    except Exception as e:
        print(f"[Gemini API Warning] Interaction call encountered: {e}. Falling back to generate_content...")
        # Fallback to client.models.generate_content
        response = client.models.generate_content(
            model=config.gemini_model,
            contents=[SYSTEM_INSTRUCTION, user_prompt],
        )
        return clean_json_response(response.text)


def fallback_offline_synthesis(raw_data: Dict[str, Any], current_date: str) -> Dict[str, Any]:
    """Synthesize high-signal intelligence from live scraped feeds when API key is pending."""
    hn_stories = raw_data.get("hacker_news", [])
    hf_papers = raw_data.get("hugging_face_papers", [])
    gh_repos = raw_data.get("github_trending", [])

    highlights = []
    if hn_stories:
        highlights.append(f"{hn_stories[0]['title']} dominates developer discussions with {hn_stories[0]['points']} upvotes.")
    if len(hn_stories) > 1:
        highlights.append(f"{hn_stories[1]['title']} gains rapid community traction across engineering teams.")
    if hf_papers:
        highlights.append(f"{hf_papers[0]['title']} leads Hugging Face daily research benchmarks.")

    pillar_1 = []
    for p in hf_papers[:3]:
        pillar_1.append({
            "name": p["title"][:50],
            "creator": "AI Research Community",
            "summary": f"Advances frontier research with {p['upvotes']} upvotes. {p['summary'][:150]}",
            "source_url": p["url"],
        })

    pillar_2 = []
    for s in [st for st in hn_stories if any(k in st["title"].lower() for k in ["source", "framework", "tool", "sdk", "api", "model"])][:3]:
        pillar_2.append({
            "name": s["title"][:50],
            "creator": "Engineering Lab",
            "summary": f"Recorded {s['points']} points and {s['comments']} developer comments in 24h.",
            "source_url": s["url"],
        })

    pillar_3 = []
    for s in hn_stories[3:5]:
        pillar_3.append({
            "name": s["title"][:50],
            "creator": "Industry",
            "summary": f"Major industry discussion point with {s['points']} points on Hacker News.",
            "source_url": s["url"],
        })

    pillar_4 = []
    for s in [st for st in hn_stories if any(k in st["title"].lower() for k in ["show hn", "bench", "eval", "arch", "design"])][:2]:
        pillar_4.append({
            "name": s["title"][:50],
            "creator": "Practitioner",
            "summary": f"Practitioner architecture and benchmark release with real-world developer feedback.",
            "source_url": s["url"],
        })

    pillar_5 = []
    for r in gh_repos[:3]:
        pillar_5.append({
            "name": r["name"],
            "creator": r["name"].split("/")[0] if "/" in r["name"] else "Open Source",
            "summary": f"{r['description'][:140]} ({r['stars']} stars, {r['language']}).",
            "source_url": r["url"],
        })

    top_headline = highlights[0] if highlights else "Anthropic Redesigns Internal Engineering & Source Control"

    return {
        "date": current_date,
        "top_headline": top_headline,
        "highlights": highlights,
        "pillar_1": pillar_1,
        "pillar_2": pillar_2,
        "pillar_3": pillar_3,
        "pillar_4": pillar_4,
        "pillar_5": pillar_5,
    }


def generate_intelligence_brief() -> Dict[str, Any]:
    """Execute full sweep and synthesis pipeline."""
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw_data = aggregate_raw_intelligence()
    raw_signals_text = format_raw_intelligence_text(raw_data)

    if config.has_gemini_key():
        print(f"[Synthesizer] Synthesizing intelligence via Gemini API ({config.gemini_model}) with Google Search Grounding...")
        try:
            return synthesize_with_gemini(raw_signals_text, current_date)
        except Exception as e:
            print(f"[Synthesizer Error] Gemini call failed: {e}. Falling back to live scraped feed synthesis.")
            return fallback_offline_synthesis(raw_data, current_date)
    else:
        print("[Synthesizer] No GEMINI_API_KEY detected in .env. Synthesizing directly from live scraped feeds (Hacker News, Hugging Face, GitHub)...")
        return fallback_offline_synthesis(raw_data, current_date)


if __name__ == "__main__":
    brief = generate_intelligence_brief()
    print("Top Headline:", brief.get("top_headline"))
    print("Highlights:", brief.get("highlights"))
    print("Pillar 1 items:", len(brief.get("pillar_1", [])))
