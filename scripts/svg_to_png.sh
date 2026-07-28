#!/usr/bin/env bash
# Convert all SVG cards to PNG (Telegram cannot render SVG in messages).
# Requires one of: rsvg-convert (best quality), inkscape, or ImageMagick convert.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/assets/svg"
DST="$ROOT/assets/png"
SIZE="${1:-512}"
mkdir -p "$DST"

for f in "$SRC"/*.svg; do
  name="$(basename "$f" .svg)"
  out="$DST/$name.png"
  if command -v rsvg-convert >/dev/null; then
    rsvg-convert -w "$SIZE" -h "$SIZE" --keep-aspect-ratio "$f" -o "$out"
  elif command -v inkscape >/dev/null; then
    inkscape "$f" --export-type=png --export-width="$SIZE" -o "$out" >/dev/null 2>&1
  else
    convert -background white -density 300 "$f" -resize "${SIZE}x${SIZE}" "$out"
  fi
done
echo "OK: $(ls "$DST" | wc -l) PNG files in assets/png ($SIZE px)"
