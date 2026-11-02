"""Hardened multi-source intelligence aggregator with prompt-injection defenses and retry resilience."""

import datetime
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
import requests

from config import config
from models.schemas import (
    FetchHackerNewsInput,
    FetchHuggingFaceInput,
    FetchGitHubTrendingInput,
)
from orchestration.retry_handler import retry_with_backoff
from security.sanitizer import (
    sanitize_untrusted_text,
    wrap_untrusted_context,
)


@retry_with_backoff(max_retries=3, initial_delay=1.0, max_delay=10.0)
def _http_get_with_retry(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> requests.Response:
    """Execute HTTP GET with exponential backoff and explicit timeout boundary."""
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def _fetch_single_hn_keyword(kw: str, cutoff_ts: int) -> List[Dict[str, Any]]:
    """Fetch stories for a single keyword from HN Algolia with input sanitization."""
    safe_kw = sanitize_untrusted_text(kw, max_length=50)
    url = (
        f"https://hn.algolia.com/api/v1/search_by_date?"
        f"tags=story&numericFilters=created_at_i>{cutoff_ts}&query={safe_kw}&hitsPerPage=15"
    )
    items = []
    try:
        resp = _http_get_with_retry(url, timeout=config.request_timeout_seconds)
        hits = resp.json().get("hits", [])
        for h in hits:
            story_id = str(h.get("objectID", ""))
            points = int(h.get("points") or 0)
            raw_title = h.get("title", "")
            title = sanitize_untrusted_text(raw_title, max_length=250)
            raw_url = h.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            story_url = sanitize_untrusted_text(raw_url, max_length=500)
            comments = int(h.get("num_comments") or 0)
            if points >= 3 or comments >= 3:
                items.append({
                    "story_id": story_id,
                    "source": "Hacker News",
                    "title": title,
                    "url": story_url,
                    "points": points,
                    "comments": comments,
                    "created_at": h.get("created_at"),
                })
    except Exception as e:
        # Avoid logging full URL with queries if they might carry sensitive terms
        print(f"[Warning] Resilient HN fetch warning for '{safe_kw}': {type(e).__name__}")
    return items


def fetch_hacker_news_stories(lookback_hours: int = 24, keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Fetch high-signal AI/Tech stories from Hacker News posted in the last N hours in parallel."""
    # Enforce strict schema validation on tool parameters
    tool_input = FetchHackerNewsInput(lookback_hours=lookback_hours, keywords=keywords)
    
    cutoff_ts = int(time.time()) - (tool_input.lookback_hours * 3600)
    query_keywords = tool_input.keywords or [
        "AI", "LLM", "OpenAI", "Anthropic", "Google", "DeepSeek", "Meta", "NVIDIA", "agent", "vLLM"
    ]
    stories = []
    seen_ids = set()

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_kw = {
            executor.submit(_fetch_single_hn_keyword, kw, cutoff_ts): kw for kw in query_keywords
        }
        for future in as_completed(future_to_kw):
            try:
                for item in future.result():
                    sid = item.get("story_id")
                    if sid not in seen_ids:
                        seen_ids.add(sid)
                        stories.append(item)
            except Exception as e:
                kw = future_to_kw[future]
                print(f"[Warning] Error processing HN keyword '{kw}': {type(e).__name__}")

    # Sort by points descending
    stories.sort(key=lambda x: x["points"], reverse=True)
    return stories[:25]


def fetch_huggingface_daily_papers(limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch top trending AI research breakthroughs from Hugging Face Daily Papers."""
    tool_input = FetchHuggingFaceInput(limit=limit)
    url = "https://huggingface.co/api/daily_papers"
    papers = []
    try:
        resp = _http_get_with_retry(url, timeout=config.request_timeout_seconds)
        data = resp.json()
        for item in data[: tool_input.limit]:
            paper_info = item.get("paper", {})
            title = sanitize_untrusted_text(paper_info.get("title", ""), max_length=250)
            raw_summary = paper_info.get("summary", "")
            summary = sanitize_untrusted_text(raw_summary, max_length=400)
            paper_id = sanitize_untrusted_text(paper_info.get("id", ""), max_length=100)
            upvotes = int(item.get("upvotes", 0))
            paper_url = f"https://huggingface.co/papers/{paper_id}" if paper_id else "https://huggingface.co/papers"

            papers.append({
                "source": "Hugging Face Daily Papers",
                "title": title,
                "summary": summary[:200] + "..." if len(summary) > 200 else summary,
                "url": paper_url,
                "upvotes": upvotes,
            })
    except Exception as e:
        print(f"[Warning] Resilient Hugging Face fetch warning: {type(e).__name__}")
    return papers


def fetch_github_trending_ai(days_back: int = 3, limit: int = 15) -> List[Dict[str, Any]]:
    """Fetch top newly created/trending AI repositories on GitHub."""
    tool_input = FetchGitHubTrendingInput(days_back=days_back, limit=limit)
    date_str = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=tool_input.days_back)).strftime(
        "%Y-%m-%d"
    )
    url = f"https://api.github.com/search/repositories?q=topic:ai+created:>{date_str}&sort=stars&order=desc&per_page={tool_input.limit}"
    headers = {"User-Agent": "AITechBriefAgent/2.0", "Accept": "application/vnd.github.v3+json"}

    # Use GitHub token if available (e.g. from GitHub Actions secrets.GITHUB_TOKEN) to avoid 403 rate limits
    gh_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token.strip()}"

    repos = []
    try:
        resp = _http_get_with_retry(url, headers=headers, timeout=config.request_timeout_seconds)
        items = resp.json().get("items", [])
        for r in items:
            repo_name = sanitize_untrusted_text(r.get("full_name", ""), max_length=150)
            desc = sanitize_untrusted_text(r.get("description") or "No description provided.", max_length=350)
            stars = int(r.get("stargazers_count", 0))
            html_url = sanitize_untrusted_text(r.get("html_url", ""), max_length=500)
            language = sanitize_untrusted_text(r.get("language") or "Python", max_length=50)

            repos.append({
                "source": "GitHub Trending",
                "name": repo_name,
                "description": desc,
                "stars": stars,
                "url": html_url,
                "language": language,
            })
    except Exception as e:
        print(f"[Warning] Resilient GitHub fetch warning: {type(e).__name__}")
    return repos


def aggregate_raw_intelligence() -> Dict[str, Any]:
    """Gather live data across all real-time endpoints."""
    hn_stories = fetch_hacker_news_stories(lookback_hours=24)
    hf_papers = fetch_huggingface_daily_papers()
    gh_repos = fetch_github_trending_ai(days_back=2)

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hacker_news": hn_stories,
        "hugging_face_papers": hf_papers,
        "github_trending": gh_repos,
    }


def format_raw_intelligence_text(data: Dict[str, Any]) -> str:
    """Format raw intelligence into strictly delimited context blocks for LLM synthesis."""
    lines = [f"### LIVE AGGREGATED SIGNALS ({data.get('timestamp')})"]

    # Hacker News
    hn_block = []
    for s in data.get("hacker_news", []):
        hn_block.append(f"- [{s.get('points', 0)} pts] {s.get('title', '')} | URL: {s.get('url', '')}")
    lines.append("\n#### Hacker News AI Discussions (Last 24 Hours):")
    lines.append(wrap_untrusted_context("\n".join(hn_block), source_label="hacker_news"))

    # Hugging Face
    hf_block = []
    for p in data.get("hugging_face_papers", [])[:8]:
        hf_block.append(
            f"- [{p.get('upvotes', 0)} upvotes] {p.get('title', '')} | URL: {p.get('url', '')} | Summary: {p.get('summary', '')}"
        )
    lines.append("\n#### Hugging Face Top Daily Research Papers:")
    lines.append(wrap_untrusted_context("\n".join(hf_block), source_label="hugging_face_papers"))

    # GitHub
    gh_block = []
    for r in data.get("github_trending", [])[:8]:
        gh_block.append(
            f"- {r.get('name', '')} ({r.get('stars', 0)} stars, {r.get('language', '')}): {r.get('description', '')} | URL: {r.get('url', '')}"
        )
    lines.append("\n#### GitHub Trending AI Repositories:")
    lines.append(wrap_untrusted_context("\n".join(gh_block), source_label="github_trending"))

    return "\n".join(lines)


if __name__ == "__main__":
    intel = aggregate_raw_intelligence()
    formatted = format_raw_intelligence_text(intel)
    print(formatted[:1000])
