// Paid downloads: the zips are assets of the "data" release in the private data repo, replaced on every
// weekly run. GITHUB_DATA_TOKEN (a Worker secret: a fine-grained token with read-only Contents access to
// that repo) lets the Worker ask GitHub for a short-lived download link to the current file.
const DATA_REPO = "yimizhao2015/jobmarket-lens-data";

export const PRODUCTS = {
  "latest-week": { asset: "jobmarketlens-latest-week.zip", name: "Latest Week Snapshot" },
  "full-archive": { asset: "jobmarketlens-full-archive.zip", name: "Full Archive" },
};

const gh = (env, path, accept = "application/vnd.github+json") =>
  fetch(`https://api.github.com/repos/${DATA_REPO}${path}`, {
    headers: { Authorization: `Bearer ${env.GITHUB_DATA_TOKEN}`, Accept: accept, "User-Agent": "jobmarketlens-downloads" },
    redirect: "manual",
  });

// Returns a GitHub download link for the product's zip, valid for a few minutes.
export async function downloadLink(env, product) {
  const asset = PRODUCTS[product]?.asset;
  if (!asset) throw new Error(`unknown product ${product}`);
  const rel = await gh(env, "/releases/tags/data");
  if (!rel.ok) throw new Error(`GitHub release ${rel.status}`);
  const found = (await rel.json()).assets.find(a => a.name === asset);
  if (!found) throw new Error(`${asset} not in the release`);
  const r = await gh(env, `/releases/assets/${found.id}`, "application/octet-stream");
  const link = r.headers.get("location");
  if (!link) throw new Error(`GitHub asset ${r.status}`);
  return link;
}
