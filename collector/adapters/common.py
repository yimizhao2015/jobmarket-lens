"""Shared helpers for adapters: the raw posting record and schema.org JobPosting parsing."""
import html
import json
import re

from bs4 import BeautifulSoup


def raw_posting(company, source_id, url, title, **kw):
    """Uniform raw record every adapter yields. Unknown fields stay None; nothing is guessed here."""
    rec = {
        "company": company,
        "source_id": str(source_id),
        "url": url,
        "title": title,
        "description": None,       # plain text
        "locations": [],           # list of "City, Region, Country" strings as the site gives them
        "posted_date": None,       # ISO date (YYYY-MM-DD) when the site exposes one
        "employment_type": None,   # raw text, e.g. "FULL_TIME", "Full time"
        "remote_hint": None,       # raw text, e.g. "TELECOMMUTE", "Hybrid", "Flexible"
        "pay_text": None,          # raw pay text when given outside the description
        "category": None,          # the company's own job family / team label
        "level_hint": None,        # the company's own level label, if any
        "source_method": "api",    # api | html | jsonld | page-read
    }
    rec.update({k: v for k, v in kw.items() if v is not None})
    for k in ("category", "employment_type", "remote_hint", "level_hint", "pay_text"):
        if isinstance(rec[k], list):  # JSON-LD allows lists here; downstream expects text
            rec[k] = ", ".join(str(x) for x in rec[k] if x) or None
    return rec


def html_to_text(s):
    if not s:
        return None
    soup = BeautifulSoup(s, "html.parser")
    for br in soup.find_all(["br", "li", "p", "div", "h1", "h2", "h3", "h4"]):
        br.insert_before("\n")
    text = html.unescape(soup.get_text(" "))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def find_jobposting_jsonld(page_html):
    """Return the first schema.org JobPosting object embedded in a page, or None."""
    soup = BeautifulSoup(page_html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                if d.get("@type") == "JobPosting":
                    return d
                stack.extend(d.get("@graph", []) if isinstance(d.get("@graph"), list) else [])
            elif isinstance(d, list):
                stack.extend(d)
    return None


def _place(loc):
    if isinstance(loc, dict):
        a = loc.get("address", loc)
        if isinstance(a, dict):
            parts = [a.get("addressLocality"), a.get("addressRegion"), a.get("addressCountry")]
            parts = [p.get("name") if isinstance(p, dict) else p for p in parts]
            return ", ".join(p for p in parts if p)
        if isinstance(a, str):
            return a
    return str(loc) if loc else None


def _salary_text(bs):
    if not isinstance(bs, dict):
        return None
    v = bs.get("value", {})
    cur = bs.get("currency", "")
    if isinstance(v, dict):
        lo, hi, unit = v.get("minValue"), v.get("maxValue"), v.get("unitText", "")
        val = v.get("value")
        if lo or hi:
            return f"{lo} - {hi} {cur} {unit}".strip()
        if val:
            return f"{val} {cur} {unit}".strip()
    return None


def jobposting_to_raw(company, source_id, url, jp, **kw):
    locs = jp.get("jobLocation") or []
    locs = locs if isinstance(locs, list) else [locs]
    et = jp.get("employmentType")
    if isinstance(et, list):
        et = ", ".join(et)
    posted = (jp.get("datePosted") or "")[:10] or None
    return raw_posting(
        company, source_id, url, jp.get("title"),
        description=html_to_text(jp.get("description")),
        locations=[p for p in (_place(l) for l in locs) if p],
        posted_date=posted,
        employment_type=et,
        remote_hint=jp.get("jobLocationType"),
        pay_text=_salary_text(jp.get("baseSalary")),
        category=jp.get("occupationalCategory") or jp.get("industry"),
        source_method="jsonld",
        **kw,
    )
