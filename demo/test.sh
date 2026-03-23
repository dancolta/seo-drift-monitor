#!/bin/bash
# SEO Drift Monitor — Demo Test Script
#
# Starts a local server, baselines the "good" page, swaps to the "broken"
# page, runs a check, and opens the drift report.
#
# Usage: ./demo/test.sh

set -e

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$(cd "$DEMO_DIR/../scripts" && pwd)"
PORT=8111
SERVE_DIR="$DEMO_DIR/serve"

# Clean up on exit
cleanup() {
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    rm -rf "$SERVE_DIR"
}
trap cleanup EXIT

echo "=== SEO Drift Monitor — Demo ==="
echo ""

# 1. Prepare serve directory with the "good" version
mkdir -p "$SERVE_DIR"
cp "$DEMO_DIR/good.html" "$SERVE_DIR/index.html"

# 2. Start local HTTP server
echo "[1/4] Starting local server on port $PORT..."
cd "$SERVE_DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1 > /dev/null 2>&1 &
SERVER_PID=$!
sleep 1

# Verify server is running
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "ERROR: Failed to start server on port $PORT"
    exit 1
fi
echo "      Server running (PID: $SERVER_PID)"
echo ""

# 3. Run baseline on the "good" page
echo "[2/4] Baselining the optimized page..."
echo ""
cd "$SCRIPTS_DIR/.."
python3 scripts/baseline.py "http://localhost:$PORT" --skip-cwv
echo ""

# 4. Swap to the "broken" version
echo "[3/4] Simulating a deploy that breaks SEO elements..."
cp "$DEMO_DIR/broken.html" "$SERVE_DIR/index.html"
echo "      - Organization schema removed"
echo "      - H1 removed (changed to H2)"
echo "      - Title changed to generic text"
echo "      - Description changed to vague copy"
echo "      - noindex added to robots"
echo "      - Canonical tag removed"
echo "      - OG tags partially removed"
echo ""

# 5. Run check
echo "[4/4] Running drift check..."
echo ""
RESULT=$(python3 scripts/check.py "http://localhost:$PORT" --skip-cwv)
echo "$RESULT"

# 6. Open the report
REPORT_PATH=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('report_path',''))" 2>/dev/null)
if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
    echo ""
    echo "=== Opening report in browser ==="
    open "$REPORT_PATH"
fi

echo ""
echo "=== Demo complete ==="
