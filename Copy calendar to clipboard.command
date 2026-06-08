#!/bin/bash
cd "$(dirname "$0")"
if [ ! -f calendar.ics ]; then echo "calendar.ics not found — run 'Build My TV Calendar' first."; exit 1; fi
pbcopy < calendar.ics
echo "✅ Calendar copied to clipboard ($(wc -l < calendar.ics) lines)."
echo "Now switch back to Claude and say 'copied'. You can close this window."
