#!/usr/bin/env python3
"""
History viewer for SEO Drift Monitor.

Shows all baselines and checks for a URL.

Usage:
    python history.py <url>
"""

import json
import sys
import os

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from db import get_all_baselines, get_check_history, normalize_url


def get_history(url: str) -> dict:
    """Get all baselines and checks for a URL."""
    normalized = normalize_url(url)
    baselines = get_all_baselines(normalized)
    checks = get_check_history(normalized)
    return {"baselines": baselines, "checks": checks}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python history.py <url>")
        sys.exit(1)

    result = get_history(sys.argv[1])
    print(json.dumps(result, indent=2, default=str))
