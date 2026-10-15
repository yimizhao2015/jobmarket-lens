"""Field extractors: pay, degree, experience, seniority, schedule, work arrangement, geography.

All extractors return "Not specified" (or None for numbers) when the posting does not say;
nothing is imputed.
"""
import re

NS = "Not specified"

# ---------------------------------------------------------------- required vs preferred
_PREF_SPLIT = re.compile(r"\n?\s*(preferred qualifications|preferred skills|preferred experience|nice to have|"
                         r"bonus points|desired qualifications|preferred:|additional preferred)", re.I)


def required_part(text):
    """Text before the 'preferred' section, so minimums are not raised by nice-to-haves."""
    if not text:
        return ""
    m = _PREF_SPLIT.search(text)
    return text[:m.start()] if m and m.start() > 80 else text


# ---------------------------------------------------------------- pay
_NUM = r"\$?\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*([kK])?"
_RANGE = re.compile(_NUM + r"\s*(?:-|–|—|to)\s*" + _NUM + r"\s*(USD|CAD|EUR|GBP|INR)?\s*"
                    r"(per hour|/\s*hr|/\s*hour|hourly|an hour|per year|/\s*yr|/\s*year|annually|annual|a year|per annum|"
                    r"per month|monthly)?", re.I)
_PAY_CONTEXT = re.compile(r"(pay|salary|compensation|base|wage|range|USD|\$)", re.I)


def _num(s, k):
    v = float(s.replace(",", ""))
    return v * 1000 if k else v


def parse_pay(pay_text, description):
    """Return dict(min, max, period, currency, annual_min, annual_max) or None."""
    for src in (pay_text, description):
        if not src:
            continue
        for m in _RANGE.finditer(src):
            window = src[max(0, m.start() - 160): m.end() + 20]
            if src is description and not _PAY_CONTEXT.search(window):
                continue
            lo, hi = _num(m.group(1), m.group(2)), _num(m.group(3), m.group(4))
            if lo > hi:
                lo, hi = hi, lo
            cur = (m.group(5) or ("USD" if "$" in m.group(0) or "USD" in window else "")).upper() or None
            unit = (m.group(6) or "").lower()
            if "hour" in unit or "hr" in unit:
                period = "hour"
            elif "month" in unit:
                period = "month"
            elif unit:
                period = "year"
            else:
                period = "hour" if hi < 300 else "year"
            mult = {"hour": 2080, "month": 12, "year": 1}[period]
            amin, amax = lo * mult, hi * mult
            if period == "hour" and not (7 <= lo <= 500):
                continue
            if period == "year" and not (15000 <= lo <= 3_000_000):
                continue
            return {"min": lo, "max": hi, "period": period, "currency": cur,
                    "annual_min": round(amin), "annual_max": round(amax)}
    return None


# ---------------------------------------------------------------- degree
DEGREE_ORDER = ["High school", "Associate", "Bachelor's", "Master's", "Doctorate"]
_DEG = [
    ("Doctorate", r"\bph\.?d\b|doctorate|doctoral|\bpharm\.?d\b|\bm\.?d\.?\b(?= degree)"),
    ("Master's", r"master'?s|\bm\.?s\.?\b(?= (degree|in))|\bmba\b|\bmasters\b"),
    ("Bachelor's", r"bachelor'?s|\bb\.?s\.?\b(?= (degree|in))|\bb\.?a\.?\b(?= (degree|in))|undergraduate degree|"
                   r"4[- ]year degree|four[- ]year degree|university degree|college degree|\bbachelors\b|degree in"),
    ("Associate", r"associate'?s degree|associate degree|2[- ]year degree|two[- ]year degree"),
    ("High school", r"high school|\bged\b|secondary school"),
]
_DEG_RX = [(lvl, re.compile(rx, re.I)) for lvl, rx in _DEG]
_EQUIV = re.compile(r"or equivalent (practical |work |professional )?experience|equivalent experience|"
                    r"or relevant experience|in lieu of", re.I)
_ENROLLED = re.compile(r"currently (enrolled|pursuing)", re.I)


def parse_degree(text):
    """Minimum degree named in the required part. Returns (level, equivalent_experience_accepted)."""
    req = required_part(text)
    found = [lvl for lvl, rx in _DEG_RX if rx.search(req)]
    if not found:
        return NS, False
    lvl = min(found, key=DEGREE_ORDER.index)
    if _ENROLLED.search(req) and lvl != "High school":
        lvl = "Enrolled student"
    return lvl, bool(_EQUIV.search(req))


# ---------------------------------------------------------------- experience
_YRS = re.compile(r"(?<![\d.])(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*\d{1,2}\s*)?\+?\s*(?:years?|yrs?)\b(?:\s+of)?"
                  r"(?=[^.\n]{0,80}(experience|work|industry|relevant|professional|in\b|with\b))", re.I)


def parse_years(text):
    req = required_part(text)
    vals = [int(m.group(1)) for m in _YRS.finditer(req) if int(m.group(1)) <= 30]
    return vals[0] if vals else None  # first stated requirement is the primary one


def years_bucket(y):
    if y is None:
        return NS
    if y <= 1:
        return "0-1 yrs"
    if y <= 4:
        return "2-4 yrs"
    if y <= 7:
        return "5-7 yrs"
    if y <= 10:
        return "8-10 yrs"
    return "10+ yrs"


# ---------------------------------------------------------------- seniority
LEVELS = ["Intern", "Entry", "Mid", "Senior", "Lead / Principal", "Manager", "Director & Executive"]
_LVL = [
    ("Intern", r"\bintern(ship)?\b|\bco-?op\b|apprentice|\bphd intern"),
    ("Director & Executive", r"\b(chief|vice president|\bvp\b|svp|evp|head of|director|president)\b"),
    ("Lead / Principal", r"\b(principal|staff|distinguished|fellow|lead)\b"),
    ("Manager", r"\b(manager|mgr|supervisor|store leader)\b"),
    ("Senior", r"\b(senior|sr\.?|iii|iv|expert|advisor - expert)\b"),
    ("Entry", r"\b(entry|junior|jr\.?|new grad|graduate|early career|campus|associate\b|i\b(?!i)|trainee)"),
]
_LVL_RX = [(lvl, re.compile(rx, re.I)) for lvl, rx in _LVL]
_HINT = {"early": "Entry", "entry": "Entry", "mid": "Mid", "advanced": "Senior", "senior": "Senior",
         "director": "Director & Executive", "executive": "Director & Executive", "intern": "Intern",
         "internship": "Intern", "student": "Intern", "associate": "Entry", "mid-senior level": "Senior",
         "mid-level": "Mid"}


def parse_level(title, level_hint, years):
    t = title or ""
    for lvl, rx in _LVL_RX[:2]:
        if rx.search(t):
            return lvl
    if level_hint:
        h = level_hint.strip().lower()
        for k, v in _HINT.items():
            if h.startswith(k):
                return v
    for lvl, rx in _LVL_RX[2:]:
        if rx.search(t):
            return lvl
    if years is None:
        return NS
    if years <= 1:
        return "Entry"
    if years <= 4:
        return "Mid"
    return "Senior"


# ---------------------------------------------------------------- schedule
def parse_schedule(employment_type, title, text):
    s = " ".join(filter(None, [employment_type, title]))
    if re.search(r"intern|co-?op", s, re.I):
        return "Internship"
    if re.search(r"seasonal|temporary|temp\b|fixed[- ]term", s, re.I):
        return "Temporary / Seasonal"
    if re.search(r"contract", employment_type or "", re.I):
        return "Contract"
    ft = re.search(r"full[ _-]?time|\bregular\b", s, re.I)
    pt = re.search(r"part[ _-]?time", s, re.I)
    if ft and pt:
        return "Full- or part-time"
    if pt:
        return "Part-time"
    if ft:
        return "Full-time"
    if text and re.search(r"\bfull[- ]time\b", text[:3000], re.I):
        return "Full-time"
    if text and re.search(r"\bpart[- ]time\b", text[:3000], re.I):
        return "Part-time"
    return NS


# ---------------------------------------------------------------- work arrangement
def parse_arrangement(remote_hint, locations, text):
    h = (remote_hint or "").lower()
    if "telecommute" in h or h.startswith("remote") or "fully remote" in h:
        return "Remote"
    if "hybrid" in h or "flex" in h:
        return "Hybrid"
    if any(x in h for x in ("on-site", "onsite", "on site", "in office", "in-office")):
        return "On-site"
    locs = " ".join(locations or [])
    if re.search(r"\bremote\b", locs, re.I):
        return "Remote"
    t = text or ""
    if re.search(r"\bhybrid\b", t, re.I):
        return "Hybrid"
    if re.search(r"fully remote|100% remote|remote[- ]first|this (is a|position is|role is) remote|"
                 r"work from home|remote (eligible|position|role)|can be remote|open to remote", t, re.I):
        return "Remote"
    if re.search(r"\b(on-?site|in[- ]person|in[- ]office)\b|5 days (a|per) week in (the )?office", t, re.I):
        return "On-site"
    return NS


# ---------------------------------------------------------------- geography
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}
_STATE_BY_NAME = {v.lower(): k for k, v in US_STATES.items()}
COUNTRIES = {
    "US": "United States", "USA": "United States", "UNITED STATES": "United States",
    "UNITED STATES OF AMERICA": "United States", "CA": "Canada", "CAN": "Canada", "CANADA": "Canada",
    "GB": "United Kingdom", "UK": "United Kingdom", "GBR": "United Kingdom", "UNITED KINGDOM": "United Kingdom",
    "IN": "India", "IND": "India", "INDIA": "India", "MY": "Malaysia", "MYS": "Malaysia", "MALAYSIA": "Malaysia",
    "SG": "Singapore", "SGP": "Singapore", "SINGAPORE": "Singapore", "DE": "Germany", "DEU": "Germany",
    "GERMANY": "Germany", "FR": "France", "FRA": "France", "FRANCE": "France", "IE": "Ireland", "IRL": "Ireland",
    "IRELAND": "Ireland", "JP": "Japan", "JPN": "Japan", "JAPAN": "Japan", "CN": "China", "CHN": "China",
    "CHINA": "China", "TW": "Taiwan", "TWN": "Taiwan", "TAIWAN": "Taiwan", "IL": "Israel", "ISR": "Israel",
    "ISRAEL": "Israel", "KR": "South Korea", "KOR": "South Korea", "KOREA (REPUBLIC OF)": "South Korea",
    "SOUTH KOREA": "South Korea", "MX": "Mexico", "MEX": "Mexico", "MEXICO": "Mexico", "BR": "Brazil",
    "BRA": "Brazil", "BRAZIL": "Brazil", "AR": "Argentina", "ARG": "Argentina", "ARGENTINA": "Argentina",
    "BE": "Belgium", "BEL": "Belgium", "BELGIUM": "Belgium", "NL": "Netherlands", "NLD": "Netherlands",
    "NETHERLANDS": "Netherlands", "HU": "Hungary", "HUN": "Hungary", "HUNGARY": "Hungary", "TH": "Thailand",
    "THA": "Thailand", "THAILAND": "Thailand", "PL": "Poland", "POL": "Poland", "POLAND": "Poland",
    "ES": "Spain", "ESP": "Spain", "SPAIN": "Spain", "IT": "Italy", "ITA": "Italy", "ITALY": "Italy",
    "CH": "Switzerland", "CHE": "Switzerland", "SWITZERLAND": "Switzerland", "AT": "Austria", "AUSTRIA": "Austria",
    "SE": "Sweden", "SWE": "Sweden", "SWEDEN": "Sweden", "AU": "Australia", "AUS": "Australia",
    "AUSTRALIA": "Australia", "PH": "Philippines", "PHL": "Philippines", "PHILIPPINES": "Philippines",
    "CR": "Costa Rica", "COSTA RICA": "Costa Rica", "TR": "Turkiye", "TURKIYE": "Turkiye", "TURKEY": "Turkiye",
    "AE": "United Arab Emirates", "UAE": "United Arab Emirates", "UNITED ARAB EMIRATES": "United Arab Emirates",
    "MH": "Marshall Islands", "PUERTO RICO": "United States", "VIETNAM": "Vietnam", "VN": "Vietnam",
    "CZ": "Czechia", "CZECHIA": "Czechia", "CZECH REPUBLIC": "Czechia", "RO": "Romania", "ROMANIA": "Romania",
    "DK": "Denmark", "DENMARK": "Denmark", "FI": "Finland", "FINLAND": "Finland", "NO": "Norway", "NORWAY": "Norway",
    "PT": "Portugal", "PORTUGAL": "Portugal", "CO": "Colombia", "COLOMBIA": "Colombia", "CL": "Chile", "CHILE": "Chile",
}


def parse_location(loc):
    """Return (country, us_state_code_or_None, city_or_None) from one location string."""
    if not loc:
        return None, None, None
    s = re.sub(r"\s+", " ", loc).strip()
    m = re.match(r"various locations within (.+)", s, re.I)
    if m:
        return COUNTRIES.get(m.group(1).strip().upper(), m.group(1).strip()), None, None
    parts = [p.strip() for p in re.split(r",| - |\|", s) if p.strip()]
    parts = [p for p in parts if not re.fullmatch(r"[A-Z]?\d[\dA-Z ]{2,8}", p)]  # drop postal codes
    if not parts:
        return None, None, None
    up = [p.upper() for p in parts]
    # "US, WA, Seattle" (Amazon/Workday style)
    if up[0] in ("US", "USA") and len(parts) >= 2:
        st = up[1] if up[1] in US_STATES else _STATE_BY_NAME.get(parts[1].lower())
        return "United States", st, parts[-1] if len(parts) >= 3 else None
    # "City, ST" with a US state and no country
    if len(parts) == 2 and (parts[1] in US_STATES or parts[1].lower() in _STATE_BY_NAME):
        return "United States", US_STATES.get(parts[1]) and parts[1] or _STATE_BY_NAME[parts[1].lower()], parts[0]
    country = COUNTRIES.get(up[-1])
    if country is None:
        country = next((COUNTRIES[p] for p in up if p in COUNTRIES and len(p) > 3), None)
    state = None
    if country == "United States":
        for p in parts[1:-1] or parts[:-1]:
            if p.upper() in US_STATES:
                state = p.upper()
            elif p.lower() in _STATE_BY_NAME:
                state = _STATE_BY_NAME[p.lower()]
    city = parts[0] if (len(parts) > 1 or country is None) else None
    if city and (city.upper() in COUNTRIES or re.search(r"remote|multiple|various", city, re.I)):
        city = None
    return country, state, city
