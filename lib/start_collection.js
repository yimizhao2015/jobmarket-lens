// Starts the weekly collection (GitHub Actions collect.yml) from the Worker's Monday cron (written MON: in Cloudflare's cron format 1 is Sunday), because GitHub's own
// schedule can start hours late. Cloudflare crons are in UTC, so two are set (06:17 and 07:17 UTC) and only the
// one that is 2:17 a.m. in New York goes ahead. Needs the GITHUB_ACTIONS_TOKEN secret: a fine-grained token on
// yimizhao2015/jobmarket-lens with Actions: Read and write.
const REPO = "yimizhao2015/jobmarket-lens";

export async function startCollection(env, now = new Date()) {
  const ny = (opts) => new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", ...opts }).format(now);
  const day = ny({ weekday: "short" }), hour = ny({ hour: "numeric", hourCycle: "h23" });
  if (day !== "Mon" || Number(hour) !== 2) return `skipped: ${day} ${hour}:00 in New York`;
  if (!env.GITHUB_ACTIONS_TOKEN) throw new Error("GITHUB_ACTIONS_TOKEN is not set on the Worker");
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/collect.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_ACTIONS_TOKEN}`, Accept: "application/vnd.github+json",
      "User-Agent": "jobmarket-lens-worker", "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  if (r.status !== 204) throw new Error(`GitHub ${r.status}: ${await r.text()}`);
  return "started";
}
