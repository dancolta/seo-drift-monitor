#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/seo-drift"
DATA_DIR="$HOME/.claude/seo-drift"

echo "Uninstalling SEO Drift Monitor..."

if [ -d "$SKILL_DIR" ]; then
    rm -rf "$SKILL_DIR"
    echo "  Removed $SKILL_DIR"
else
    echo "  Skill directory not found (already removed?)"
fi

read -rp "Remove stored baselines and reports ($DATA_DIR)? [y/N] " answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    rm -rf "$DATA_DIR"
    echo "  Removed $DATA_DIR"
else
    echo "  Kept $DATA_DIR"
fi

echo "Done."
