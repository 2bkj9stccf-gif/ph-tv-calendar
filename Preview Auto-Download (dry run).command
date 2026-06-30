#!/bin/bash
# SAFE PREVIEW — shows which episodes the auto-downloader WOULD grab right now,
# without queueing anything. Run this first to sanity-check before enabling the
# schedule. Reads the live Aevum DB read-only.
cd "$(dirname "$0")"
RESULT="$(pwd)/auto-download-preview.txt"
PY="/opt/homebrew/bin/python3.11"
[ -x "$PY" ] || PY="$(command -v python3)"
{
  echo "Dry run at: $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
  echo "Nothing will be downloaded — this only reports what would be queued."
  echo ""
  AUTO_DL_DRY_RUN=1 "$PY" auto_enqueue_episodes.py
} | tee "$RESULT"
echo ""
echo "Done. If the list looks right, run \"Setup Auto-Download Schedule.command\"."
