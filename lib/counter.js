// Download counts in Upstash Redis, shared by the Cloudflare Pages functions in functions/api/.
// The UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN variables are set in the Cloudflare Pages project;
// without them nothing is counted.
export const FILES = { sample: "/downloads/jobmarketlens-sample.csv" };

// Today's date in New York, as YYYY-MM-DD.
export const today = (d = new Date()) => d.toLocaleDateString("en-CA", { timeZone: "America/New_York" });

export function store(env) {
  const url = env.UPSTASH_REDIS_REST_URL, token = env.UPSTASH_REDIS_REST_TOKEN;
  return {
    configured: Boolean(url && token),
    // Runs several Redis commands in one request; returns their results in order.
    async redis(commands) {
      const r = await fetch(`${url}/pipeline`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(commands),
      });
      if (!r.ok) throw new Error(`Redis ${r.status}`);
      return (await r.json()).map(x => x.result);
    },
  };
}
