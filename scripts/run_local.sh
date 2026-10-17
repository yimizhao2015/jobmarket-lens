#!/usr/bin/env bash
# Run the weekly collection on this computer instead of GitHub's servers (some career sites
# block GitHub's data-center addresses). Same steps as .github/workflows/collect.yml:
# restore the private history, collect, rebuild, save the history, push the dashboard.
#
# Needs: python3 (3.10+), git, and the GitHub CLI signed in as the repo owner (gh auth login).
# Usage, from the repo folder:  caffeinate -i ./scripts/run_local.sh   (caffeinate keeps a Mac awake)
set -euo pipefail
cd "$(dirname "$0")/.."
DATA_REPO=yimizhao2015/jobmarket-lens-data

echo "== Updating code"
git pull --rebase origin main

echo "== Python environment"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt

echo "== Restoring history from $DATA_REPO"
mkdir -p data
gh release download data -R "$DATA_REPO" -p lens.db.gz -D data --clobber
gunzip -f data/lens.db.gz

echo "== Collecting (about 1-2 hours)"
python -m collector.run "$@"

echo "== Building dashboard"
python scripts/build_dataset.py

echo "== Saving history to $DATA_REPO"
gzip -kf data/lens.db data/normalized/postings.csv
gh release upload data -R "$DATA_REPO" data/lens.db.gz data/normalized/postings.csv.gz --clobber

echo "== Publishing dashboard"
git add -A -- web/index.html config/ "data/data source.csv" "data/Job postings"
git commit -m "Data refresh $(date -u +%F) (local run)" || echo "nothing to commit"
git pull --rebase -X theirs origin main
git push
echo "== Done. The site redeploys within a few minutes."
