// /api/download?file=sample counts one download, then sends the file. A counting failure never blocks it.
import { FILES, store, today } from "../../lib/counter.js";

export async function onRequestGet({ request, env }) {
  const file = new URL(request.url).searchParams.get("file") || "";
  const path = FILES[file];
  if (!path) return new Response("Not found", { status: 404 });
  const db = store(env);
  if (db.configured) {
    try {
      await db.redis([["INCR", `dl:${file}:total`], ["INCR", `dl:${file}:${today()}`]]);
    } catch (e) {
      console.error("download count failed:", e.message);
    }
  }
  return new Response(null, { status: 302, headers: { Location: path, "Cache-Control": "no-store" } });
}
