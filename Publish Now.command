#!/bin/bash
# Publishes today's TV calendar to GitHub right now (one-off). The daily job is
# already installed; this just pushes the current build immediately.
cd "$(dirname "$0")"
RESULT="$(pwd)/publish-now-result.txt"
{
echo "Run at: $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
echo "Building + publishing today's calendar…"
bash "$(pwd)/publish_daily.sh"
echo "Push attempted. Verifying what's now live on GitHub…"
sleep 4
RAW="$(curl -fsSL https://raw.githubusercontent.com/2bkj9stccf-gif/ph-tv-calendar/main/calendar.ics 2>/dev/null)"
echo "events live (raw):   $(printf '%s' "$RAW" | grep -c 'BEGIN:VEVENT')"
echo "The Bear live:       $(printf '%s' "$RAW" | grep -c 'The Bear — S5')"
echo "SNW live:            $(printf '%s' "$RAW" | grep -c 'Strange New Worlds — S4E1')"
} | tee "$RESULT"
echo ""
echo "Done. Paste this window back to Claude (or it syncs automatically)."
