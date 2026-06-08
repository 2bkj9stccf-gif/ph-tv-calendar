#!/bin/bash
# Backfill the upcoming "next episodes" into the master catalog (add-only, safe)
# AND record a short read-only note on how Aevum currently auto-starts, so the
# clean launchd auto-start can be set up without recreating the port conflict.
# Writes a transcript to backfill-result.txt (syncs back to Claude).
cd "$(dirname "$0")"
SELF_DIR="$(pwd)"
RESULT_FILE="$SELF_DIR/backfill-result.txt"
exec > >(tee "$RESULT_FILE") 2>&1

echo "Run at: $(date '+%Y-%m-%d %H:%M:%S')  on host: $(hostname)"
echo ""
echo "==================== CALENDAR BACKFILL ===================="
echo "Copying upcoming episodes into the master catalog (add-only)…"
echo
python3 backfill_next_episodes.py

echo ""
echo "==================== AUTO-START RECON (read-only) ===================="
echo "-- LaunchAgent plists and what each launches --"
for pl in "$HOME/Library/LaunchAgents/"*.plist; do
    [ -f "$pl" ] || continue
    echo "  • $(basename "$pl")"
    /usr/libexec/PlistBuddy -c 'Print :ProgramArguments' "$pl" 2>/dev/null \
        | grep -vE '^(Array \{|\})$' | sed 's/^/        /'
done
echo "-- system-wide launchd items mentioning aevum/media --"
ls -1 /Library/LaunchAgents/ /Library/LaunchDaemons/ 2>/dev/null | grep -iE 'aevum|media' | sed 's/^/    /'
echo "-- any Aevum watcher process + its parent chain (how it was launched) --"
WPID="$(pgrep -f 'Aevum/server/main.py' 2>/dev/null | head -1)"
if [ -z "$WPID" ]; then WPID="$(pgrep -f 'main.py --no-watch' 2>/dev/null | head -1)"; fi
p="$WPID"
hops=0
while [ -n "$p" ] && [ "$p" != "1" ] && [ "$p" != "0" ] && [ "$hops" -lt 8 ]; do
    ps -o pid=,ppid=,command= -p "$p" 2>/dev/null | sed 's/^/    /'
    p="$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')"
    hops=$((hops+1))
done
echo "-- login items (apps set to open at login) --"
osascript -e 'tell application "System Events" to get the name of every login item' 2>/dev/null | sed 's/^/    /'

echo ""
echo "Done. Saved to backfill-result.txt in this folder. You can close this window."
