#!/bin/bash
# Auto-generated. Rebuilds the TV calendar from the live Aevum database and
# publishes it to GitHub. Robust push: tries a normal push, and if the remote
# has diverged (e.g. an older calendar committed via the web), overwrites it —
# this repo only ever holds the generated calendar.ics, so overwriting is safe.
cd "/Users/daleschulz/Library/Mobile Documents/com~apple~CloudDocs/Apps/Media/ph-tv-calendar" || exit 1
TV_CAL_OUT="/Users/daleschulz/Library/Mobile Documents/com~apple~CloudDocs/Apps/Media/ph-tv-calendar/calendar.ics" "/opt/homebrew/bin/python3.11" generate_tv_calendar.py >> "/Users/daleschulz/Library/Logs/MediaStack/tvcalendar.log" 2>&1 || exit 1
git add calendar.ics
git commit -q -m "Daily TV calendar $(date +%F)" 2>/dev/null
git push -q origin main 2>/dev/null || git push -q -f origin main
