import { onRequestGet as __api_download_js_onRequestGet } from "/home/user/jobmarket-lens/functions/api/download.js"
import { onRequestGet as __api_stats_js_onRequestGet } from "/home/user/jobmarket-lens/functions/api/stats.js"

export const routes = [
    {
      routePath: "/api/download",
      mountPath: "/api",
      method: "GET",
      middlewares: [],
      modules: [__api_download_js_onRequestGet],
    },
  {
      routePath: "/api/stats",
      mountPath: "/api",
      method: "GET",
      middlewares: [],
      modules: [__api_stats_js_onRequestGet],
    },
  ]