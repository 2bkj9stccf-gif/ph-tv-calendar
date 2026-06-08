#!/bin/bash
# Builds your TV calendar from Aevum and publishes it to GitHub so your
# iPhone subscription updates. First run asks once for a GitHub token.
cd "$(dirname "$0")"
REMOTE_HOST="github.com/2bkj9stccf-gif/ph-tv-calendar.git"

if [ ! -d .git ]; then
  echo "── First-time setup ───────────────────────────────"
  echo "Paste your GitHub token below (it stays hidden), then press Return:"
  read -rs TOKEN
  echo
  if [ -z "$TOKEN" ]; then echo "No token entered. Aborting."; exit 1; fi
  git init -q
  git branch -M main
  git remote add origin "https://${TOKEN}@${REMOTE_HOST}"
  git config user.name  "Aevum TV Calendar"
  git config user.email "tv-calendar@localhost"
  printf '.DS_Store\nicloud\n' > .gitignore
fi

echo "Building calendar from Aevum…"
TV_CAL_OUT="$(pwd)/calendar.ics" python3 generate_tv_calendar.py || { echo "Build failed."; exit 1; }

git add -A
git commit -q -m "Update TV calendar $(date +%F)" || echo "(nothing changed)"
echo "Publishing to GitHub…"
git push -q origin main && echo "✅ Published." || echo "❌ Push failed (check token)."
echo "You can close this window."
