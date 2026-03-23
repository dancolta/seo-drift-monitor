#!/usr/bin/env python3
"""
Visual HTML report generator for SEO Drift Monitor.

Generates a clean, data-focused drift report with severity cards,
before/after change details, fix recommendations, and CWV comparison bars.
No screenshots — all changes are code/backend elements best shown as data.
"""

import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from db import REPORTS_DIR, init_db


# --- Severity styling ---

SEVERITY = {
    "CRITICAL": {
        "bg": "#fef2f2", "border": "#ef4444", "text": "#991b1b",
        "badge_bg": "#dc2626", "badge_text": "#ffffff",
        "icon": "&#x2716;",  # x mark
        "dot": "#ef4444",
    },
    "WARNING": {
        "bg": "#fffbeb", "border": "#f59e0b", "text": "#92400e",
        "badge_bg": "#d97706", "badge_text": "#ffffff",
        "icon": "&#x26A0;",  # warning triangle
        "dot": "#f59e0b",
    },
    "INFO": {
        "bg": "#f0fdf4", "border": "#10b981", "text": "#065f46",
        "badge_bg": "#059669", "badge_text": "#ffffff",
        "icon": "&#x2139;",  # info
        "dot": "#10b981",
    },
}


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _format_date(iso_str: str) -> str:
    """Format ISO date to readable string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y &middot; %H:%M UTC")
    except (ValueError, AttributeError):
        return iso_str or "Unknown"


def _format_date_short(iso_str: str) -> str:
    """Short date format for compact display."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %H:%M")
    except (ValueError, AttributeError):
        return iso_str or "—"


# --- Report sections ---

def _summary_header(domain: str, baseline_date: str, check_date: str,
                    critical: int, warning: int, info: int) -> str:
    """Top section: URL, dates, status badge, severity counts."""
    total = critical + warning + info
    if critical > 0:
        status_label = "DRIFT DETECTED"
        status_color = "#dc2626"
        status_bg = "#fef2f2"
        ring_color = "#fecaca"
    elif warning > 0:
        status_label = "CHANGES FOUND"
        status_color = "#d97706"
        status_bg = "#fffbeb"
        ring_color = "#fde68a"
    elif info > 0:
        status_label = "MINOR CHANGES"
        status_color = "#059669"
        status_bg = "#f0fdf4"
        ring_color = "#a7f3d0"
    else:
        status_label = "ALL CLEAR"
        status_color = "#059669"
        status_bg = "#f0fdf4"
        ring_color = "#a7f3d0"

    return f"""
    <!-- Header -->
    <div style="margin-bottom: 32px;">
        <div style="display: flex; justify-content: space-between; align-items: center;
                    margin-bottom: 20px;">
            <div>
                <div style="font-size: 11px; font-weight: 600; text-transform: uppercase;
                            letter-spacing: 1.5px; color: #9ca3af; margin-bottom: 6px;">
                    SEO Drift Report
                </div>
                <h1 style="font-size: 22px; font-weight: 700; color: #111827; margin: 0;">
                    {_escape(domain)}
                </h1>
            </div>
            <div style="background: {status_bg}; color: {status_color}; padding: 6px 14px;
                        border-radius: 20px; font-weight: 700; font-size: 12px;
                        letter-spacing: 0.5px; border: 1.5px solid {ring_color};">
                {status_label}
            </div>
        </div>

        <!-- Date bar -->
        <div style="display: flex; align-items: center; gap: 12px; padding: 12px 16px;
                    background: #f9fafb; border-radius: 8px; font-size: 13px; color: #6b7280;">
            <span style="font-weight: 600; color: #374151;">Baseline</span>
            <span>{_format_date(baseline_date)}</span>
            <span style="color: #d1d5db;">&#x2192;</span>
            <span style="font-weight: 600; color: #374151;">Check</span>
            <span>{_format_date(check_date)}</span>
            <span style="margin-left: auto; color: #9ca3af;">{total} change{'s' if total != 1 else ''}</span>
        </div>

        <!-- Severity cards -->
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px;">
            {_severity_card("Critical", critical, SEVERITY["CRITICAL"])}
            {_severity_card("Warning", warning, SEVERITY["WARNING"])}
            {_severity_card("Info", info, SEVERITY["INFO"])}
        </div>
    </div>
    """


def _severity_card(label: str, count: int, colors: dict) -> str:
    """Single severity count card."""
    opacity = "1" if count > 0 else "0.45"
    return f"""
    <div style="text-align: center; padding: 14px 10px; border-radius: 8px;
                background: {colors['bg']}; border: 1px solid {colors['border']}20;
                opacity: {opacity};">
        <div style="font-size: 28px; font-weight: 800; color: {colors['badge_bg']};
                    line-height: 1.1;">{count}</div>
        <div style="font-size: 11px; font-weight: 600; text-transform: uppercase;
                    letter-spacing: 0.8px; color: {colors['text']}; margin-top: 2px;">
            {label}
        </div>
    </div>
    """


def _changes_section(diffs: list[dict]) -> str:
    """Main diff list grouped by severity."""
    if not diffs:
        return """
        <div style="text-align: center; padding: 48px 20px; color: #059669;">
            <div style="font-size: 36px; margin-bottom: 8px;">&#x2713;</div>
            <div style="font-size: 16px; font-weight: 600;">No drift detected</div>
            <div style="font-size: 13px; color: #6b7280; margin-top: 4px;">
                Page matches the baseline. All SEO elements intact.
            </div>
        </div>
        """

    rows = ""
    current_severity = None
    for diff in diffs:
        sev = diff["severity"]
        if sev != current_severity:
            current_severity = sev
            colors = SEVERITY.get(sev, SEVERITY["INFO"])
            rows += f"""
            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase;
                        letter-spacing: 1.2px; color: {colors['badge_bg']}; margin-top: 20px;
                        margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%;
                             background: {colors['dot']};"></span>
                {sev}
            </div>
            """
        rows += _diff_card(diff)

    return f"""
    <div style="margin-bottom: 32px;">
        <h2 style="font-size: 15px; font-weight: 700; color: #111827; margin-bottom: 4px;
                   padding-bottom: 10px; border-bottom: 1px solid #e5e7eb;">
            Changes Detected
        </h2>
        {rows}
    </div>
    """


def _diff_card(diff: dict) -> str:
    """Single change card with before/after and recommendation."""
    colors = SEVERITY.get(diff["severity"], SEVERITY["INFO"])
    element = diff["element"].replace(".", " / ").replace("_", " ")
    # Capitalize first letter of each word but keep short
    element_display = element.title()

    before = _escape(diff.get("before", ""))
    after = _escape(diff.get("after", ""))
    rec = _escape(diff.get("recommendation", ""))

    return f"""
    <div style="background: #ffffff; border: 1px solid #e5e7eb; border-left: 3px solid {colors['border']};
                border-radius: 0 6px 6px 0; padding: 14px 16px; margin-bottom: 6px;">
        <!-- Element name + badge -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 13px; font-weight: 700; color: #111827;">{element_display}</span>
            <span style="font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
                         background: {colors['badge_bg']}; color: {colors['badge_text']};
                         padding: 2px 8px; border-radius: 10px;">{diff['severity']}</span>
        </div>
        <!-- Before / After -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
            <div style="background: #f9fafb; padding: 8px 10px; border-radius: 4px; font-size: 12px;">
                <div style="color: #9ca3af; font-size: 10px; font-weight: 600; text-transform: uppercase;
                            letter-spacing: 0.5px; margin-bottom: 3px;">Before</div>
                <div style="color: #374151; word-break: break-word; font-family: 'SF Mono', 'Fira Code',
                            'Cascadia Code', monospace; font-size: 12px;">{before}</div>
            </div>
            <div style="background: {colors['bg']}; padding: 8px 10px; border-radius: 4px; font-size: 12px;">
                <div style="color: {colors['text']}; font-size: 10px; font-weight: 600; text-transform: uppercase;
                            letter-spacing: 0.5px; margin-bottom: 3px;">After</div>
                <div style="color: {colors['text']}; font-weight: 600; word-break: break-word;
                            font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
                            font-size: 12px;">{after}</div>
            </div>
        </div>
        <!-- Recommendation -->
        <div style="font-size: 12px; color: #6b7280; padding: 6px 0 0 0;
                    border-top: 1px solid #f3f4f6;">
            {rec}
        </div>
    </div>
    """


def _cwv_section(b_cwv: dict | None, c_cwv: dict | None) -> str:
    """Core Web Vitals comparison with horizontal bars."""
    if not b_cwv or not c_cwv:
        return ""

    b_score = b_cwv.get("score", 0)
    c_score = c_cwv.get("score", 0)
    score_diff = c_score - b_score
    score_color = "#059669" if score_diff >= 0 else "#dc2626" if score_diff < -10 else "#d97706"

    metrics = [
        ("LCP", "Largest Contentful Paint", b_cwv.get("lcp", 0), c_cwv.get("lcp", 0), "s", True),
        ("FCP", "First Contentful Paint", b_cwv.get("fcp", 0), c_cwv.get("fcp", 0), "s", True),
        ("CLS", "Cumulative Layout Shift", b_cwv.get("cls", 0), c_cwv.get("cls", 0), "", True),
        ("TBT", "Total Blocking Time", b_cwv.get("tbt", 0), c_cwv.get("tbt", 0), "ms", True),
    ]

    metric_rows = ""
    for abbr, full_name, before, after, unit, higher_is_worse in metrics:
        if before == 0 and after == 0:
            continue
        metric_rows += _cwv_metric_row(abbr, full_name, before, after, unit, higher_is_worse)

    return f"""
    <div style="margin-bottom: 32px;">
        <h2 style="font-size: 15px; font-weight: 700; color: #111827; margin-bottom: 14px;
                   padding-bottom: 10px; border-bottom: 1px solid #e5e7eb;">
            Core Web Vitals
        </h2>

        <!-- Score summary -->
        <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 12px;
                    align-items: center; margin-bottom: 20px; padding: 16px;
                    background: #f9fafb; border-radius: 8px;">
            <div style="text-align: center;">
                <div style="font-size: 10px; font-weight: 600; text-transform: uppercase;
                            letter-spacing: 1px; color: #9ca3af; margin-bottom: 4px;">Baseline</div>
                <div style="font-size: 32px; font-weight: 800; color: #374151;">{b_score}</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 20px; color: {score_color}; font-weight: 800;">
                    {'+' if score_diff > 0 else ''}{score_diff}
                </div>
                <div style="font-size: 10px; color: #9ca3af; text-transform: uppercase;
                            letter-spacing: 0.5px;">pts</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 10px; font-weight: 600; text-transform: uppercase;
                            letter-spacing: 1px; color: #9ca3af; margin-bottom: 4px;">Current</div>
                <div style="font-size: 32px; font-weight: 800; color: {score_color};">{c_score}</div>
            </div>
        </div>

        <!-- Individual metrics -->
        {metric_rows}
    </div>
    """


def _cwv_metric_row(abbr: str, full_name: str, before: float, after: float,
                    unit: str, higher_is_worse: bool) -> str:
    """Single CWV metric comparison row."""
    if before > 0:
        pct = ((after - before) / before) * 100
    else:
        pct = 0

    if higher_is_worse:
        color = "#dc2626" if pct > 20 else "#d97706" if pct > 0 else "#059669"
    else:
        color = "#059669" if pct >= 0 else "#dc2626" if pct < -20 else "#d97706"

    max_val = max(before, after, 0.001)
    b_width = max(min((before / max_val) * 100, 100), 2)
    a_width = max(min((after / max_val) * 100, 100), 2)
    sign = "+" if pct > 0 else ""

    return f"""
    <div style="margin-bottom: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline;
                    margin-bottom: 6px;">
            <div>
                <span style="font-size: 13px; font-weight: 700; color: #111827;">{abbr}</span>
                <span style="font-size: 11px; color: #9ca3af; margin-left: 4px;">{full_name}</span>
            </div>
            <span style="font-size: 12px; font-weight: 700; color: {color};">{sign}{pct:.0f}%</span>
        </div>
        <!-- Baseline bar -->
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
            <span style="width: 52px; text-align: right; font-size: 12px; color: #9ca3af;
                         font-family: 'SF Mono', monospace;">{before}{unit}</span>
            <div style="flex: 1; background: #f3f4f6; border-radius: 3px; height: 14px;">
                <div style="width: {b_width}%; background: #d1d5db; height: 100%;
                            border-radius: 3px;"></div>
            </div>
        </div>
        <!-- Current bar -->
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="width: 52px; text-align: right; font-size: 12px; font-weight: 600;
                         color: {color}; font-family: 'SF Mono', monospace;">{after}{unit}</span>
            <div style="flex: 1; background: #f3f4f6; border-radius: 3px; height: 14px;">
                <div style="width: {a_width}%; background: {color}; height: 100%;
                            border-radius: 3px;"></div>
            </div>
        </div>
    </div>
    """


# --- Main generator ---

def generate_drift_report(
    baseline: dict,
    current: dict,
    diffs: list[dict],
    url: str,
    check_time: str,
) -> str:
    """
    Generate a visual HTML drift report.

    Returns:
        Path to the generated HTML report file.
    """
    init_db()
    domain = urlparse(url).netloc.replace("www.", "")
    timestamp = check_time.replace(":", "-").replace("+", "")[:19]

    critical = len([d for d in diffs if d["severity"] == "CRITICAL"])
    warning = len([d for d in diffs if d["severity"] == "WARNING"])
    info = len([d for d in diffs if d["severity"] == "INFO"])

    header = _summary_header(domain, baseline.get("created_at", ""), check_time,
                             critical, warning, info)
    changes = _changes_section(diffs)
    cwv = _cwv_section(baseline.get("cwv"), current.get("cwv"))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Drift Report &mdash; {_escape(domain)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
                         'Helvetica Neue', Arial, sans-serif;
            background: #ffffff;
            color: #111827;
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
        }}
        .container {{
            max-width: 720px;
            margin: 0 auto;
            padding: 36px 28px 48px;
        }}
        @media (max-width: 640px) {{
            .container {{ padding: 20px 16px 32px; }}
        }}
        @media print {{
            body {{ font-size: 12px; }}
            .container {{ padding: 12px; max-width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {header}
        {changes}
        {cwv}
        <!-- Footer -->
        <div style="padding-top: 20px; border-top: 1px solid #f3f4f6; margin-top: 8px;
                    font-size: 11px; color: #c0c5ce; text-align: center; letter-spacing: 0.3px;">
            Generated by
            <a href="https://github.com/dancolta/seo-drift-monitor"
               style="color: #9ca3af; text-decoration: none;">SEO Drift Monitor</a>
            &mdash; extension for
            <a href="https://github.com/AgriciDaniel/claude-seo"
               style="color: #9ca3af; text-decoration: none;">claude-seo</a>
        </div>
    </div>
</body>
</html>"""

    filename = f"{domain.replace('.', '_')}_{timestamp}_drift.html"
    report_path = os.path.join(REPORTS_DIR, filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Report saved: {report_path}", file=sys.stderr)
    return report_path


if __name__ == "__main__":
    # Test with mock data
    mock_baseline = {
        "created_at": "2026-03-20T14:30:00+00:00",
        "cwv": {"score": 72, "lcp": 3.2, "fcp": 1.8, "cls": 0.05, "tbt": 180, "si": 4.1},
    }
    mock_current = {
        "cwv": {"score": 58, "lcp": 4.1, "fcp": 1.9, "cls": 0.04, "tbt": 195, "si": 5.2},
    }
    mock_diffs = [
        {"element": "schema.Organization", "severity": "CRITICAL",
         "before": "Organization schema present", "after": "Removed",
         "recommendation": "Re-add Organization JSON-LD schema. Use /seo-schema to generate."},
        {"element": "h1", "severity": "CRITICAL",
         "before": "Welcome to Example", "after": "New Homepage",
         "recommendation": "Verify the new H1 contains target keywords."},
        {"element": "cwv.lcp", "severity": "WARNING",
         "before": "3.2s", "after": "4.1s (+28%)",
         "recommendation": "LCP regressed by 28%. Check for new unoptimized images."},
        {"element": "open_graph", "severity": "WARNING",
         "before": "7 OG tags", "after": "3 OG tags (removed: og:image, og:title, og:type, og:description)",
         "recommendation": "Open Graph tags were removed. This affects social media sharing."},
        {"element": "content", "severity": "INFO",
         "before": "Hash: a1b2c3d4e5f6", "after": "Hash: f6e5d4c3b2a1",
         "recommendation": "Page content changed. Review to ensure SEO-critical content is intact."},
    ]
    path = generate_drift_report(
        mock_baseline, mock_current, mock_diffs,
        "https://example.com", "2026-03-22T10:15:00+00:00",
    )
    print(f"Test report: {path}")
