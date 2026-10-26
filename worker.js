// Cloudflare Worker: /api/* goes to the functions in functions/api/; everything else is a static file from web/.
// Its Monday cron starts the weekly collection on GitHub (lib/start_collection.js).
import * as buy from "./functions/api/buy.js";
import * as deliver from "./functions/api/deliver.js";
import * as download from "./functions/api/download.js";
import * as lemonWebhook from "./functions/api/lemon-webhook.js";
import * as stats from "./functions/api/stats.js";
import { startCollection } from "./lib/start_collection.js";

const ROUTES = {
  "/api/buy": buy, "/api/deliver": deliver, "/api/download": download,
  "/api/lemon-webhook": lemonWebhook, "/api/stats": stats,
};

export default {
  async fetch(request, env) {
    const route = ROUTES[new URL(request.url).pathname];
    if (!route) return env.ASSETS.fetch(request);
    const handler = request.method === "GET" ? route.onRequestGet : request.method === "POST" ? route.onRequestPost : null;
    if (!handler) return new Response("Method not allowed", { status: 405 });
    return handler({ request, env });
  },
  // Monday cron (wrangler.jsonc triggers): start the weekly collection on time
  async scheduled(event, env) {
    console.log("weekly collection:", await startCollection(env, new Date(event.scheduledTime)));
  },
};
