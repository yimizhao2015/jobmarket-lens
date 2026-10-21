// /api/buy?product=latest-week|full-archive: starts a Lemon Squeezy checkout for that product. The checkout
// carries a random token; Lemon Squeezy's webhook marks the token paid (lemon-webhook.js), and after payment
// the buyer returns to /api/deliver?token=…, which also appears as the button in the receipt email.
import { PRODUCTS } from "../../lib/products.js";

const VARIANT = { "latest-week": "LEMONSQUEEZY_VARIANT_LATEST", "full-archive": "LEMONSQUEEZY_VARIANT_ARCHIVE" };

export async function onRequestGet({ request, env }) {
  const product = new URL(request.url).searchParams.get("product") || "";
  if (!PRODUCTS[product]) return new Response("Not found", { status: 404 });
  const token = crypto.randomUUID();
  const deliver = new URL(`/api/deliver?token=${token}`, request.url).href;
  const r = await fetch("https://api.lemonsqueezy.com/v1/checkouts", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.LEMONSQUEEZY_API_KEY}`,
      Accept: "application/vnd.api+json",
      "Content-Type": "application/vnd.api+json",
    },
    body: JSON.stringify({ data: {
      type: "checkouts",
      attributes: {
        checkout_data: { custom: { token, product } },
        product_options: { redirect_url: deliver, receipt_link_url: deliver, receipt_button_text: "Download your data" },
      },
      relationships: {
        store: { data: { type: "stores", id: String(env.LEMONSQUEEZY_STORE_ID) } },
        variant: { data: { type: "variants", id: String(env[VARIANT[product]]) } },
      },
    } }),
  });
  if (!r.ok) {
    console.error("checkout failed:", r.status, await r.text());
    return new Response("The checkout could not be opened. Please try again in a minute.", { status: 502 });
  }
  return new Response(null, { status: 303, headers: { Location: (await r.json()).data.attributes.url, "Cache-Control": "no-store" } });
}
