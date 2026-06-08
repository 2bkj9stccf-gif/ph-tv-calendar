#!/bin/bash
cd "$(dirname "$0")"
echo "Reading your Aevum data (read-only — nothing will be changed)…"
echo
python3 data_health_xray.py
echo
echo "Done — switch back to Claude and paste this whole window."
