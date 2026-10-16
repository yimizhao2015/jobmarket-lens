"""Polite HTTP client: one session, fixed delay, robots.txt check, retries."""
import re
import time
from urllib.parse import urlparse

import requests


class BlockedError(Exception):
    """The site refused us (robots.txt, 401/403, bot wall). Recorded, never papered over."""


class Http:
    def __init__(self, user_agent, delay=0.6, respect_robots=True, timeout=30):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"})
        self.delay = delay
        self.respect_robots = respect_robots
        self.timeout = timeout
        self._robots = {}
        self._last = 0.0

    def _allowed(self, url):
        if not self.respect_robots:
            return True
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        rules = self._robots.get(base)
        if rules is None:
            try:
                r = self.s.get(base + "/robots.txt", timeout=self.timeout)
                text = r.text if r.status_code == 200 else ""
            except requests.RequestException:
                text = ""
            rules, crawl_delay = parse_robots(text, self.s.headers["User-Agent"])
            if crawl_delay:
                self.delay = max(self.delay, crawl_delay)
            self._robots[base] = rules
        path = (p.path or "/") + (f"?{p.query}" if p.query else "")
        return robots_allows(rules, path)

    def request(self, method, url, **kw):
        if not self._allowed(url):
            raise BlockedError(f"robots.txt disallows {url}")
        for attempt in range(4):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
            except requests.RequestException as e:
                if attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
                continue
            if r.status_code in (401, 403):
                raise BlockedError(f"HTTP {r.status_code} from {url}")
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 2))
                continue
            r.raise_for_status()
            return r
        raise RuntimeError("unreachable")

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


def parse_robots(text, user_agent):
    """Rules (allow?, pattern) and Crawl-delay for our agent, per RFC 9309: the group naming our
    product token if there is one, otherwise the '*' group."""
    token = user_agent.split("/")[0].strip().lower()
    groups, cur, in_agents = [], None, False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not in_agents:
                cur = {"agents": [], "rules": [], "delay": None}
                groups.append(cur)
            cur["agents"].append(val.lower())
            in_agents = True
            continue
        in_agents = False
        if cur is None:
            continue
        if key in ("allow", "disallow") and val:
            cur["rules"].append((key == "allow", val))
        elif key == "crawl-delay":
            try:
                cur["delay"] = float(val)
            except ValueError:
                pass
    mine = [g for g in groups if any(a != "*" and a in token for a in g["agents"])]
    chosen = mine or [g for g in groups if "*" in g["agents"]]
    rules = [r for g in chosen for r in g["rules"]]
    delays = [g["delay"] for g in chosen if g["delay"]]
    return rules, (max(delays) if delays else None)


def robots_allows(rules, path):
    """RFC 9309: the longest matching rule wins; on a tie, allow wins. No match means allowed."""
    best_len, allowed = -1, True
    for allow, pattern in rules:
        rx = "^" + re.escape(pattern).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path):
            n = len(pattern)
            if n > best_len or (n == best_len and allow):
                best_len, allowed = n, allow
    return allowed
