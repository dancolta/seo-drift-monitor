#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/seo-drift"

echo "Installing SEO Drift Monitor..."

# Create skill directory
mkdir -p "$SKILL_DIR/scripts"

# Copy files
cp -f SKILL.md "$SKILL_DIR/"
cp -f README.md "$SKILL_DIR/"
cp -f requirements.txt "$SKILL_DIR/"
cp -f scripts/*.py "$SKILL_DIR/scripts/"

# Install Python dependencies
pip3 install -q -r "$SKILL_DIR/requirements.txt"

# Install Playwright Chromium (for PDF generation)
python3 -m playwright install chromium 2>/dev/null || echo "  [WARN] Playwright chromium install skipped (optional, for PDF reports)"

echo "Installed to $SKILL_DIR"
echo ""
echo "Set your PageSpeed Insights API key:"
echo "  export PSI_API_KEY=\"your-api-key-here\""
echo ""
echo "Done. Claude Code will auto-discover the skill."
