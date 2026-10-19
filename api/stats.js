// /api/stats: download counts for the admin area. The caller must send a GitHub token that can write to
// the site repo (the same token used to sign in to /admin), so only site editors can read the counts.
import { FILES, configured, redis, today } from "./_store.js";

const REPO = "yimizhao2015/jobmarket-lens";
const DAYS = 30;

async function canEdit(token) {
  const r = await fetch(`https://api.github.com/repos/${REPO}`, {
    headers: { Authorization: `Bearer ${token}`, "User-Agent": "jobmarketlens-stats", Accept: "application/vnd.github+json" },
  });
  return r.ok && Boolean((await r.json()).permissions?.push);
}

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  const token = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!token || !(await canEdit(token))) return res.status(401).json({ error: "Sign in with a GitHub token that can edit the site." });
  if (!configured) return res.status(503).json({ error: "The download counter has no database yet: connect Upstash Redis to the Vercel project." });

  const days = [];
  for (let i = DAYS - 1; i >= 0; i--) days.push(today(new Date(Date.now() - i * 864e5)));
  const out = {};
  for (const file of Object.keys(FILES)) {
    const [total, ...daily] = await redis([["GET", `dl:${file}:total`], ...days.map(d => ["GET", `dl:${file}:${d}`])]);
    out[file] = { total: +total || 0, days: days.map((d, i) => ({ date: d, count: +daily[i] || 0 })) };
  }
  res.json({ since: "2026-10-19", files: out });
}
