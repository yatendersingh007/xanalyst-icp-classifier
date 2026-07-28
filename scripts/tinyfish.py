import time
import requests
from config import (TINYFISH_API_KEY, TF_SEARCH_URL, TF_FETCH_URL,
                    TF_LOCATION, PAGE_CHAR_LIMIT)

_HEADERS = {"X-API-Key": TINYFISH_API_KEY}
_RETRY_STATUS = {429, 500, 502, 503}


def _get(url, **kw):
    for attempt in range(4):
        r = requests.get(url, headers=_HEADERS, timeout=30, **kw)
        if r.status_code in _RETRY_STATUS:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def _post(url, payload):
    for attempt in range(4):
        r = requests.post(url, headers=_HEADERS, json=payload, timeout=60)
        if r.status_code in _RETRY_STATUS:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def search(query, n=5):
    """Ranked web results: [{position, site_name, title, snippet, url}, ...]"""
    data = _get(TF_SEARCH_URL, params={"query": query[:2000], "location": TF_LOCATION})
    return (data.get("results") or [])[:n]


def fetch(urls):
    """Clean markdown per URL. Returns {url: text}. Per-URL failures are skipped."""
    urls = [u for u in urls if u][:10]
    if not urls:
        return {}
    data = _post(TF_FETCH_URL, {"urls": urls, "format": "markdown"})
    out = {}
    for res in data.get("results", []):
        txt = res.get("text")
        if isinstance(txt, str) and txt.strip():
            out[res["url"]] = txt[:PAGE_CHAR_LIMIT]
    return out
