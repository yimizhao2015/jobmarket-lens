// Cloudflare Worker: /api/* goes to the functions in functions/api/; everything else is a static file from web/.
import * as download from "./functions/api/download.js";
import * as stats from "./functions/api/stats.js";

const ROUTES = { "/api/download": download, "/api/stats": stats };

export default {
  async fetch(request, env) {
    const route = ROUTES[new URL(request.url).pathname];
    if (!route) return env.ASSETS.fetch(request);
    if (request.method !== "GET") return new Response("Method not allowed", { status: 405 });
    return route.onRequestGet({ request, env });
  },
};
