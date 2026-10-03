#!/usr/bin/env bash
# Build the self-hosted vector base map: a Kolkata + Howrah extract of the latest Protomaps
# OpenStreetMap basemap build, as one .pmtiles file the app reads with HTTP range requests.
#   scripts/build_tiles.sh [out_dir]          (default app/tiles; needs curl, jq, network)
# Writes <out_dir>/kolkata-<build>.pmtiles and <out_dir>/kolkata.json (the manifest the app reads).
# MAXZOOM (default 15) trades detail for size; the app over-zooms past it.
set -euo pipefail
out="${1:-app/tiles}"; maxz="${MAXZOOM:-15}"
bbox="88.20,22.36,88.55,22.74"      # pipeline BBOX (88.25–88.50, 22.40–22.70) plus a margin
mkdir -p "$out"

pm="$(command -v pmtiles || true)"
if [ -z "$pm" ]; then
  asset=$(curl -fsSL https://api.github.com/repos/protomaps/go-pmtiles/releases/latest \
    | jq -r '.assets[] | select(.name | test("Linux_x86_64\\.tar\\.gz$")) | .browser_download_url')
  curl -fsSL "$asset" | tar xz -C /tmp pmtiles
  pm=/tmp/pmtiles
fi

build=$(curl -fsSL https://build-metadata.protomaps.dev/builds.json | jq -r '[.[].key] | map(select(endswith(".pmtiles"))) | sort | last')
[ -n "$build" ] && [ "$build" != null ] || { echo "no Protomaps build found" >&2; exit 1; }
name="kolkata-${build%.pmtiles}.pmtiles"
if [ ! -s "$out/$name" ]; then
  rm -f "$out"/kolkata-*.pmtiles
  "$pm" extract "https://build.protomaps.com/$build" "$out/$name" --bbox="$bbox" --maxzoom="$maxz" --download-threads=4
fi
"$pm" show "$out/$name" | head -20 || true   # head closes the pipe early; fine under pipefail
size=$(stat -c %s "$out/$name")
jq -n --arg file "$name" --arg build "${build%.pmtiles}" --argjson maxzoom "$maxz" --argjson bytes "$size" \
  '{file: $file, build: $build, maxzoom: $maxzoom, bytes: $bytes}' > "$out/kolkata.json"
echo "tiles: $out/$name ($((size / 1024 / 1024)) MB, z0–$maxz, build ${build%.pmtiles})"
