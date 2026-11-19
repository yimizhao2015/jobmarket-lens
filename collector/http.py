"""Polite HTTP client: one session, fixed delay, robots.txt check, retries."""
import os
import re
import ssl
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlparse

import certifi
import requests


class BlockedError(Exception):
    """The site refused us (robots.txt, 401/403, bot wall). Recorded, never papered over."""


class OutOfTime(Exception):
    """The run's time budget is used up (collector.run --minutes); the company stops where it is."""


class Cooldown:
    """A pause shared by the companies of one host group: when one of them is told to slow down (HTTP 429),
    all of them wait, since the platform counts our requests together."""
    def __init__(self):
        self.lock = threading.Lock()
        self.until = 0.0

    def hold(self, seconds):
        with self.lock:
            self.until = max(self.until, time.time() + seconds)

    def wait(self):
        left = self.until - time.time()
        if left > 0:
            time.sleep(left)


class Http:
    def __init__(self, user_agent, delay=0.6, respect_robots=True, timeout=30, cooldown=None):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent, "Accept-Language": "en-US,en;q=0.9"})
        self.delay = delay
        self.respect_robots = respect_robots
        self.timeout = timeout
        self._robots = {}
        self._last = 0.0
        self.cooldown = cooldown
        self.deadline = None  # time.time() after which no request starts (set by collector.run)
        # Postings of this company already in the history, {source_id: url} and {url: source_id}; run.py
        # fills them so adapters can skip detail pages they have read before (adapters.common.seen_before).
        self.known, self.known_urls = {}, {}

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
        if self.deadline and time.time() > self.deadline:
            raise OutOfTime("stopped: the run's time budget ran out")
        if not self._allowed(url):
            raise BlockedError(f"robots.txt disallows {url}")
        attempts = 7  # 429s get the longer schedule below; other errors give up after 4 tries
        for attempt in range(attempts):
            if self.cooldown:
                self.cooldown.wait()
            if self.deadline and time.time() > self.deadline:
                raise OutOfTime("stopped: the run's time budget ran out")
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
            except requests.exceptions.SSLError:
                # Some sites send their certificate without the intermediate. Fetch the missing intermediate
                # from the link in the certificate itself (AIA) and retry; the chain is still fully verified.
                if attempt >= 3 or not self._complete_chain(urlparse(url).hostname):
                    raise
                continue
            except requests.RequestException as e:
                if attempt >= 3:
                    raise
                time.sleep(2 ** (attempt + 1))
                continue
            if r.status_code in (401, 403):
                raise BlockedError(f"HTTP {r.status_code} from {url}")
            if r.status_code == 429 and r.headers.get("cf-mitigated") == "challenge":
                # Not a rate limit but a Cloudflare "Security Check" page that needs a browser (Workday sites since
                # Nov 2026). It sometimes clears after a pause; if it doesn't, the site is blocking us.
                if attempt >= 2:
                    raise BlockedError(f"Cloudflare security check (HTTP 429) from {url}")
                pause = 30 * 2 ** attempt
                if self.cooldown:
                    self.cooldown.hold(pause)
                time.sleep(pause)
                continue
            if r.status_code == 429 and attempt < attempts - 1:
                # Too many requests: wait as long as the site asks (Retry-After), else 15 s, 30 s, ... up to 4 min.
                pause = min(_retry_after(r) or 15 * 2 ** attempt, 240)
                if self.cooldown:
                    self.cooldown.hold(pause)
                time.sleep(pause)
                continue
            if r.status_code in (500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 2))
                continue
            r.raise_for_status()
            return r
        raise RuntimeError("unreachable")

    def _complete_chain(self, host):
        if host in getattr(self, "_chain_fixed", set()):
            return False
        self._chain_fixed = getattr(self, "_chain_fixed", set()) | {host}
        pems, pem = [], ssl.get_server_certificate((host, 443), timeout=self.timeout)
        for _ in range(3):  # leaf -> intermediate(s); stop once nothing more to fetch
            with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
                f.write(pem)
            try:
                issuers = ssl._ssl._test_decode_cert(f.name).get("caIssuers") or ()
            except ssl.SSLError:
                issuers = ()
            finally:
                os.unlink(f.name)
            if not issuers:
                break
            pem = _as_pem(requests.get(issuers[0], timeout=self.timeout).content)
            if not pem:
                raise requests.exceptions.SSLError(f"could not read the issuer certificate at {issuers[0]}")
            pems.append(pem)
        if not pems:
            return False
        bundle = getattr(self, "_bundle", None)
        if not bundle:
            fd, bundle = tempfile.mkstemp(suffix=".pem")
            os.close(fd)
            with open(certifi.where()) as src, open(bundle, "w") as dst:
                dst.write(src.read())
            self._bundle = bundle
        with open(bundle, "a") as dst:
            dst.write("\n" + "\n".join(pems))
        self.s.verify = bundle  # roots stay certifi's: only intermediates are added
        return True

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


def _retry_after(r):
    """Seconds from a Retry-After header given in seconds; None when absent or a date."""
    try:
        return max(0.0, float(r.headers.get("Retry-After", "")))
    except ValueError:
        return None


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


def _as_pem(data):
    """The first certificate in an AIA download as PEM: a PEM or DER certificate, or a PKCS#7 bundle (.p7c),
    which some CAs serve instead. None when it is none of these (an error page, say)."""
    if data.startswith(b"-----BEGIN CERTIFICATE"):
        return data.decode()
    if not data.startswith(b"\x30"):                      # not DER at all
        return None
    for args in (["x509", "-inform", "DER"], ["pkcs7", "-inform", "DER", "-print_certs"]):
        out = subprocess.run(["openssl", *args], input=data, capture_output=True)
        m = re.search(rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", out.stdout, re.S)
        if out.returncode == 0 and m:
            return m.group(0).decode() + "\n"
    return None
