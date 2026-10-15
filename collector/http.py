"""Polite HTTP client: one session, fixed delay, robots.txt check, retries."""
import time
import urllib.robotparser
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
        rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.s.get(base + "/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[base] = rp
        return rp.can_fetch(self.s.headers["User-Agent"], url)

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
