#!/bin/bash
# Installs + loads the auto-download agent (box 2): enqueues newly-aired
# episodes of the shows you're watching/watchlisted. Runs at login and every 3h.
# Re-run any time to update it.
cd "$(dirname "$0")"
RESULT="$(pwd)/auto-download-setup.txt"
{
  MEDIA_DIR="$(cd .. && pwd)"
  SRC="$MEDIA_DIR/shared/launchd/com.media.autoenqueue.plist"
  DEST="$HOME/Library/LaunchAgents/com.media.autoenqueue.plist"

  echo "Setup at: $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
  if [ ! -f "$SRC" ]; then
    echo "ERROR: template not found at $SRC"; exit 1
  fi
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/MediaStack"

  # Substitute placeholders → real paths.
  sed -e "s#__MEDIA_DIR__#$MEDIA_DIR#g" -e "s#__HOME__#$HOME#g" "$SRC" > "$DEST"

  # Reload cleanly.
  launchctl unload "$DEST" 2>/dev/null
  launchctl load "$DEST" && echo "Loaded com.media.autoenqueue."

  echo "Installed: $DEST"
  echo "Schedule:  at login + every 3 hours"
  echo "Log:       $HOME/Library/Logs/MediaStack/auto_enqueue.log"
  echo ""
  echo "Kicking off one run now…"
  launchctl kickstart -k "gui/$UID/com.media.autoenqueue" 2>/dev/null \
    && echo "Triggered." || bash "$MEDIA_DIR/ph-tv-calendar/auto_enqueue.sh"
} | tee "$RESULT"
echo ""
echo "Done. Paste this window back to Claude if you want me to confirm it took."
