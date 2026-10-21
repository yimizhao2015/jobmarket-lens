// Lemon Squeezy webhook (order_created, order_refunded). Signed with LEMONSQUEEZY_WEBHOOK_SECRET; a paid
// order marks its checkout token paid for 30 days, so the buyer can download from the receipt link again.
import { store } from "../../lib/counter.js";
import { PRODUCTS } from "../../lib/products.js";

const DAYS = 30;

async function signed(secret, body, signature) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body)));
  const hex = [...mac].map(b => b.toString(16).padStart(2, "0")).join("");
  return signature.length === hex.length && crypto.subtle.timingSafeEqual
    ? crypto.subtle.timingSafeEqual(new TextEncoder().encode(hex), new TextEncoder().encode(signature))
    : hex === signature;
}

export async function onRequestPost({ request, env }) {
  const body = await request.text();
  if (!env.LEMONSQUEEZY_WEBHOOK_SECRET) return new Response("LEMONSQUEEZY_WEBHOOK_SECRET is not set on the Worker", { status: 500 });
  if (!(await signed(env.LEMONSQUEEZY_WEBHOOK_SECRET, body, request.headers.get("x-signature") || "")))
    return new Response("Bad signature", { status: 401 });
  const event = JSON.parse(body);
  const { token, product } = event.meta?.custom_data || {};
  if (!token || !PRODUCTS[product]) return new Response("ignored");
  const db = store(env);
  if (event.meta.event_name === "order_created" && event.data?.attributes?.status === "paid") {
    await db.redis([["SET", `paid:${token}`, product, "EX", DAYS * 86400], ["INCR", `sold:${product}:total`]]);
  } else if (event.meta.event_name === "order_refunded") {
    await db.redis([["DEL", `paid:${token}`]]);
  }
  return new Response("ok");
}
