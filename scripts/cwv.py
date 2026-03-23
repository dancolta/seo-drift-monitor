#!/usr/bin/env python3
"""
Core Web Vitals fetcher using Google PageSpeed Insights API.

Adapted from the proven PSI integration in the NodeSparks outreach scanner.
Uses curl to avoid Python SSL certificate issues.
"""

import json
import subprocess
import sys
import time
import urllib.parse

# PageSpeed Insights API key (Google Cloud project)
PSI_API_KEY = "AIzaSyAOi6STdZHm04isQK12oCnXYKL7J5n4scQ"
PSI_TIMEOUT = 90  # seconds per attempt


def fetch_cwv(url: str, strategy: str = "mobile") -> dict | None:
    """
    Fetch Core Web Vitals from Google PageSpeed Insights API.

    Args:
        url: The URL to analyze
        strategy: "mobile" or "desktop"

    Returns:
        Dictionary with {score, fcp, lcp, si, tbt, cls, extras} or None on failure.
    """
    psi_url = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?"
        + urllib.parse.urlencode({
            "url": url,
            "category": "performance",
            "strategy": strategy,
            "key": PSI_API_KEY,
        })
    )

    for attempt in range(3):
        try:
            result = subprocess.run(
                ["curl", "-s", "-f", psi_url],
                capture_output=True,
                text=True,
                timeout=PSI_TIMEOUT,
            )
            if result.returncode == 0 and result.stdout.strip():
                break
            if attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"  PSI retry in {wait}s... (attempt {attempt + 2}/3)", file=sys.stderr)
                time.sleep(wait)
        except subprocess.TimeoutExpired:
            if attempt < 2:
                print(f"  PSI timed out, retrying...", file=sys.stderr)
                continue
    else:
        print("  [WARN] PageSpeed Insights: all attempts failed", file=sys.stderr)
        return None

    try:
        data = json.loads(result.stdout)
        lhr = data["lighthouseResult"]
        cat = lhr["categories"]["performance"]
        audits = lhr["audits"]

        if cat["score"] is None:
            print("  [WARN] PageSpeed Insights returned null score", file=sys.stderr)
            return None

        score = int(cat["score"] * 100)
        fcp = round(audits["first-contentful-paint"]["numericValue"] / 1000, 1)
        lcp = round(audits["largest-contentful-paint"]["numericValue"] / 1000, 1)
        si = round(audits["speed-index"]["numericValue"] / 1000, 1)
        tbt = int(audits["total-blocking-time"]["numericValue"])
        cls_val = round(audits["cumulative-layout-shift"]["numericValue"], 3)

        extras = []

        # Render-blocking resources
        rb = audits.get("render-blocking-resources", {})
        if rb.get("details", {}).get("items"):
            total_ms = sum(i.get("wastedMs", 0) for i in rb["details"]["items"])
            count = len(rb["details"]["items"])
            if total_ms > 500:
                extras.append(f"{count} render-blocking resources ({total_ms:,.0f}ms)")

        # Modern image formats
        mf = audits.get("modern-image-formats", {})
        if mf.get("details", {}).get("items"):
            total_kb = sum(i.get("wastedBytes", 0) for i in mf["details"]["items"]) / 1024
            if total_kb > 100:
                extras.append(f"Images not in modern formats ({total_kb:,.0f} KiB)")

        # Unused JavaScript
        ujs = audits.get("unused-javascript", {})
        if ujs.get("details", {}).get("items"):
            total_kb = sum(i.get("wastedBytes", 0) for i in ujs["details"]["items"]) / 1024
            if total_kb > 50:
                extras.append(f"Unused JavaScript ({total_kb:,.0f} KiB)")

        # Server response time
        srt = audits.get("server-response-time", {})
        if srt.get("details", {}).get("items"):
            rt = srt["details"]["items"][0].get("responseTime", 0)
            if rt > 300:
                extras.append(f"Slow server response ({rt:.0f}ms)")

        return {
            "score": score,
            "fcp": fcp,
            "lcp": lcp,
            "si": si,
            "tbt": tbt,
            "cls": cls_val,
            "extras": extras,
        }

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  [WARN] PageSpeed Insights parse error: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cwv.py <url> [mobile|desktop]")
        sys.exit(1)
    url = sys.argv[1]
    strategy = sys.argv[2] if len(sys.argv) > 2 else "mobile"
    result = fetch_cwv(url, strategy)
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("Failed to fetch CWV data", file=sys.stderr)
        sys.exit(1)
