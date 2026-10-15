"""Collect postings from each company's official career site.

    python -m collector.run                     # all companies
    python -m collector.run --only NVDA,AMZN    # a subset
    python -m collector.run --max 200           # cap per company

Writes data/raw/<run_date>/<TICKER>.jsonl and data/raw/<run_date>/run_log.json, then
updates data/lens.db so every posting carries first_seen / last_seen across runs.
"""
import argparse
import json
import sys
import time
import traceback
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
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config/companies.json").read_text())
    col = cfg["collection"]
    max_jobs = args.max or col["max_postings_per_company"]
    only = set(args.only.split(",")) if args.only else None
    out = ROOT / "data/raw" / args.date
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "run_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}

    for c in cfg["companies"]:
        t = c["ticker"]
        if only and t not in only:
            continue
        entry = {"ticker": t, "name": c["name"], "adapter": c["adapter"], "career_site": c["career_site"],
                 "started": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        fn = ADAPTERS.get(c["adapter"])
        if fn is None:
            entry.update(status="not_applicable", detail=c.get("known_issue"), collected=0)
            log[t] = entry
            print(f"[{t}] skipped: {entry['detail']}")
            continue
        http = Http(col["user_agent"], col["request_delay_seconds"], col["respect_robots_txt"])
        stats, n, t0 = {}, 0, time.time()
        try:
            with open(out / f"{t}.jsonl", "w") as f:
                for rec in fn(t, c["params"], http, max_jobs, stats):
                    rec["collected_at"] = args.date
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
                    if n % 50 == 0:
                        print(f"[{t}] {n} postings", flush=True)
            entry["status"] = "ok" if n else "empty"
        except BlockedError as e:
            entry.update(status="blocked", detail=str(e))
        except Exception as e:
            entry.update(status="error", detail=f"{type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stderr)
        entry.update(collected=n, seconds=round(time.time() - t0), **stats)
        log[t] = entry
        print(f"[{t}] {entry['status']}: {n} postings {entry.get('detail', '')}", flush=True)
        log_path.write_text(json.dumps(log, indent=2))

    log_path.write_text(json.dumps(log, indent=2))
    store.ingest_run(ROOT, args.date)
    print("run log:", log_path)


if __name__ == "__main__":
    main()
