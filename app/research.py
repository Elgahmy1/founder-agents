"""Free web research tools (no API keys, no paid services).

Sources: Hacker News (Algolia API), Reddit search JSON, DuckDuckGo HTML,
and URLs the founder supplies. Every document gets a numbered id so agents
can cite it; anything they cannot cite becomes an ASSUMPTION.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import httpx

UA = {"User-Agent": "founder-agents/0.1 (open-source research bot)"}


@dataclass
class Doc:
    id: str
    url: str
    title: str
    snippet: str
    origin: str


def _clean(s: str, n: int = 400) -> str:
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]


def hn_search(query: str, limit: int = 4) -> list[dict]:
    r = httpx.get(
        "https://hn.algolia.com/api/v1/search",
        params={"query": query, "tags": "(story,comment)", "hitsPerPage": limit},
        headers=UA,
        timeout=15,
    )
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        url = f"https://news.ycombinator.com/item?id={h['objectID']}"
        text = h.get("comment_text") or h.get("story_text") or h.get("title") or ""
        out.append({"url": url, "title": h.get("title") or h.get("story_title") or "HN", "snippet": text, "origin": "hackernews"})
    return out


def reddit_search(query: str, limit: int = 4) -> list[dict]:
    r = httpx.get(
        "https://www.reddit.com/search.json",
        params={"q": query, "limit": limit, "sort": "relevance"},
        headers=UA,
        timeout=15,
    )
    r.raise_for_status()
    out = []
    for c in r.json().get("data", {}).get("children", []):
        d = c["data"]
        out.append({
            "url": "https://www.reddit.com" + d["permalink"],
            "title": d.get("title", ""),
            "snippet": d.get("selftext") or d.get("title", ""),
            "origin": "reddit",
        })
    return out


def ddg_search(query: str, limit: int = 4) -> list[dict]:
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=UA, timeout=15)
    r.raise_for_status()
    out = []
    for m in re.finditer(
        r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
        r.text,
        flags=re.S,
    ):
        href = html.unescape(m.group(1))
        if "uddg=" in href:
            href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if "duckduckgo.com" in href:
            continue
        out.append({"url": href, "title": _clean(m.group(2), 150), "snippet": m.group(3), "origin": "web"})
        if len(out) >= limit:
            break
    return out


class Researcher:
    """Collects documents from free sources. Failures are recorded, not hidden."""

    def __init__(self, enabled: bool = True, max_sources: int = 8):
        self.enabled = enabled
        self.max_sources = max_sources
        self.errors: list[str] = []

    def gather(self, queries: list[str], founder_urls: list[str] | None = None) -> list[Doc]:
        raw: list[dict] = [
            {"url": u, "title": "Founder-supplied source", "snippet": "", "origin": "founder"}
            for u in (founder_urls or [])
        ]
        if self.enabled:
            for q in queries:
                for fn in (hn_search, reddit_search, ddg_search):
                    try:
                        raw.extend(fn(q))
                    except Exception as e:  # network blocked, rate limited, etc.
                        self.errors.append(f"{fn.__name__}('{q}'): {type(e).__name__}")
        seen: set[str] = set()
        docs: list[Doc] = []
        for d in raw:
            if d["url"] in seen or not d["url"].startswith("http"):
                continue
            seen.add(d["url"])
            docs.append(Doc(id=f"S{len(docs) + 1}", url=d["url"], title=_clean(d["title"], 150),
                            snippet=_clean(d["snippet"]), origin=d["origin"]))
            if len(docs) >= self.max_sources:
                break
        return docs


def docs_for_prompt(docs: list[Doc]) -> str:
    if not docs:
        return "NO SOURCES WERE RETRIEVED. Every market claim must be marked as an assumption."
    return "\n".join(f"[{d.id}] ({d.origin}) {d.title} :: {d.snippet}" for d in docs)
