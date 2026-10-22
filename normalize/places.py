"""Place names from GeoNames (geonames.org, CC BY 4.0, via the geonamescache package), used to fill the country
and US state of a posting whose career site gives only a city, or writes its location in a form parse.py's
rules don't split. A city name is used only when it points to one place clearly: the largest place with that
name must be several times larger than the next one in another country or state, so "London" is London,
United Kingdom, but "Richmond" or "Vancouver" stay without a country."""
import re
import unicodedata

import geonamescache

MIN_POPULATION = 5000       # smallest places considered (GeoNames' 5,000+ list)
CLEAR_RATIO = 5             # the largest match must be this many times the next one elsewhere

_gc = geonamescache.GeonamesCache(min_city_population=MIN_POPULATION)
_COUNTRY_BY_CODE = {c["iso"]: c["name"] for c in _gc.get_countries().values()}
_COUNTRY_BY_CODE.update({"US": "United States", "PR": "United States", "KR": "South Korea", "TR": "Turkiye",
                         "CZ": "Czechia", "VN": "Vietnam", "TW": "Taiwan", "HK": "Hong Kong",
                         "MK": "North Macedonia", "CG": "Republic of the Congo", "CD": "DR Congo"})
ISO3 = {c["iso3"]: _COUNTRY_BY_CODE[c["iso"]] for c in _gc.get_countries().values()}
NAMES = {_COUNTRY_BY_CODE[c["iso"]].upper(): _COUNTRY_BY_CODE[c["iso"]] for c in _gc.get_countries().values()}
NAMES.update({c["name"].upper(): _COUNTRY_BY_CODE[c["iso"]] for c in _gc.get_countries().values()})
# Other spellings and languages seen on career sites
NAMES.update({
    "ENGLAND": "United Kingdom", "SCOTLAND": "United Kingdom", "WALES": "United Kingdom",
    "NORTHERN IRELAND": "United Kingdom", "GREAT BRITAIN": "United Kingdom", "ENG": "United Kingdom",
    "CHINA MAINLAND": "China", "MAINLAND CHINA": "China", "REPUBLIC OF KOREA": "South Korea",
    "KOREA, REPUBLIC OF": "South Korea", "TÜRKIYE": "Turkiye", "RUSSIA": "Russia", "UNITED STATES OF AMERICA": "United States",
    "CONGO-BRAZZAVILLE": "Republic of the Congo", "IVORY COAST": "Ivory Coast", "CÔTE D'IVOIRE": "Ivory Coast",
    # French
    "ÉTATS-UNIS": "United States", "ROYAUME-UNI": "United Kingdom", "ALLEMAGNE": "Germany", "IRLANDE": "Ireland",
    "POLOGNE": "Poland", "MEXIQUE": "Mexico", "ESPAGNE": "Spain", "ITALIE": "Italy", "SUISSE": "Switzerland",
    "BELGIQUE": "Belgium", "PAYS-BAS": "Netherlands", "TAÏWAN": "Taiwan", "INDE": "India", "CHINE": "China",
    "JAPON": "Japan", "CORÉE DU SUD": "South Korea", "ÉMIRATS ARABES UNIS": "United Arab Emirates",
    "BRÉSIL": "Brazil", "AUTRICHE": "Austria", "SUÈDE": "Sweden", "DANEMARK": "Denmark", "NORVÈGE": "Norway",
    "SINGAPOUR": "Singapore", "AUSTRALIE": "Australia", "HONGRIE": "Hungary", "ROUMANIE": "Romania",
    "RÉPUBLIQUE TCHÈQUE": "Czechia", "TCHÉQUIE": "Czechia", "MALAISIE": "Malaysia", "TURQUIE": "Turkiye",
    "ARABIE SAOUDITE": "Saudi Arabia", "ÉGYPTE": "Egypt", "MAROC": "Morocco", "AFRIQUE DU SUD": "South Africa",
    # Spanish / Portuguese
    "CANADÁ": "Canada", "ESPAÑA": "Spain", "MALASIA": "Malaysia", "REINO UNIDO": "United Kingdom",
    "ALEMANIA": "Germany", "FRANCIA": "France", "BRASIL": "Brazil", "MÉXICO": "Mexico", "JAPÓN": "Japan",
    "PAÍSES BAJOS": "Netherlands", "SUIZA": "Switzerland", "IRLANDA": "Ireland", "POLONIA": "Poland",
    # Polish
    "STANY ZJEDNOCZONE AMERYKI": "United States", "STANY ZJEDNOCZONE": "United States", "NIEMCY": "Germany",
    "ZJEDNOCZONE KRÓLESTWO": "United Kingdom", "WIELKA BRYTANIA": "United Kingdom", "KANADA": "Canada",
    "FRANCJA": "France", "HISZPANIA": "Spain", "WŁOCHY": "Italy", "MEKSYK": "Mexico", "INDIE": "India",
    "CHINY": "China", "JAPONIA": "Japan", "IRLANDIA": "Ireland", "HOLANDIA": "Netherlands",
    "PORTORYKO": "United States", "AUSTRALIA": "Australia", "POLSKA": "Poland",
    # Others
    "DEUTSCHLAND": "Germany", "ÖSTERREICH": "Austria", "SCHWEIZ": "Switzerland", "NEDERLAND": "Netherlands",
    "ITALIA": "Italy", "РОССИЯ": "Russia", "КЫРГЫЗСТАН": "Kyrgyzstan", "КАЗАХСТАН": "Kazakhstan",
    "中國": "China", "中国": "China", "韓國": "South Korea", "韩国": "South Korea", "타이완": "Taiwan", "台灣": "Taiwan",
    "중국": "China", "TCHAJ-WAN": "Taiwan", "日本": "Japan", "미국": "United States", "美國": "United States",
})


def _key(s):
    """Lower-case, accents removed, punctuation folded to spaces: "São Paulo" and "SAO PAULO" share a key."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower().replace("st.", "saint").replace("ft.", "fort")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_PLAIN = re.compile(r"[A-Za-zÀ-ÿ' .\-]{4,}$")
_CITIES = {}     # key -> {(country, us_state): (population, name)}, from each place's own name
_OTHER = {}      # the same, from other names of large cities
for c in _gc.get_cities().values():
    country = _COUNTRY_BY_CODE.get(c["countrycode"])
    if not country:
        continue
    st = c["admin1code"] if c["countrycode"] == "US" else ("PR" if c["countrycode"] == "PR" else None)
    # other names ("Bangalore", "Milano", "Bombay") only for large cities: small places' alternate names are
    # often a neighborhood or a nearby town's name ("Mystic" is listed under Medford, Massachusetts)
    other = {a for a in c.get("alternatenames") or [] if _PLAIN.match(a)} if c["population"] >= 100000 else set()
    for index, names in ((_CITIES, {c["name"]}), (_OTHER, other)):
        for n in names:
            k = _key(n)
            if len(k) < 4:
                continue
            slot = index.setdefault(k, {})
            prev = slot.get((country, st))
            if not prev or c["population"] > prev[0]:
                slot[(country, st)] = (c["population"], c["name"])


def country(text):
    """English country name for a country name, ISO3 code or foreign spelling, else None."""
    t = (text or "").strip().upper()
    return NAMES.get(t) or ISO3.get(t)


def city(text, country_name=None, us_state=None, prefer=None):
    """(country, us_state, city name, population) for a city name that clearly points to one place, else None.
    A known country or US state narrows the matches first; then, when any match is in a country in prefer
    (the countries a company's other postings name), only those count. When the name is still unclear but
    every close match is in one country, that country comes back with no state or city."""
    k = _key(text or "")
    found = _CITIES.get(k) or _OTHER.get(k)
    if not found:
        return None
    cands = [(pop, ctry, st, name) for (ctry, st), (pop, name) in found.items()
             if (not country_name or ctry == country_name) and (not us_state or st == us_state)]
    if prefer and any(c[1] in prefer for c in cands):
        cands = [c for c in cands if c[1] in prefer]
    if not cands:
        return None
    cands.sort(reverse=True)
    close = [c for c in cands if c[0] * CLEAR_RATIO > cands[0][0]]
    if len(close) > 1:
        if len({c[1] for c in close}) == 1 and not country_name:
            return close[0][1], None, None, close[0][0]
        return None
    pop, ctry, st, name = cands[0]
    return ctry, st, name, pop
