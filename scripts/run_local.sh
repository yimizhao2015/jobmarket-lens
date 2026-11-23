#!/usr/bin/env bash
# Run the weekly collection on this computer instead of GitHub's servers (some career sites
# block GitHub's data-center addresses). Same steps as .github/workflows/collect.yml:
# restore the private history, collect, rebuild, save the history, push the dashboard.
#
# Needs: python3 (3.10+), git, xz (on a Mac: brew install xz), and the GitHub CLI signed in as the repo owner (gh auth login).
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
if gh release download data -R "$DATA_REPO" -p lens.db.xz -D data --clobber; then
  xz -d -T0 -f data/lens.db.xz
else  # the format used before Nov 30, 2026
  gh release download data -R "$DATA_REPO" -p lens.db.gz -D data --clobber
  gunzip -f data/lens.db.gz
fi
gh release download data -R "$DATA_REPO" -p norm_cache.db.gz -D data --clobber && gunzip -f data/norm_cache.db.gz || true

echo "== Collecting (about 1-2 hours)"
python -m collector.run "$@"

echo "== Building dashboard"
python scripts/build_dataset.py

echo "== Saving history to $DATA_REPO"
xz -kf -T0 -6 data/lens.db
gzip -kf data/normalized/postings.csv data/norm_cache.db
gh release upload data -R "$DATA_REPO" data/lens.db.xz data/normalized/postings.csv.gz data/norm_cache.db.gz --clobber
gh release delete-asset data lens.db.gz -R "$DATA_REPO" -y 2>/dev/null || true

echo "== Publishing dashboard"
git add -A -- web/index.html web/postings web/downloads config/
git commit -m "Data refresh $(date -u +%F) (local run)" || echo "nothing to commit"
git pull --rebase -X theirs origin main
git push
echo "== Done. The site redeploys within a few minutes."
