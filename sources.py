import os
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any
import requests


def _fetch_single_hn_keyword(kw: str, cutoff_ts: int) -> List[Dict[str, Any]]:
    """Fetch stories for a single keyword from HN Algolia."""
    url = (
        f"https://hn.algolia.com/api/v1/search_by_date?"
        f"tags=story&numericFilters=created_at_i>{cutoff_ts}&query={kw}&hitsPerPage=15"
    )
    items = []
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            hits = resp.json().get("hits", [])
            for h in hits:
                story_id = h.get("objectID")
                points = h.get("points") or 0
                title = h.get("title", "")
                story_url = h.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                comments = h.get("num_comments") or 0
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
        print(f"[Warning] Failed to fetch HN for query '{kw}': {e}")
    return items


def fetch_hacker_news_stories(lookback_hours: int = 24) -> List[Dict[str, Any]]:
    """Fetch high-signal AI/Tech stories from Hacker News posted in the last 24 hours in parallel."""
    cutoff_ts = int(time.time()) - (lookback_hours * 3600)
    keywords = ["AI", "LLM", "OpenAI", "Anthropic", "Google", "DeepSeek", "Meta", "NVIDIA", "agent", "vLLM"]
    stories = []
    seen_ids = set()

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_kw = {executor.submit(_fetch_single_hn_keyword, kw, cutoff_ts): kw for kw in keywords}
        for future in as_completed(future_to_kw):
            try:
                for item in future.result():
                    sid = item.get("story_id")
                    if sid not in seen_ids:
                        seen_ids.add(sid)
                        stories.append(item)
            except Exception as e:
                kw = future_to_kw[future]
                print(f"[Warning] Error processing HN keyword '{kw}': {e}")

    # Sort by points descending
    stories.sort(key=lambda x: x["points"], reverse=True)
    return stories[:25]


def fetch_huggingface_daily_papers() -> List[Dict[str, Any]]:
    """Fetch top trending AI research breakthroughs from Hugging Face Daily Papers."""
    url = "https://huggingface.co/api/daily_papers"
    papers = []
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data[:15]:
                paper_info = item.get("paper", {})
                title = paper_info.get("title", "")
                summary = paper_info.get("summary", "")
                paper_id = paper_info.get("id", "")
                upvotes = item.get("upvotes", 0)
                paper_url = f"https://huggingface.co/papers/{paper_id}" if paper_id else "https://huggingface.co/papers"
                
                papers.append({
                    "source": "Hugging Face Daily Papers",
                    "title": title,
                    "summary": summary[:200] + "..." if len(summary) > 200 else summary,
                    "url": paper_url,
                    "upvotes": upvotes
                })
        else:
            print(f"[Warning] Hugging Face returned status code {resp.status_code}")
    except Exception as e:
        print(f"[Warning] Failed to fetch Hugging Face papers: {e}")
    return papers


def fetch_github_trending_ai(days_back: int = 3) -> List[Dict[str, Any]]:
    """Fetch top newly created/trending AI repositories on GitHub."""
    date_str = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=topic:ai+created:>{date_str}&sort=stars&order=desc&per_page=15"
    headers = {"User-Agent": "AITechBriefAgent/1.0"}
    
    # Use GitHub token if available (e.g. from GitHub Actions secrets.GITHUB_TOKEN) to avoid 403 rate limits
    gh_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token.strip()}"

    repos = []
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            for r in items:
                repos.append({
                    "source": "GitHub Trending",
                    "name": r.get("full_name"),
                    "description": r.get("description") or "No description provided.",
                    "stars": r.get("stargazers_count", 0),
                    "url": r.get("html_url"),
                    "language": r.get("language") or "Python"
                })
        else:
            print(f"[Warning] GitHub API returned status {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        print(f"[Warning] Failed to fetch GitHub trending: {e}")
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
        "github_trending": gh_repos
    }


def format_raw_intelligence_text(data: Dict[str, Any]) -> str:
    """Format raw intelligence into clean structured text for Gemini synthesis."""
    lines = [f"### LIVE AGGREGATED SIGNALS ({data.get('timestamp')})"]

    lines.append("\n#### Hacker News AI Discussions (Last 24 Hours):")
    for s in data.get("hacker_news", []):
        lines.append(f"- [{s['points']} pts] {s['title']} | URL: {s['url']}")

    lines.append("\n#### Hugging Face Top Daily Research Papers:")
    for p in data.get("hugging_face_papers", [])[:8]:
        lines.append(f"- [{p['upvotes']} upvotes] {p['title']} | URL: {p['url']} | Summary: {p['summary']}")

    lines.append("\n#### GitHub Trending AI Repositories:")
    for r in data.get("github_trending", [])[:8]:
        lines.append(f"- {r['name']} ({r['stars']} stars): {r['description']} | URL: {r['url']}")

    return "\n".join(lines)


if __name__ == "__main__":
    intel = aggregate_raw_intelligence()
    formatted = format_raw_intelligence_text(intel)
    print(formatted[:1000])
