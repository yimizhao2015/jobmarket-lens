// /api/deliver?token=…: once Lemon Squeezy has confirmed the payment, sends the buyer the current zip.
// The buyer can arrive a moment before the webhook does, so until then the page waits and retries.
import { store, today } from "../../lib/counter.js";
import { PRODUCTS, downloadLink } from "../../lib/products.js";

const page = (title, text, refresh) => new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">${refresh ? '<meta http-equiv="refresh" content="3">' : ""}
<title>${title} | JobMarket Lens</title><link rel="stylesheet" href="/site.css"></head><body><div class="page">
<header class="site-head"><a class="brand" href="/">JobMarket <span>Lens</span></a></header>
<article><h1>${title}</h1><p>${text}</p></article></div></body></html>`,
  { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });

export async function onRequestGet({ request, env }) {
  const token = new URL(request.url).searchParams.get("token") || "";
  if (!/^[0-9a-f-]{36}$/.test(token)) return page("Link not valid", 'This download link is not valid. Please <a href="/contact">contact us</a> with your order number.');
  const db = store(env);
  const [product] = await db.redis([["GET", `paid:${token}`]]);
  if (!product) return page("Confirming your payment…", "This page refreshes on its own. If it keeps waiting, use the download button in your receipt email, or <a href=\"/contact\">contact us</a>.", true);
  try {
    const link = await downloadLink(env, product);
    await db.redis([["INCR", `dl:${product}:total`], ["INCR", `dl:${product}:${today()}`]]).catch(() => {});
    return new Response(null, { status: 302, headers: { Location: link, "Cache-Control": "no-store" } });
  } catch (e) {
    console.error("delivery failed:", e.message);
    return page("Download not ready", 'The file could not be fetched just now. Please try again in a minute, or <a href="/contact">contact us</a> with your order number.');
  }
}
