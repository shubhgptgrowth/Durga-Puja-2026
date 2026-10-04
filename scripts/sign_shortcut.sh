#!/usr/bin/env bash
# Sign the "Pujo steps" Shortcut on a Mac that is signed into iCloud, and put it where the app links to it.
#   scripts/sign_shortcut.sh        then commit app/shortcut/pujo-steps.shortcut and push
set -euo pipefail
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
python3 scripts/make_shortcut.py "$tmp/unsigned.shortcut"
mkdir -p app/shortcut
shortcuts sign --mode anyone --input "$tmp/unsigned.shortcut" --output app/shortcut/pujo-steps.shortcut
# Point the app's "Add the Shortcut" button at it.
sed -i '' "s|healthShortcut: '[^']*'|healthShortcut: 'shortcut/pujo-steps.shortcut'|" app/config.js
echo "Signed: app/shortcut/pujo-steps.shortcut, and app/config.js now links to it. Commit both and push."

