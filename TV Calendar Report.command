#!/bin/bash
cd "$(dirname "$0")"
echo "Checking what your TV calendar catches…"
echo
python3 tv_report.py
echo
echo "Done — switch back to Claude and paste this whole window."
