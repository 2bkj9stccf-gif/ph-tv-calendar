#!/bin/bash
# Double-click to build your "My Shows" TV calendar from the Aevum database.
cd "$(dirname "$0")"
echo "Building your TV calendar from Aevum…"
echo
TV_CAL_OUT="$(pwd)/calendar.ics" python3 generate_tv_calendar.py
echo
echo "If it printed 'Wrote …', the file 'calendar.ics' is now in this folder."
echo "You can close this window."
