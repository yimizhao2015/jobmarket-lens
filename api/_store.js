// Download counts in Upstash Redis (connected to the Vercel project under Storage). The Vercel
// integration sets either the KV_* or the UPSTASH_* variables; without them nothing is counted.
const URL_ = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
const TOKEN = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;

export const configured = Boolean(URL_ && TOKEN);

// Runs several Redis commands in one request; returns their results in order.
export async function redis(commands) {
  const r = await fetch(`${URL_}/pipeline`, {
    method: "POST",
    headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(commands),
  });
  if (!r.ok) throw new Error(`Redis ${r.status}`);
  return (await r.json()).map(x => x.result);
}

// Today's date in New York, as YYYY-MM-DD.
export const today = (d = new Date()) => d.toLocaleDateString("en-CA", { timeZone: "America/New_York" });

export const FILES = { sample: "/downloads/jobmarketlens-sample.csv" };
