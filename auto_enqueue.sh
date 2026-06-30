#!/bin/bash
# Box 2 runner: enqueue newly-aired episodes of the shows you're watching /
# watchlisted into DownloadEngine's queue. Reads the same Aevum DB the TV
# calendar reads. Idempotent — safe to run as often as you like.
#
# It writes PENDING rows into download_queue; DownloadEngine picks them up on
# its normal tick. No git, no network of its own.
cd "$(dirname "$0")" || exit 1

LOG="$HOME/Library/Logs/MediaStack/auto_enqueue.log"
mkdir -p "$(dirname "$LOG")"

PY="/opt/homebrew/bin/python3.11"
[ -x "$PY" ] || PY="$(command -v python3)"

{
  echo "----- $(date '+%Y-%m-%d %H:%M:%S') auto_enqueue ($PY) -----"
  "$PY" auto_enqueue_episodes.py
  echo "----- exit $? -----"
} >> "$LOG" 2>&1
