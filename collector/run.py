"""Collect postings from each company's official career site.

    python -m collector.run                     # all companies
    python -m collector.run --only NVDA,AMZN    # a subset
    python -m collector.run --max 200           # cap per company
    python -m collector.run --workers 48        # companies in parallel (default 48)
    python -m collector.run --full              # re-read every detail page, even for known postings

Writes data/raw/<run_date>/<TICKER>.jsonl and data/raw/<run_date>/run_log.json, then
updates data/lens.db so every posting carries first_seen / last_seen across runs.

Collection is incremental: postings already in data/lens.db are matched in the site's listing and written
as {"source_id", "seen_only": true} lines without requesting their detail pages again. They still count
toward the per-company cap and toward "collected"; "fetched" counts detail pages actually read.
"""
import argparse
import json
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

from collector.adapters import ADAPTERS
from collector.http import BlockedError, Http
from collector import store

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated tickers")
    ap.add_argument("--max", type=int, help="max postings per company (overrides config)")
    ap.add_argument("--date", default=date.today().isoformat(), help="run date label")
    ap.add_argument("--workers", type=int, default=48, help="companies collected in parallel")
    ap.add_argument("--full", action="store_true", help="ignore the history and re-read every detail page")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config/companies.json").read_text())
    col = cfg["collection"]
    max_jobs = args.max or col["max_postings_per_company"]
    only = set(args.only.split(",")) if args.only else None
    out = ROOT / "data/raw" / args.date
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "run_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}

    lock = threading.Lock()
    known, last_collected = store.known_postings(ROOT)
    if args.full:
        known = {}

    def one(c):
        # One Http client (own delay and robots cache) per company, so per-site politeness is unchanged
        # when companies run in parallel.
        t = c["ticker"]
        entry = {"ticker": t, "name": c["name"], "adapter": c["adapter"], "career_site": c["career_site"],
                 "started": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        fn = ADAPTERS.get(c["adapter"])
        if fn is None:
            entry.update(status="not_applicable", detail=c.get("known_issue"), collected=0)
            with lock:
                log[t] = entry
            return
        delay = col.get("request_delay_by_adapter", {}).get(c["adapter"], col["request_delay_seconds"])
        http = Http(col["user_agent"], delay, col["respect_robots_txt"])
        http.known = known.get(t, {})
        http.known_urls = {u: sid for sid, u in http.known.items() if u}
        stats, n, fetched, t0 = {}, 0, 0, time.time()
        try:
            with open(out / f"{t}.jsonl", "w") as f:
                for rec in fn(t, c["params"], http, max_jobs, stats):
                    rec["collected_at"] = args.date
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
                    if not rec.get("seen_only"):
                        fetched += 1
                        # Listings can repeat a posting (Workday pages past the end); read it only once per run.
                        http.known.setdefault(rec["source_id"], rec["url"])
                        if rec["url"]:
                            http.known_urls.setdefault(rec["url"], rec["source_id"])
            entry["status"] = "ok" if n else "empty"
        except BlockedError as e:
            entry.update(status="blocked", detail=str(e))
        except Exception as e:
            entry.update(status="error", detail=f"{type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stderr)
        entry.update(collected=n, fetched=fetched, seconds=round(time.time() - t0), **stats)
        with lock:
            log[t] = entry
            log_path.write_text(json.dumps(log, indent=2))
        print(f"[{t}] {entry['status']}: {n} postings ({fetched} new) {entry.get('detail', '')}", flush=True)

    def last_cost(c):
        # The last successful run's postings (a full cap when there is none yet) times the site's request
        # delay, as a proxy for how long the company takes.
        delay = col.get("request_delay_by_adapter", {}).get(c["adapter"], col["request_delay_seconds"])
        return last_collected.get(c["ticker"], max_jobs) * delay

    # Slowest companies first, so none of them starts near the end of the run.
    todo = sorted((c for c in cfg["companies"] if not only or c["ticker"] in only), key=last_cost, reverse=True)
    # Companies sharing a host group (one platform's firewall) run in their own small pool, alongside the rest.
    groups = col.get("host_groups", {})
    pools = [ThreadPoolExecutor(max_workers=args.workers)]
    pools += [ThreadPoolExecutor(max_workers=g["max_concurrent"]) for g in groups.values()]
    pool_of = dict(zip(groups, pools[1:]))
    futures = [pool_of.get(c.get("host_group"), pools[0]).submit(one, c) for c in todo]
    for fut in futures:
        fut.result()
    for p in pools:
        p.shutdown()

    log_path.write_text(json.dumps(log, indent=2))
    store.ingest_run(ROOT, args.date)
    print("run log:", log_path)


if __name__ == "__main__":
    main()
