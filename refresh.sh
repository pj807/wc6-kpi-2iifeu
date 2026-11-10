#!/bin/bash
# One command to update the dashboard: pull fresh numbers from GHL, check for private data, publish.
# Run from anywhere:  ./refresh.sh
set -euo pipefail
cd "$(dirname "$0")"
# get the latest version from GitHub first (the daily run commits data there)
if [ -d .git ]; then git pull -q --rebase; fi

echo "1/4 Pulling fresh numbers from GHL (read-only)…"
python3 -I scripts/pull.py

echo "2/4 Privacy check on the files that get published…"
python3 -I scripts/privacy_scan.py index.html data.json summary.json report.txt config.json changelog.json CHANGELOG.md README.md

if [ ! -d .git ]; then
  echo "Updated locally. (No GitHub repo here yet, so nothing was published.)"
  exit 0
fi

echo "3/4 Saving a new version…"
git add index.html data.json summary.json report.txt config.json changelog.json CHANGELOG.md README.md refresh.sh scripts .gitignore .github 2>/dev/null || true
python3 -I scripts/privacy_scan.py   # scans exactly what's staged; stops here if anything private slipped in
if git diff --cached --quiet; then echo "No changes since last update."; exit 0; fi
git commit -q -m "Update numbers $(date '+%Y-%m-%d %H:%M')"

echo "4/4 Publishing to GitHub Pages…"
git push -q
echo "Done. The live page updates within about a minute."
