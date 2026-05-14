#!/bin/bash
# preview.sh — Start HTTP server and open browser
#
# Usage:
#   ./preview.sh [port]          # serve artifacts root
#   ./preview.sh [port] <path>   # serve specific directory
#
# Examples:
#   ./preview.sh
#   ./preview.sh 8080
#   ./preview.sh 8000 ../research/2026-05-14/AAPL-Q2-2026-DataViz

PORT="${1:-8000}"
TARGET="${2:-}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARTIFACTS_DIR="$(dirname "$SCRIPT_DIR")"

if [ -n "$TARGET" ]; then
  SERVE_DIR="$(cd "$TARGET" 2>/dev/null && pwd || echo "$ARTIFACTS_DIR/$TARGET")"
else
  SERVE_DIR="$ARTIFACTS_DIR"
fi

if [ ! -d "$SERVE_DIR" ]; then
  echo "❌ Directory not found: $SERVE_DIR"
  exit 1
fi

echo "🚀 Serving: $SERVE_DIR"
echo "🌐 URL:     http://localhost:$PORT"
echo "   (Ctrl+C to stop)"
echo ""

# Open browser (macOS/Linux)
if command -v xdg-open &>/dev/null; then
  (sleep 0.8 && xdg-open "http://localhost:$PORT") &
elif command -v open &>/dev/null; then
  (sleep 0.8 && open "http://localhost:$PORT") &
fi

cd "$SERVE_DIR" && python3 -m http.server "$PORT"
