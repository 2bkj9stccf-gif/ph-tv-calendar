#!/bin/bash
cd "$(dirname "$0")"
echo "This merges the legacy 'default' profile onto Dale, then removes it."
echo "It backs up your database first. Press Return to continue, or close to cancel."
read _
python3 cleanup_default_profile.py
echo
echo "Paste this whole window back to Claude."
