"""
NewsAPI integration.

- The API key is read from the NEWSAPI_KEY environment variable only.
  It is never hard-coded and never sent to the frontend.
- If no key is configured, or NewsAPI returns an error/rate-limit, this
  falls back to a small, clearly-labeled OFFLINE sample so the rest of
  the pipeline (NLP -> graph -> timeline) remains demonstrable without
  a key. The fallback is always tagged is_live=False so the frontend
  can show an honest "offline sample data" banner instead of pretending
  it's live.
"""
import requests
from datetime import datetime, timezone

NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"
REQUEST_TIMEOUT = 8  # seconds


class NewsAPIError(Exception):
    pass


def _offline_sample(query: str):
    """A small offline dataset so the feature is demonstrable without a
    live key. Clearly not presented as live data by the caller."""
    query_lc = query.lower()
    samples = [
        {
            "title": f"Fact-check: what we actually know about \"{query}\"",
            "source_name": "Offline Sample Source",
            "url": "https://example.com/fact-check",
            "published_at": "2024-06-01T09:00:00Z",
            "description": f"A widely shared claim about {query} has circulated online; "
                            f"here is what independent fact-checkers found.",
        },
        {
            "title": f"Viral post about {query} draws scrutiny from researchers",
            "source_name": "Offline Sample Source",
            "url": "https://example.com/viral-post",
            "published_at": "2024-06-04T13:30:00Z",
            "description": f"Researchers are examining how a claim about {query} spread "
                            f"rapidly across social platforms over the past week.",
        },
        {
            "title": f"Timeline: how the {query} narrative changed over several months",
            "source_name": "Offline Sample Source",
            "url": "https://example.com/timeline",
            "published_at": "2024-06-10T18:15:00Z",
            "description": f"A look at how successive retellings of the {query} story "
                            f"introduced new, unverified details.",
        },
    ]
    return samples


def search_news(query: str, api_key: str, page_size: int = 10):
    """
    Searches NewsAPI's /v2/everything endpoint for `query`.

    Returns: (articles: list[dict], is_live: bool, warning: str|None)
    Never raises for "no key configured" or "upstream error" — those are
    reported back as a warning + offline fallback so callers can still
    render *something* useful and honest.
    """
    if not api_key:
        return (
            _offline_sample(query),
            False,
            "NEWSAPI_KEY is not configured on the server, so offline sample "
            "articles are shown instead of live results. Get a free key at "
            "https://newsapi.org/register and set NEWSAPI_KEY in backend/.env.",
        )

    try:
        response = requests.get(
            NEWSAPI_ENDPOINT,
            params={
                "q": query,
                "sortBy": "relevancy",
                "pageSize": page_size,
                "language": "en",
                "apiKey": api_key,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        return (
            _offline_sample(query),
            False,
            f"Could not reach NewsAPI ({exc.__class__.__name__}). Showing offline sample data instead.",
        )

    if response.status_code == 401:
        return (
            _offline_sample(query),
            False,
            "NewsAPI rejected the configured API key (401 Unauthorized). "
            "Showing offline sample data instead.",
        )
    if response.status_code == 429:
        return (
            _offline_sample(query),
            False,
            "NewsAPI rate limit reached (429). Showing offline sample data instead.",
        )
    if response.status_code != 200:
        return (
            _offline_sample(query),
            False,
            f"NewsAPI returned an unexpected error (HTTP {response.status_code}). "
            "Showing offline sample data instead.",
        )

    payload = response.json()
    raw_articles = payload.get("articles", [])
    if not raw_articles:
        return [], True, None  # genuinely no results — do NOT fabricate any

    articles = []
    for a in raw_articles:
        articles.append({
            "title": a.get("title") or "(untitled)",
            "source_name": (a.get("source") or {}).get("name") or "Unknown source",
            "url": a.get("url"),
            "published_at": a.get("publishedAt"),
            "description": a.get("description") or "",
        })
    return articles, True, None
