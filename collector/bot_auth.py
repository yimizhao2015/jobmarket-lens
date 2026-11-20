"""Web Bot Auth: sign each request so Cloudflare can verify who we are (RFC 9421 HTTP Message Signatures).

Cloudflare's bot protection (in front of Workday career sites since Nov 2026) lets verified bots through when the
site allows them. We identify ourselves with an Ed25519 key: every request carries Signature-Agent, Signature-Input
and Signature headers, and the matching public key is published by the site's Worker at
https://www.jobmarketlens.com/.well-known/http-message-signatures-directory (functions/bot_key_directory.js).

The key is a private JWK ({"kty":"OKP","crv":"Ed25519","x":...,"d":...}) in the WEB_BOT_AUTH_KEY environment
variable (a GitHub Actions secret; the Worker has the same secret). Without it, requests go out unsigned.
https://developers.cloudflare.com/bots/reference/bot-verification/web-bot-auth/
"""
import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlparse

SIGNATURE_AGENT = "https://www.jobmarketlens.com"


def _b64url_decode(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def thumbprint(x):
    """RFC 7638 / RFC 8037 A.3 JWK thumbprint of an Ed25519 public key: the keyid."""
    canonical = json.dumps({"crv": "Ed25519", "kty": "OKP", "x": x}, separators=(",", ":"), sort_keys=True)
    return _b64url(hashlib.sha256(canonical.encode()).digest())


def authority(url):
    """RFC 9421 @authority: the host, lowercased, with the port only when it isn't the scheme's default."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if p.port and not ((p.scheme == "https" and p.port == 443) or (p.scheme == "http" and p.port == 80)):
        host += f":{p.port}"
    return host


class Signer:
    def __init__(self, jwk, agent=SIGNATURE_AGENT):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519" or not jwk.get("d"):
            raise ValueError("WEB_BOT_AUTH_KEY must be a private Ed25519 JWK")
        self._key = Ed25519PrivateKey.from_private_bytes(_b64url_decode(jwk["d"]))
        self.keyid = thumbprint(jwk["x"])
        self.agent = agent

    def headers(self, url, now=None, ttl=60):
        """The three headers for a request to url."""
        created = int(now if now is not None else time.time())
        agent = f'"{self.agent}"'  # a structured-field string: the quotes are part of the value
        params = (f'("@authority" "signature-agent");created={created};keyid="{self.keyid}";alg="ed25519"'
                  f';expires={created + ttl};nonce="{_b64url(secrets.token_bytes(32))}";tag="web-bot-auth"')
        base = f'"@authority": {authority(url)}\n"signature-agent": {agent}\n"@signature-params": {params}'
        sig = base64.b64encode(self._key.sign(base.encode())).decode()
        return {"Signature-Agent": agent, "Signature-Input": f"sig1={params}", "Signature": f"sig1=:{sig}:"}


def from_env():
    """A Signer from WEB_BOT_AUTH_KEY, or None when it isn't set (local runs, forks)."""
    raw = os.environ.get("WEB_BOT_AUTH_KEY", "").strip()
    return Signer(json.loads(raw)) if raw else None
