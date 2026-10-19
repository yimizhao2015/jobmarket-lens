// /api/download?file=sample counts one download, then sends the file. A counting failure never blocks it.
import { FILES, configured, redis, today } from "./_store.js";

export default async function handler(req, res) {
  const file = String(req.query.file || "");
  const path = FILES[file];
  if (!path) return res.status(404).send("Not found");
  if (configured) {
    try {
      await redis([["INCR", `dl:${file}:total`], ["INCR", `dl:${file}:${today()}`]]);
    } catch (e) {
      console.error("download count failed:", e.message);
    }
  }
  res.setHeader("Cache-Control", "no-store");
  res.redirect(302, path);
}
