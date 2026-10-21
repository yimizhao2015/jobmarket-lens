// /api/stats: download counts for the admin area. The caller must send a GitHub token that can write to
// the site repo (the same token used to sign in to /admin), so only site editors can read the counts.
import { FILES, store, today } from "../../lib/counter.js";

const REPO = "yimizhao2015/jobmarket-lens";
const DAYS = 30;

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });

async function canEdit(token) {
  const r = await fetch(`https://api.github.com/repos/${REPO}`, {
    headers: { Authorization: `Bearer ${token}`, "User-Agent": "jobmarketlens-stats", Accept: "application/vnd.github+json" },
  });
  return r.ok && Boolean((await r.json()).permissions?.push);
}

export async function onRequestGet({ request, env }) {
  const token = (request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (!token || !(await canEdit(token))) return json({ error: "Sign in with a GitHub token that can edit the site." }, 401);
  const db = store(env);
  if (!db.configured) return json({ error: "The download counter has no database yet: add the Upstash variables to the Cloudflare Pages project." }, 503);

  const days = [];
  for (let i = DAYS - 1; i >= 0; i--) days.push(today(new Date(Date.now() - i * 864e5)));
  const out = {};
  for (const file of Object.keys(FILES)) {
    const [total, ...daily] = await db.redis([["GET", `dl:${file}:total`], ...days.map(d => ["GET", `dl:${file}:${d}`])]);
    out[file] = { total: +total || 0, days: days.map((d, i) => ({ date: d, count: +daily[i] || 0 })) };
  }
  return json({ since: "2026-10-19", files: out });
}
