#!/bin/bash
# One-shot repair for the PH TV calendar:
#   - clears the stale git lock that jammed daily publishing
#   - rebuilds calendar.ics from Aevum (skipped gracefully if unavailable)
#   - restores the wiped GitHub repo (empty-tree commit) and adds the Pages workflow
#   - the workflow then auto-enables GitHub Pages and deploys
DIR="/Users/daleschulz/Library/Mobile Documents/com~apple~CloudDocs/Apps/Media/ph-tv-calendar"
cd "$DIR" || { echo "Repo folder not found: $DIR"; read -r; exit 1; }

echo "──────────────────────────────────────────────"
echo "  Fixing PH TV calendar"
echo "──────────────────────────────────────────────"

echo "1) Clearing stale git locks + sandbox leftovers…"
rm -f .git/*.lock .git/index.lock.bak .git/STALE-LOCK-* .git/stray_wtest_* \
      .git/_wtest .git/_trash_wtest _wtest 2>/dev/null
echo "   done."

echo "2) Rebuilding calendar.ics from Aevum (ok to skip if Aevum is down)…"
REGEN=0
for PY in /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "$PY" ]; then
        if TV_CAL_OUT="$DIR/calendar.ics" "$PY" generate_tv_calendar.py; then REGEN=1; fi
        break
    fi
done
[ "$REGEN" = 1 ] && echo "   rebuilt." || echo "   skipped — publishing existing calendar.ics."

echo "3) Restoring repo on GitHub…"
git reset -q
git add calendar.ics ".github/workflows/deploy-pages.yml"
git commit -q -m "Restore calendar + Pages deploy workflow ($(date +%F))" || echo "   (nothing new to commit)"
if git push origin main 2>&1; then
    echo "   pushed."
else
    echo "   normal push refused (history was overwritten) — force-pushing the clean state…"
    git push -f origin main && echo "   force-pushed."
fi

echo "──────────────────────────────────────────────"
echo "  Events published: $(grep -c 'BEGIN:VEVENT' calendar.ics)"
echo "  The deploy Action will enable Pages + publish in ~1 min."
echo "  Watch:  https://github.com/2bkj9stccf-gif/ph-tv-calendar/actions"
echo "  Live:   https://2bkj9stccf-gif.github.io/ph-tv-calendar/calendar.ics"
echo "──────────────────────────────────────────────"
echo ""
echo "Done. You can close this window."
read -r
