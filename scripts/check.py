#!/usr/bin/env python3
"""
Diff engine for SEO Drift Monitor.

Compares the current state of a page against its most recent baseline,
classifies changes by severity (CRITICAL/WARNING/INFO), and generates
fix recommendations.

Usage:
    python check.py <url>
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

# Add parent seo scripts to path
SEO_SCRIPTS_DIR = os.path.expanduser("~/.claude/skills/seo/scripts")
sys.path.insert(0, SEO_SCRIPTS_DIR)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from parse_html import parse_html
from cwv import fetch_cwv
from db import (
    normalize_url, url_hash, get_latest_baseline, save_check, init_db,
)
from report import generate_drift_report


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


def run_check(url: str, skip_cwv: bool = False) -> dict:
    """
    Check a URL against its most recent baseline.

    Returns:
        Dictionary with diffs, summary, and report path.
    """
    init_db()
    normalized = normalize_url(url)
    now = datetime.now(timezone.utc).isoformat()

    # 1. Load baseline
    baseline = get_latest_baseline(normalized)
    if not baseline:
        return {"error": f"No baseline found for {normalized}. Run baseline first."}

    print(f"Checking: {normalized}", file=sys.stderr)
    print(f"  Against baseline from: {baseline['created_at']}", file=sys.stderr)

    # 2. Fetch current state
    print("  Fetching current page...", file=sys.stderr)
    fetch_result = fetch_page_safe(normalized)
    if fetch_result["error"]:
        return {"error": f"Failed to fetch page: {fetch_result['error']}"}

    html = fetch_result["content"]
    status_code = fetch_result["status_code"]

    # 3. Parse current HTML
    print("  Parsing SEO elements...", file=sys.stderr)
    parsed = parse_html(html, normalized)

    html_hash = hashlib.sha256(html.encode()).hexdigest()
    schema_canonical = json.dumps(parsed["schema"], sort_keys=True)
    schema_hash = hashlib.sha256(schema_canonical.encode()).hexdigest()

    screenshot_path = None

    # 5. CWV
    cwv = None
    if not skip_cwv:
        print("  Fetching Core Web Vitals...", file=sys.stderr)
        cwv = fetch_cwv(normalized)

    # 6. Build current state dict
    current = {
        "title": parsed["title"],
        "meta_description": parsed["meta_description"],
        "canonical": parsed["canonical"],
        "robots": parsed["meta_robots"],
        "headings": {
            "h1": parsed["h1"],
            "h2": parsed["h2"],
            "h3": parsed["h3"],
        },
        "schema": parsed["schema"],
        "schema_hash": schema_hash,
        "open_graph": parsed["open_graph"],
        "html_hash": html_hash,
        "cwv": cwv,
        "status_code": status_code,
        "screenshot_path": screenshot_path,
    }

    # 7. Compute diffs
    print("  Computing diffs...", file=sys.stderr)
    diffs = compute_diffs(baseline, current)

    # 8. Generate visual report
    report_path = None
    print("  Generating report...", file=sys.stderr)
    try:
        report_path = generate_drift_report(baseline, current, diffs, normalized, now)
    except Exception as e:
        print(f"  [WARN] Report generation failed: {e}", file=sys.stderr)

    # 9. Save check to DB
    check_id = save_check(
        baseline_id=baseline["id"],
        diffs=diffs,
        screenshot_path=screenshot_path,
        report_path=report_path,
        url=normalized,
    )

    summary = {
        "check_id": check_id,
        "url": normalized,
        "baseline_id": baseline["id"],
        "baseline_date": baseline["created_at"],
        "checked_at": now,
        "diffs": diffs,
        "summary": {
            "critical": len([d for d in diffs if d["severity"] == "CRITICAL"]),
            "warning": len([d for d in diffs if d["severity"] == "WARNING"]),
            "info": len([d for d in diffs if d["severity"] == "INFO"]),
        },
        "report_path": report_path,
    }

    severity_counts = summary["summary"]
    print(
        f"  Result: {severity_counts['critical']} CRITICAL, "
        f"{severity_counts['warning']} WARNING, {severity_counts['info']} INFO",
        file=sys.stderr,
    )

    return summary


def compute_diffs(baseline: dict, current: dict) -> list[dict]:
    """Compare baseline and current state, return classified diffs."""
    diffs = []

    # --- CRITICAL checks ---

    # Status code degradation
    b_status = baseline.get("status_code", 200)
    c_status = current.get("status_code", 200)
    if c_status and c_status >= 400 and (not b_status or b_status < 400):
        diffs.append({
            "element": "status_code",
            "severity": "CRITICAL",
            "before": str(b_status),
            "after": str(c_status),
            "recommendation": f"Page is returning HTTP {c_status}. Check server configuration and ensure the page is accessible. Run /seo-technical to diagnose.",
        })

    # Schema blocks removed
    b_types = _schema_types(baseline.get("schema", []))
    c_types = _schema_types(current.get("schema", []))
    removed_types = b_types - c_types
    for st in removed_types:
        diffs.append({
            "element": f"schema.{st}",
            "severity": "CRITICAL",
            "before": f"{st} schema present",
            "after": "Removed",
            "recommendation": f"Re-add {st} JSON-LD schema. Use /seo-schema to generate the correct markup.",
        })

    # Canonical changed
    b_canonical = _normalize_for_compare(baseline.get("canonical", ""))
    c_canonical = _normalize_for_compare(current.get("canonical", ""))
    if b_canonical and c_canonical and b_canonical != c_canonical:
        diffs.append({
            "element": "canonical",
            "severity": "CRITICAL",
            "before": baseline.get("canonical", ""),
            "after": current.get("canonical", ""),
            "recommendation": "Canonical URL changed. Verify this is intentional. An incorrect canonical can deindex the page. Use /seo-technical to review.",
        })
    elif b_canonical and not c_canonical:
        diffs.append({
            "element": "canonical",
            "severity": "CRITICAL",
            "before": baseline.get("canonical", ""),
            "after": "(removed)",
            "recommendation": "Canonical tag was removed. Add it back to prevent duplicate content issues. Use /seo-technical to review.",
        })

    # robots noindex added
    b_robots = (baseline.get("robots") or "").lower()
    c_robots = (current.get("robots") or "").lower()
    if "noindex" not in b_robots and "noindex" in c_robots:
        diffs.append({
            "element": "robots",
            "severity": "CRITICAL",
            "before": baseline.get("robots") or "(none)",
            "after": current.get("robots", ""),
            "recommendation": "noindex was added to meta robots. This will remove the page from Google. Remove noindex unless intentional. Use /seo-technical to review.",
        })

    # H1 removed or changed
    b_h1 = baseline.get("headings", {}).get("h1", [])
    c_h1 = current.get("headings", {}).get("h1", [])
    if b_h1 and not c_h1:
        diffs.append({
            "element": "h1",
            "severity": "CRITICAL",
            "before": b_h1[0] if b_h1 else "(none)",
            "after": "(removed)",
            "recommendation": "H1 heading was removed. Every page needs exactly one H1 for SEO. Restore or add a new H1. Use /seo-page to optimize.",
        })
    elif b_h1 and c_h1 and b_h1[0].strip().lower() != c_h1[0].strip().lower():
        diffs.append({
            "element": "h1",
            "severity": "CRITICAL",
            "before": b_h1[0],
            "after": c_h1[0],
            "recommendation": "H1 text changed. Verify the new H1 contains your target keywords. Use /seo-page to optimize.",
        })

    # --- WARNING checks ---

    # Title changed
    b_title = (baseline.get("title") or "").strip()
    c_title = (current.get("title") or "").strip()
    if b_title and c_title and b_title != c_title:
        diffs.append({
            "element": "title",
            "severity": "WARNING",
            "before": b_title,
            "after": c_title,
            "recommendation": "Title tag changed. Ensure the new title includes target keywords and is under 60 characters. Use /seo-page to optimize.",
        })
    elif b_title and not c_title:
        diffs.append({
            "element": "title",
            "severity": "CRITICAL",
            "before": b_title,
            "after": "(removed)",
            "recommendation": "Title tag was removed. This is critical for SEO. Add a title tag immediately. Use /seo-page to optimize.",
        })

    # Description changed
    b_desc = (baseline.get("meta_description") or "").strip()
    c_desc = (current.get("meta_description") or "").strip()
    if b_desc and c_desc and b_desc != c_desc:
        diffs.append({
            "element": "meta_description",
            "severity": "WARNING",
            "before": b_desc[:100] + ("..." if len(b_desc) > 100 else ""),
            "after": c_desc[:100] + ("..." if len(c_desc) > 100 else ""),
            "recommendation": "Meta description changed. Ensure it's compelling and under 160 characters. Use /seo-page to optimize.",
        })

    # CWV regression >20%
    b_cwv = baseline.get("cwv")
    c_cwv = current.get("cwv")
    if b_cwv and c_cwv:
        for metric, label in [("lcp", "LCP"), ("fcp", "FCP"), ("cls", "CLS"), ("tbt", "TBT")]:
            b_val = b_cwv.get(metric, 0)
            c_val = c_cwv.get(metric, 0)
            if b_val and b_val > 0:
                pct_change = ((c_val - b_val) / b_val) * 100
                if pct_change > 20:
                    unit = "ms" if metric == "tbt" else "s" if metric != "cls" else ""
                    diffs.append({
                        "element": f"cwv.{metric}",
                        "severity": "WARNING",
                        "before": f"{b_val}{unit}",
                        "after": f"{c_val}{unit} (+{pct_change:.0f}%)",
                        "recommendation": f"{label} regressed by {pct_change:.0f}%. Use /seo-technical to diagnose performance issues.",
                    })

        # Overall score regression
        b_score = b_cwv.get("score", 0)
        c_score = c_cwv.get("score", 0)
        if b_score and c_score and (b_score - c_score) >= 10:
            diffs.append({
                "element": "cwv.score",
                "severity": "WARNING",
                "before": f"{b_score}/100",
                "after": f"{c_score}/100 ({c_score - b_score:+d})",
                "recommendation": f"Performance score dropped by {b_score - c_score} points. Run /seo-technical for detailed diagnosis.",
            })

    # OG tags changed
    b_og = baseline.get("open_graph", {})
    c_og = current.get("open_graph", {})
    if b_og != c_og:
        removed_og = set(b_og.keys()) - set(c_og.keys())
        if removed_og:
            diffs.append({
                "element": "open_graph",
                "severity": "WARNING",
                "before": f"{len(b_og)} OG tags",
                "after": f"{len(c_og)} OG tags (removed: {', '.join(removed_og)})",
                "recommendation": "Open Graph tags were removed. This affects how the page appears when shared on social media. Use /seo-page to restore.",
            })

    # Schema modified (not removed)
    added_types = c_types - b_types
    for st in added_types:
        diffs.append({
            "element": f"schema.{st}",
            "severity": "INFO",
            "before": "(not present)",
            "after": f"{st} schema added",
            "recommendation": "New schema added. Validate with Google's Rich Results Test. Use /seo-schema to review.",
        })

    if baseline.get("schema_hash") != current.get("schema_hash") and not removed_types and not added_types:
        diffs.append({
            "element": "schema",
            "severity": "WARNING",
            "before": f"{len(baseline.get('schema', []))} schema blocks",
            "after": f"{len(current.get('schema', []))} schema blocks (content modified)",
            "recommendation": "Schema content was modified. Validate the updated schema with Google's Rich Results Test. Use /seo-schema to review.",
        })

    # --- INFO checks ---

    # H2/H3 structure changed
    b_h2 = baseline.get("headings", {}).get("h2", [])
    c_h2 = current.get("headings", {}).get("h2", [])
    if b_h2 != c_h2:
        diffs.append({
            "element": "headings.h2",
            "severity": "INFO",
            "before": f"{len(b_h2)} H2 headings",
            "after": f"{len(c_h2)} H2 headings",
            "recommendation": "H2 heading structure changed. Review for keyword relevance. Use /seo-page to optimize.",
        })

    # Content hash changed (catch-all)
    if baseline.get("html_hash") != current.get("html_hash"):
        # Only add if no other content-related diffs were found
        content_diffs = [d for d in diffs if d["element"] not in ("cwv.score", "cwv.lcp", "cwv.fcp", "cwv.cls", "cwv.tbt")]
        if not content_diffs:
            diffs.append({
                "element": "content",
                "severity": "INFO",
                "before": "Content hash: " + baseline["html_hash"][:12],
                "after": "Content hash: " + current["html_hash"][:12],
                "recommendation": "Page content changed. Review to ensure SEO-critical content is intact. Run /seo-audit for a full review.",
            })

    # Sort by severity
    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    diffs.sort(key=lambda d: severity_order.get(d["severity"], 3))

    return diffs


def _schema_types(schemas: list) -> set:
    """Extract unique @type values from schema blocks."""
    types = set()
    for s in schemas:
        if isinstance(s, dict):
            st = s.get("@type", "")
            if isinstance(st, list):
                types.update(st)
            elif st:
                types.add(st)
    return types


def _normalize_for_compare(url_str: str) -> str:
    """Normalize URL for comparison (strip protocol, trailing slash)."""
    if not url_str:
        return ""
    return url_str.lower().rstrip("/").replace("http://", "").replace("https://", "")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check.py <url> [--skip-cwv]")
        sys.exit(1)

    target_url = sys.argv[1]
    skip_cwv = "--skip-cwv" in sys.argv

    result = run_check(target_url, skip_cwv=skip_cwv)
    print(json.dumps(result, indent=2))
