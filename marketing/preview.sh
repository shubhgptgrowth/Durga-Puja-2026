#!/usr/bin/env bash
# Renders the redesign for review into preview/ (served at /kit/preview/ by deploy; nothing is posted):
#   preview/carousels/   every carousel, a real photo on each slide
#   preview/posts/       Wave 1 posts and stories in the same look
#   preview/kit/         the daily kit post and story cards
#   preview/reels/<d>/   the daily reels and stories for each date given (voiceover, hard cuts)
#   preview/index.html   one page to review it all
# Usage: bash marketing/preview.sh "2026-10-06 2026-10-07"
set -u
DATES="${1:-}"
SITE=$(python -c "from marketing.kit import SITE; print(SITE)")
mkdir -p preview
python -m marketing.carousels --out preview/carousels --photos && node marketing/carousels.mjs preview/carousels \
  || echo "::warning::carousels not rendered"
python -m marketing.posts --out preview/posts && SPEC=posts.json node marketing/carousels.mjs preview/posts \
  || echo "::warning::posts not rendered"
python -m marketing.kit --out preview/kit && node marketing/render.mjs preview/kit \
  || echo "::warning::kit cards not rendered"
for d in $DATES; do
  [ -f "marketing/daily/$d.json" ] || { echo "::warning::no plan for $d"; continue; }
  python -m marketing.footage.factory "$d" --catalog catalog/catalog.json --out "preview/reels/$d" \
    --base-url "${SITE}kit/preview/reels/$d/" || echo "::warning::reels for $d not rendered"
done
python -m marketing.preview_page preview
