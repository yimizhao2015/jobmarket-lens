// Web Bot Auth key directory (/.well-known/http-message-signatures-directory): publishes the public half of the
// collector's Ed25519 key so Cloudflare can verify the signed requests it sends (collector/bot_auth.py).
// The key is the WEB_BOT_AUTH_KEY Worker secret (a private JWK, the same value as the GitHub Actions secret).
// The response itself is signed with that key, as the directory draft asks.
// https://datatracker.ietf.org/doc/draft-meunier-http-message-signatures-directory/

const b64url = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function thumbprint(x) {
  const canonical = JSON.stringify({ crv: "Ed25519", kty: "OKP", x });
  return b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(canonical)));
}

export async function onRequestGet({ request, env }) {
  if (!env.WEB_BOT_AUTH_KEY) return new Response("Not found", { status: 404 });
  const jwk = JSON.parse(env.WEB_BOT_AUTH_KEY);
  const body = JSON.stringify({ keys: [{ kty: "OKP", crv: "Ed25519", x: jwk.x }] });
  const key = await crypto.subtle.importKey("jwk", { kty: "OKP", crv: "Ed25519", x: jwk.x, d: jwk.d }, { name: "Ed25519" }, false, ["sign"]);
  const created = Math.floor(Date.now() / 1000);
  const nonce = b64url(crypto.getRandomValues(new Uint8Array(32)));
  const params = `("@authority";req);alg="ed25519";keyid="${await thumbprint(jwk.x)}";nonce="${nonce}";tag="http-message-signatures-directory";created=${created};expires=${created + 300}`;
  const base = `"@authority";req: ${new URL(request.url).host.toLowerCase()}\n"@signature-params": ${params}`;
  const sig = btoa(String.fromCharCode(...new Uint8Array(await crypto.subtle.sign({ name: "Ed25519" }, key, new TextEncoder().encode(base)))));
  return new Response(body, {
    headers: {
      "Content-Type": "application/http-message-signatures-directory+json",
      "Cache-Control": "max-age=86400",
      "Signature-Input": `sig1=${params}`,
      "Signature": `sig1=:${sig}:`,
    },
  });
}
