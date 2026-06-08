"""Web Search & Document Fetch for SPEACE AGI Team agents.

Provides two main capabilities:
- WebSearcher: query DuckDuckGo (HTML endpoint) and return ranked results
- DocumentFetcher: fetch a URL and extract readable text/metadata

Both are designed to be dependency-light (only `requests` + stdlib), and
fall back gracefully if a request fails. Results are cached in
`data/agi_team/web_cache.jsonl` for reproducibility.

This module is the foundation for letting SPEACE agents autonomously
search the web for technical and scientific documents to improve
themselves — without requiring any third-party search API key.
"""

import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests


# ── Cache ───────────────────────────────────────────────────────────────
CACHE_PATH = Path("data/agi_team/web_cache.jsonl")
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Simple in-memory cache (URL → result) to avoid repeated fetches in one session
_memory_cache: Dict[str, Dict[str, Any]] = {}


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    if key in _memory_cache:
        return _memory_cache[key]
    if not CACHE_PATH.exists():
        return None
    try:
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("key") == key:
                        _memory_cache[key] = entry
                        return entry
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None
    return None


def _cache_put(key: str, value: Dict[str, Any]):
    _memory_cache[key] = value
    try:
        with CACHE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, **value}, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── HTML helpers (no BS4 dependency) ──────────────────────────────────
class _TextExtractor(HTMLParser):
    """Pull visible text out of HTML, ignoring scripts/styles."""

    SKIP_TAGS = {"script", "style", "noscript", "iframe", "svg", "header", "footer", "nav"}

    def __init__(self):
        super().__init__()
        self._buf: List[str] = []
        self._skip_depth = 0
        self._title_parts: List[str] = []
        self._in_title = False
        self._meta_desc: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta" and attr_dict.get("name", "").lower() == "description":
            self._meta_desc = attr_dict.get("content", "").strip()

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        else:
            self._buf.append(text)

    def result(self) -> Dict[str, str]:
        body = " ".join(self._buf)
        body = re.sub(r"\s+", " ", body).strip()
        title = " ".join(self._title_parts).strip()
        return {
            "title": title,
            "description": self._meta_desc or "",
            "text": body,
        }


def _extract_text(html: str) -> Dict[str, str]:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    return parser.result()


# ── DuckDuckGo HTML search ────────────────────────────────────────────
DDG_URL = "https://html.duckduckgo.com/html/"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_ddg_results(html: str, max_results: int) -> List[Dict[str, str]]:
    """Extract {title, url, snippet} tuples from DDG HTML page."""
    results: List[Dict[str, str]] = []

    # Find each <div class="result ..."> block and parse its inner content.
    # The result block contains:
    #   <h2 class="result__title"><a class="result__a" href="URL">TITLE</a></h2>
    #   <a class="result__snippet" href="URL">SNIPPET</a>
    block_re = re.compile(
        r'<div[^>]+class="result\s+results_links[^"]*"[^>]*>(.*?)(?=<div[^>]+class="result\s+results_links|</div>\s*</div>\s*<div[^>]+class="(?:nav|serp))',
        re.IGNORECASE | re.DOTALL,
    )

    def _extract_block(block: str) -> Optional[Dict[str, str]]:
        # Title and URL from result__a
        m_title = re.search(
            r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            block, re.IGNORECASE | re.DOTALL,
        )
        if not m_title:
            return None
        title = _strip_tags(m_title.group("title") or "").strip()
        url = _normalize_ddg_url(m_title.group("url"))
        if not title or not url:
            return None
        # Snippet from result__snippet (it's an <a> with text)
        m_snip = re.search(
            r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
            block, re.IGNORECASE | re.DOTALL,
        )
        snippet = _strip_tags(m_snip.group("snippet") if m_snip else "").strip()
        return {"title": title, "url": url, "snippet": snippet}

    for m in block_re.finditer(html):
        item = _extract_block(m.group(1))
        if item:
            results.append(item)
        if len(results) >= max_results:
            return results

    # Fallback: scan for every <a class="result__a"> in document order,
    # pairing each with the next <a class="result__snippet">.
    if not results:
        a_re = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        s_re = re.compile(
            r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        titles = list(a_re.finditer(html))
        snippets = list(s_re.finditer(html))
        # Pair by index, capped at min(len(titles), len(snippets))
        for i, t in enumerate(titles):
            if i >= len(snippets):
                break
            title = _strip_tags(t.group("title") or "").strip()
            url = _normalize_ddg_url(t.group("url"))
            snippet = _strip_tags(snippets[i].group("snippet") or "").strip()
            if title and url:
                results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break

    return results


def _normalize_ddg_url(url: str) -> str:
    """Unwrap DDG redirect URLs (//duckduckgo.com/l/?uddg=...)."""
    if "duckduckgo.com/l/" in url and "uddg=" in url:
        try:
            parsed = urlparse(url if url.startswith("http") else f"https:{url}")
            qs = parse_qs(parsed.query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        except Exception:
            return url
    if url.startswith("//"):
        return "https:" + url
    return url


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    s = _TAG_RE.sub(" ", s)
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    s = s.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


# ── Public API ─────────────────────────────────────────────────────────
class WebSearcher:
    """Search DuckDuckGo HTML endpoint and return ranked results.

    Usage:
        s = WebSearcher()
        results = s.search("neural plasticity STDP review", max_results=5)
    """

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Returns a list of {title, url, snippet} dicts."""
        if not query or not query.strip():
            return []
        cache_key = f"search::{query}::{max_results}"
        cached = _cache_get(cache_key)
        if cached:
            return cached.get("results", [])

        try:
            resp = self.session.get(
                DDG_URL,
                params={"q": query, "kl": "it-it"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            return [{"error": f"search failed: {e}"}]

        results = _parse_ddg_results(html, max_results)
        _cache_put(cache_key, {"ts": time.time(), "type": "search", "query": query,
                                "max_results": max_results, "results": results})
        return results


class DocumentFetcher:
    """Fetch a URL and extract readable text.

    Returns dict with keys: url, status, title, description, text, length.
    """

    def __init__(self, timeout: float = 20.0, max_chars: int = 30000):
        self.timeout = timeout
        self.max_chars = max_chars
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch(self, url: str) -> Dict[str, Any]:
        if not url or not url.startswith(("http://", "https://")):
            return {"url": url, "status": 0, "error": "Invalid URL"}
        cache_key = f"fetch::{url}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            status = resp.status_code
            ctype = resp.headers.get("Content-Type", "").lower()
            if status != 200:
                result = {"url": url, "status": status, "error": f"HTTP {status}",
                          "content_type": ctype}
            elif "text/html" not in ctype and "application/xhtml" not in ctype:
                result = {"url": url, "status": status, "error": f"Non-HTML content: {ctype}",
                          "content_type": ctype}
            else:
                # Try to detect encoding
                text = resp.content.decode(resp.encoding or "utf-8", errors="replace")
                extracted = _extract_text(text)
                truncated_text = extracted["text"][: self.max_chars]
                if len(extracted["text"]) > self.max_chars:
                    truncated_text += f"\n\n[...troncato a {self.max_chars} caratteri su {len(extracted['text'])} totali...]"
                result = {
                    "url": url,
                    "status": status,
                    "title": extracted["title"],
                    "description": extracted["description"],
                    "text": truncated_text,
                    "length": len(extracted["text"]),
                }
        except requests.Timeout:
            result = {"url": url, "status": 0, "error": "Timeout"}
        except Exception as e:
            result = {"url": url, "status": 0, "error": str(e)}

        _cache_put(cache_key, {"ts": time.time(), "type": "fetch", **result})
        return result


# ── High-level helper for agents ───────────────────────────────────────
def research(query: str, max_results: int = 5, fetch_top: int = 2,
             fetch_max_chars: int = 8000) -> Dict[str, Any]:
    """One-shot research: search + fetch the top N results.

    Returns:
        {
            "query": str,
            "results": [{"title","url","snippet"} ...],
            "documents": [{"url","title","text","length"} ...]
        }
    """
    s = WebSearcher()
    f = DocumentFetcher(max_chars=fetch_max_chars)
    results = s.search(query, max_results=max_results)
    if not results or (len(results) == 1 and "error" in results[0]):
        return {"query": query, "results": results, "documents": [],
                "error": results[0].get("error") if results else "no results"}

    documents = []
    for r in results[:fetch_top]:
        doc = f.fetch(r["url"])
        documents.append({
            "url": r["url"],
            "title": r.get("title", ""),
            "text": doc.get("text", ""),
            "length": doc.get("length", 0),
            "status": doc.get("status", 0),
            "error": doc.get("error"),
        })
    return {"query": query, "results": results, "documents": documents}
