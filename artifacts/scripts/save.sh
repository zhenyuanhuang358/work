#!/bin/bash
# save.sh — Save a new artifact with auto-organization
#
# Usage:
#   ./save.sh <category> <id> <html-file> [--screenshot] [--pdf]
#
# Example:
#   ./save.sh research NVDA-Q1-2026-Editorial /tmp/nvda.html --screenshot --pdf

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARTIFACTS_DIR="$(dirname "$SCRIPT_DIR")"
DATE=$(date +%Y-%m-%d)

CATEGORY="${1:-research}"
ARTIFACT_ID="${2:-artifact-$(date +%s)}"
SOURCE_HTML="$3"
DO_SCREENSHOT=false
DO_PDF=false

for arg in "$@"; do
  case $arg in
    --screenshot) DO_SCREENSHOT=true ;;
    --pdf)        DO_PDF=true ;;
  esac
done

if [ -z "$SOURCE_HTML" ] || [ ! -f "$SOURCE_HTML" ]; then
  echo "❌ Usage: $0 <category> <id> <html-file> [--screenshot] [--pdf]"
  exit 1
fi

DEST_DIR="$ARTIFACTS_DIR/$CATEGORY/$DATE/$ARTIFACT_ID"
mkdir -p "$DEST_DIR"

# Copy HTML
cp "$SOURCE_HTML" "$DEST_DIR/index.html"
echo "✓ Saved:  $DEST_DIR/index.html"

# Write basic meta if none exists
if [ ! -f "$DEST_DIR/meta.json" ]; then
  cat > "$DEST_DIR/meta.json" <<METAEOF
{
  "id": "$ARTIFACT_ID",
  "title": "$ARTIFACT_ID",
  "category": "$CATEGORY",
  "created": "$DATE",
  "tags": []
}
METAEOF
  echo "✓ Created meta.json"
fi

# Screenshot
if $DO_SCREENSHOT; then
  echo "📸 Taking screenshot..."
  node "$SCRIPT_DIR/screenshot.js" "$DEST_DIR/index.html" "$DEST_DIR/preview.png" --width=1440
fi

# PDF
if $DO_PDF; then
  echo "📄 Exporting PDF..."
  node "$SCRIPT_DIR/pdf.js" "$DEST_DIR/index.html" "$DEST_DIR/export.pdf"
fi

echo ""
echo "🗂  Artifact saved:"
ls -la "$DEST_DIR"
echo ""
echo "📂 Open: file://$DEST_DIR/index.html"
