// Share buttons for Insights articles: fills every <div class="share"> with copy-link, email and social links.
(function () {
  const url = "https://www.jobmarketlens.com" + location.pathname.replace(/\.html$/, "");
  const title = (document.querySelector("article h1") || document).textContent.trim();
  const u = encodeURIComponent(url), t = encodeURIComponent(title);
  const links = [
    ["Email", `mailto:?subject=${t}&body=${encodeURIComponent(title + "\n\n" + url)}`],
    ["LinkedIn", `https://www.linkedin.com/sharing/share-offsite/?url=${u}`],
    ["Facebook", `https://www.facebook.com/sharer/sharer.php?u=${u}`],
    ["X", `https://x.com/intent/tweet?url=${u}&text=${t}`],
    ["Reddit", `https://www.reddit.com/submit?url=${u}&title=${t}`],
  ];
  document.querySelectorAll(".share").forEach(el => {
    el.innerHTML = `<span class="share-l">Share</span><button type="button" class="share-b">Copy link</button>` +
      links.map(([n, h]) => `<a class="share-b" href="${h}"${n === "Email" ? "" : ' target="_blank" rel="noopener"'}>${n}</a>`).join("");
    const btn = el.querySelector("button");
    btn.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(url); btn.textContent = "Link copied"; }
      catch { prompt("Copy this link:", url); }
      setTimeout(() => btn.textContent = "Copy link", 2000);
    });
  });
})();
