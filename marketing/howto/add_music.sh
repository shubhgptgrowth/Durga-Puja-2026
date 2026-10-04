#!/usr/bin/env bash
# Adds a licence-safe dhak bed to the composed how-to reels (compose.mjs writes them silent).
#   bash marketing/howto/add_music.sh <outDir>      # reads <outDir>/reels/*.mp4, writes <outDir>/reels-music/howto-*.mp4
# Music: "Rhythm of Dhak", Sumita Roy Dutta, CC BY-SA 4.0 (Wikimedia Commons). Credit it in the caption.
# Each reel starts at a different point in the recording so consecutive posts don't sound identical.
set -euo pipefail
out=${1:-howto-out}; mkdir -p "$out/reels-music"
dhak="$out/dhak.mp3"
[ -s "$dhak" ] || curl -sfL -A "PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026)" -o "$dhak" \
  "https://upload.wikimedia.org/wikipedia/commons/0/04/Rhythm_of_Dhak_a_huge_membranophone_instrument_from_Bengal_and_Assam%2C_used_in_Hindu_religious_festivals%2C_especially_Durga_Puja.mp3"
i=0
for f in "$out"/reels/*.mp4; do
  b=$(basename "$f" .mp4); d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f"); s=$((10 + i * 13)); i=$((i + 1))
  ffmpeg -v error -y -i "$f" -ss "$s" -i "$dhak" -filter_complex \
    "[1:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:$d,afade=t=in:d=0.6,afade=t=out:st=$(python3 -c "print($d-2)"):d=2,loudnorm=I=-15:TP=-1.5[a]" \
    -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k -shortest -movflags +faststart "$out/reels-music/howto-$b.mp4"
  echo "howto-$b.mp4"
done
