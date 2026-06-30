#!/bin/bash
# Sets a fresh GitHub token on the repo remote and pushes the already-prepared
# restore commit (calendar.ics + Pages workflow). You paste the token; it is
# read hidden and never displayed.
DIR="/Users/daleschulz/Library/Mobile Documents/com~apple~CloudDocs/Apps/Media/ph-tv-calendar"
cd "$DIR" || { echo "Repo not found: $DIR"; read -r; exit 1; }

echo "──────────────────────────────────────────────────────────"
echo "  Set a fresh GitHub token + publish the TV calendar"
echo "──────────────────────────────────────────────────────────"
echo
echo "Your previous token was corrupted (stored 4x) and was shown in"
echo "plain text earlier, so create a NEW one first:"
echo
echo "  github.com  ->  Settings  ->  Developer settings"
echo "    ->  Fine-grained tokens  ->  Generate new token"
echo "    Repository access: only  2bkj9stccf-gif/ph-tv-calendar"
echo "    Permissions: Contents = Read and write"
echo
printf "Paste the new token, then press Return (input is hidden): "
read -rs TOKEN; echo
if [ -z "$TOKEN" ]; then echo "No token entered - stopping."; read -r; exit 1; fi

git remote set-url origin "https://${TOKEN}@github.com/2bkj9stccf-gif/ph-tv-calendar.git"
unset TOKEN
echo "Remote updated with the new token. Pushing..."
echo

if git push origin main; then
    echo
    echo "✅ Pushed. The 'Deploy calendar to Pages' Action will now enable"
    echo "   GitHub Pages and publish the calendar (about 1 minute)."
else
    echo
    echo "⚠ Push was refused. Make sure the token has Contents = Read and write"
    echo "   on the 2bkj9stccf-gif/ph-tv-calendar repository, then run this again."
fi
echo
echo "Watch the deploy:  https://github.com/2bkj9stccf-gif/ph-tv-calendar/actions"
echo "Live calendar URL: https://2bkj9stccf-gif.github.io/ph-tv-calendar/calendar.ics"
echo
echo "You can close this window when the Action shows a green check."
read -r
