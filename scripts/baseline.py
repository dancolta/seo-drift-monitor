#!/usr/bin/env python3
"""
Capture a baseline snapshot of a page's SEO-critical elements.

Stores title, meta tags, canonical, headings, schema/JSON-LD, OG tags,
and Core Web Vitals as a "known good" state.

Usage:
    python baseline.py <url>
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

# Add parent seo scripts to path for imports
SEO_SCRIPTS_DIR = os.path.expanduser("~/.claude/skills/seo/scripts")
sys.path.insert(0, SEO_SCRIPTS_DIR)

# Add local scripts dir
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from parse_html import parse_html
from cwv import fetch_cwv
from db import (
    normalize_url, url_hash, save_baseline, init_db,
)


def fetch_page_safe(url: str) -> dict:
    """Fetch a page with requests first, fallback to curl on SSL errors."""
    try:
        from fetch_page import fetch_page
        result = fetch_page(url)
        if result.get("error"):
            raise Exception(f"fetch_page failed: {result['error']}")
        return result
    except Exception:
        pass
    # Fallback: curl -sk (same approach as the outreach scanner)
    import subprocess
    try:
        proc = subprocess.run(
            ["curl", "-sk", "-L", "--max-redirs", "5", "-o", "-",
             "-w", "\n%{http_code}\n%{url_effective}", url],
            capture_output=True, text=True, timeout=30,
        )
        parts = proc.stdout.rsplit("\n", 2)
        if len(parts) >= 3:
            content = parts[0]
            status_code = int(parts[1]) if parts[1].strip().isdigit() else 200
            final_url = parts[2].strip() or url
        else:
            content = proc.stdout
            status_code = 200
            final_url = url
        return {
            "url": final_url,
            "status_code": status_code,
            "content": content,
            "headers": {},
            "redirect_chain": [],
            "error": None,
        }
    except Exception as e:
        return {"url": url, "status_code": None, "content": None,
                "headers": {}, "redirect_chain": [], "error": str(e)}


def capture_baseline(url: str, skip_cwv: bool = False) -> dict:
    """
    Capture a complete baseline snapshot of a URL.

    Args:
        url: The URL to baseline
        skip_cwv: Skip PageSpeed Insights API call (faster, for testing)

    Returns:
        Dictionary with baseline data including the saved ID.
    """
    init_db()
    normalized = normalize_url(url)
    uhash = url_hash(normalized)
    now = datetime.now(timezone.utc).isoformat()

    print(f"Baselining: {normalized}", file=sys.stderr)

    # 1. Fetch HTML
    print("  Fetching page...", file=sys.stderr)
    fetch_result = fetch_page_safe(normalized)
    if fetch_result["error"]:
        return {"error": f"Failed to fetch page: {fetch_result['error']}"}

    html = fetch_result["content"]
    status_code = fetch_result["status_code"]

    # 2. Parse HTML for SEO elements
    print("  Parsing SEO elements...", file=sys.stderr)
    parsed = parse_html(html, normalized)

    # 3. Compute hashes
    html_hash = hashlib.sha256(html.encode()).hexdigest()
    schema_canonical = json.dumps(parsed["schema"], sort_keys=True)
    schema_hash = hashlib.sha256(schema_canonical.encode()).hexdigest()

    # 4. Core Web Vitals
    cwv = None
    if not skip_cwv:
        print("  Fetching Core Web Vitals...", file=sys.stderr)
        cwv = fetch_cwv(normalized)
        if cwv:
            print(f"  CWV score: {cwv['score']}/100, LCP: {cwv['lcp']}s", file=sys.stderr)
        else:
            print("  [WARN] CWV data unavailable", file=sys.stderr)

    # 5. Build baseline data
    headings = {
        "h1": parsed["h1"],
        "h2": parsed["h2"],
        "h3": parsed["h3"],
    }

    baseline_data = {
        "url": normalized,
        "url_hash": uhash,
        "created_at": now,
        "html_hash": html_hash,
        "title": parsed["title"],
        "meta_description": parsed["meta_description"],
        "canonical": parsed["canonical"],
        "robots": parsed["meta_robots"],
        "headings": headings,
        "schema": parsed["schema"],
        "schema_hash": schema_hash,
        "open_graph": parsed["open_graph"],
        "cwv": cwv,
        "screenshot_path": None,
        "status_code": status_code,
    }

    # 6. Save to database
    baseline_id = save_baseline(baseline_data)
    baseline_data["id"] = baseline_id

    print(f"  Baseline saved (ID: {baseline_id})", file=sys.stderr)

    return baseline_data


def format_summary(data: dict) -> dict:
    """Format baseline data as a concise JSON summary for Claude."""
    if "error" in data:
        return {"error": data["error"]}

    schema_types = []
    for s in data.get("schema", []):
        if isinstance(s, dict):
            st = s.get("@type", "Unknown")
            if isinstance(st, list):
                schema_types.extend(st)
            else:
                schema_types.append(st)

    summary = {
        "id": data["id"],
        "url": data["url"],
        "created_at": data["created_at"],
        "title": data.get("title"),
        "h1": data["headings"]["h1"],
        "h1_count": len(data["headings"]["h1"]),
        "h2_count": len(data["headings"]["h2"]),
        "h3_count": len(data["headings"]["h3"]),
        "schema_count": len(data.get("schema", [])),
        "schema_types": schema_types,
        "canonical": data.get("canonical"),
        "robots": data.get("robots"),
        "og_tags": len(data.get("open_graph", {})),
        "status_code": data.get("status_code"),
    }

    if data.get("cwv"):
        summary["cwv"] = {
            "score": data["cwv"]["score"],
            "lcp": data["cwv"]["lcp"],
            "fcp": data["cwv"]["fcp"],
            "cls": data["cwv"]["cls"],
            "tbt": data["cwv"]["tbt"],
        }

    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python baseline.py <url> [--skip-cwv]")
        sys.exit(1)

    target_url = sys.argv[1]
    skip_cwv = "--skip-cwv" in sys.argv

    result = capture_baseline(target_url, skip_cwv=skip_cwv)
    summary = format_summary(result)
    print(json.dumps(summary, indent=2))
