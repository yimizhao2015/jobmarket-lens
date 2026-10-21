// Builds the text pages from the Markdown in content/ (edited in /admin): About, Methodology, Privacy,
// the Insights index and every Insights article. Runs on each Cloudflare deploy (npm run build) and locally.
import { readFileSync, writeFileSync, readdirSync, mkdirSync, rmSync, existsSync } from "node:fs";
import { join, basename } from "node:path";
import { load } from "js-yaml";
import { marked } from "marked";

const ROOT = new URL("..", import.meta.url).pathname;
const SITE = "https://www.jobmarketlens.com";

const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function read(path) {
  const text = readFileSync(path, "utf8");
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) throw new Error(`${path}: missing front matter`);
  return { ...load(m[1]), body: m[2] };
}

// "2026-10-18" (string or YAML date) -> { iso: "2026-10-18", long: "October 18, 2026" }
function day(v) {
  const iso = v instanceof Date ? v.toISOString().slice(0, 10) : String(v).slice(0, 10);
  const long = new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
  return { iso, long };
}

// Markdown -> HTML; the first paragraph becomes the lede.
function render(md, lede) {
  const html = marked.parse(md, { gfm: true });
  return lede ? html.replace(/<p>/, '<p class="lede">') : html;
}

// Header: the main sections. Footer: the same plus Contact Us. /about/* highlights About.
const NAV = [["/", "Dashboard"], ["/insights", "Insights"], ["/about", "About"], ["/data", "Get the Data"]];
const FOOT = [...NAV, ["/contact", "Contact Us"]];
const links = (list, current, section) => list.map(([h, l]) => `<a href="${h}"${h === "/data" ? ' class="cta"' : ""}${
  h === current || h === section ? ' aria-current="page"' : ""}>${l}</a>`).join("");
const nav = current => links(NAV, current, current.startsWith("/about") ? "/about" : current.startsWith("/insights") ? "/insights" : "");
const foot = current => links(FOOT, current, "");

function page({ title, description, path, current, og, article, share, contact }) {
  const url = SITE + path;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${esc(title)} | JobMarket Lens</title>
<meta name="description" content="${esc(description)}">
<link rel="canonical" href="${url}">
${og ? `<meta property="og:type" content="${og}">
<meta property="og:site_name" content="JobMarket Lens">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${url}">
<meta name="twitter:card" content="summary">
` : ""}<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/site.css">
</head>
<body>
<div class="page">
  <header class="site-head">
    <a class="brand" href="/">JobMarket <span>Lens</span></a>
    <nav class="site-nav" aria-label="Site">${nav(current)}</nav>
  </header>
  <article>
${article}
  </article>
  <footer class="site-foot">
    <nav aria-label="Footer">${foot(current)}</nav>
    © 2026 JobMarket Lens. All rights reserved.
  </footer>
</div>
${contact ? '<script src="/contact.js"></script>\n' : ""}${share ? '<script src="/share.js"></script>\n' : ""}</body>
</html>
`;
}

const out = (rel, html) => { const p = join(ROOT, "web", rel); mkdirSync(join(p, ".."), { recursive: true }); writeFileSync(p, html); };

// About section: About, Methodology and Privacy, with tabs between them
const ABOUT = [["about", "/about", "About"], ["methodology", "/about/methodology", "Methodology"], ["privacy", "/about/privacy", "Privacy"]];
for (const [name, path] of ABOUT) {
  const d = read(join(ROOT, "content/pages", name + ".md"));
  const tabs = `    <nav class="tabs" aria-label="About">${ABOUT.map(([, h, l]) => `<a href="${h}"${h === path ? ' aria-current="page"' : ""}>${l}</a>`).join("")}</nav>\n`;
  out(path.slice(1) + ".html", page({
    title: d.page_title || d.title, description: d.description, path, current: path,
    article: tabs + `    <h1>${esc(d.title)}</h1>\n` + (d.dateline ? `    <p class="dateline">${esc(d.dateline)}</p>\n` : "") + render(d.body, !d.dateline),
  }));
}
for (const old of ["methodology.html", "privacy.html"]) rmSync(join(ROOT, "web", old), { force: true });   // now under /about/

// Contact Us: intro text, then the form (web/contact.js)
{
  const d = read(join(ROOT, "content/pages/contact.md"));
  out("contact.html", page({
    title: d.page_title || d.title, description: d.description, path: "/contact", current: "/contact", contact: true,
    article: `    <h1>${esc(d.title)}</h1>\n` + render(d.body, true) + `    <div class="contact"></div>`,
  }));
}

// Get the Data: the plans as cards; a plan without a checkout link shows its button as coming soon
{
  const d = read(join(ROOT, "content/pages/data.md"));
  const card = p => `      <li class="plan">
        <h2>${esc(p.name)}</h2>
        <p class="price">${esc(p.price)}</p>
        <ul>${(p.features || []).map(f => `<li>${esc(f)}</li>`).join("")}</ul>
        ${p.link ? `<a class="plan-btn" href="${esc(p.link)}"${/^\/(downloads\/|api\/download)/.test(p.link)
                   // a file download is not a page view: /api/download counts it for /admin/stats
                   ? " download" : ""}>${esc(p.button)}</a>`
                 : `<span class="plan-btn off" aria-disabled="true">${esc(p.button)}</span><span class="soon">Coming soon</span>`}
      </li>`;
  out("data.html", page({
    title: d.page_title || d.title, description: d.description, path: "/data", current: "/data", og: "website",
    article: `    <h1>${esc(d.title)}</h1>\n` + (d.intro ? `    <p class="lede">${esc(d.intro)}</p>\n` : "") +
      `    <ul class="plans">\n${(d.plans || []).map(card).join("\n")}\n    </ul>\n` + render(d.body, false),
  }));
}

// Insights articles, newest first; drafts are left out
const dir = join(ROOT, "content/insights");
const articles = readdirSync(dir).filter(f => f.endsWith(".md")).map(f => ({ slug: basename(f, ".md"), ...read(join(dir, f)) }))
  .filter(a => !a.draft).map(a => ({ ...a, day: day(a.date) })).sort((a, b) => b.day.iso.localeCompare(a.day.iso) || a.slug.localeCompare(b.slug));

const insightsDir = join(ROOT, "web/insights");
if (existsSync(insightsDir)) rmSync(insightsDir, { recursive: true });   // so a deleted article disappears from the site
for (const a of articles) {
  const byline = `${a.day.long} · By ${a.author || "JobMarketLens Reviews"}`;
  out(`insights/${a.slug}.html`, page({
    title: a.title, description: a.description || a.summary, path: `/insights/${a.slug}`, current: `/insights/${a.slug}`, og: "article", share: true,
    article: `    <h1>${esc(a.title)}</h1>\n    <p class="byline">${esc(byline)}</p>\n    <div class="share"></div>\n` +
      render(a.body, true) + `    <div class="share end"></div>`,
  }));
}

// Insights index
const idx = read(join(ROOT, "content/pages/insights.md"));
out("insights/index.html", page({
  title: idx.page_title || idx.title, description: idx.description, path: "/insights", current: "/insights", og: "website",
  article: `    <h1>${esc(idx.title)}</h1>\n` + render(idx.body, true) + `    <ul class="cards">\n` +
    articles.map(a => `      <li><a href="/insights/${a.slug}">${esc(a.title)}</a><br>
        <span class="dateline">${esc(a.day.long)} · By ${esc(a.author || "JobMarketLens Reviews")}</span><br>
        ${esc(a.summary || a.description)}</li>`).join("\n") + `\n    </ul>`,
}));

console.log(`Built 4 pages, the Insights index and ${articles.length} article(s).`);
