import re
from scripts import tinyfish

_DOMAIN_RE = re.compile(r"^(https?://)?([\w-]+\.)+[a-z]{2,}(/\S*)?$", re.I)


def _clean_url(raw):
    """'Website / Source' cells are often a semicolon-joined citation list
    like 'kauligcapital.com; PitchBook (60 investments); FINTRX' — take the
    first token that actually looks like a fetchable domain/URL."""
    for tok in raw.split(";"):
        tok = tok.strip()
        if _DOMAIN_RE.match(tok):
            return tok
    return ""


def _query(row):
    """Build a search query from whatever the row has."""
    bits = [row["company"]]
    if row["hq"]:
        bits.append(row["hq"])
    # Add sector hints if available
    if row.get("industry"):
        bits.append(row["industry"])
    else:
        bits.append("real estate fund investments family office")
    return " ".join(bits)


def research(row):
    """Return an evidence bundle for one row using TinyFish Search + Fetch (both free)."""
    results = tinyfish.search(_query(row), n=5)

    # Pick pages to read: the row's website/domain first, then top organic result
    target_urls = []
    for field in ("website", "domain"):
        w = _clean_url(row.get(field, ""))
        if w and w.lower() not in ("n/a", "nan", ""):
            url = w if w.startswith("http") else "https://" + w
            if url not in target_urls:
                target_urls.append(url)
    for r in results:
        if r.get("url") and r["url"] not in target_urls:
            target_urls.append(r["url"])
        if len(target_urls) >= 3:
            break

    pages = tinyfish.fetch(target_urls[:3])

    return {
        "uid": row["uid"],
        "company": row["company"],
        "sheet_priors": {
            "contact_name": row.get("contact_name", ""),
            "title": row.get("title", ""),
            "industry": row.get("industry", ""),
            "hq": row.get("hq", ""),
            "country": row.get("country", ""),
            "employee_range": row.get("employee_range", ""),
            "company_type": row.get("company_type", ""),
            # xlsx-specific fields (empty for CSVs, that's fine)
            "source_of_wealth": row.get("source_of_wealth", ""),
            "family_founder": row.get("family_founder", ""),
            "claimed_aum": row.get("aum", ""),
            "claimed_re_classes": row.get("re_classes", ""),
            "claimed_style": row.get("investment_style", ""),
        },
        "search_results": [
            {"title": r.get("title"), "snippet": r.get("snippet"), "url": r.get("url")}
            for r in results
        ],
        "fetched_pages": [{"url": u, "text": t} for u, t in pages.items()],
    }
