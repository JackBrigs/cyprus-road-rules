#!/usr/bin/env bash
# Convert downloaded SVG sign images (assets/img/*.svg) to PNG for Telegram.
# JPG/PNG originals are used as-is. Requires rsvg-convert or inkscape.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/assets/img"
SIZE="${1:-512}"

shopt -s nullglob
count=0
for f in "$DIR"/*.svg; do
  out="${f%.svg}.png"
  [ -f "$out" ] && continue
  if command -v rsvg-convert >/dev/null; then
    rsvg-convert -w "$SIZE" --keep-aspect-ratio "$f" -o "$out"
  elif command -v inkscape >/dev/null; then
    inkscape "$f" --export-type=png --export-width="$SIZE" -o "$out" >/dev/null 2>&1
  else
    echo "Need rsvg-convert (apt install librsvg2-bin) or inkscape" >&2
    exit 1
  fi
  count=$((count+1))
done
echo "converted $count svg → png in assets/img"
