#!/usr/bin/env python3
"""
Visual HTML/PDF report generator for SEO Drift Monitor.

Generates side-by-side screenshot comparisons with color-coded diff tables
and Core Web Vitals comparison bars.
"""

import base64
import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from db import REPORTS_DIR, init_db

SEVERITY_COLORS = {
    "CRITICAL": {"bg": "#fef2f2", "border": "#dc2626", "text": "#991b1b", "badge": "#dc2626"},
    "WARNING": {"bg": "#fffbeb", "border": "#d97706", "text": "#92400e", "badge": "#d97706"},
    "INFO": {"bg": "#f0fdf4", "border": "#059669", "text": "#065f46", "badge": "#059669"},
}


def _img_to_base64(path: str) -> str:
    """Read an image file and return base64 data URI."""
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"


def _format_date(iso_str: str) -> str:
    """Format ISO date string to readable format."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except (ValueError, AttributeError):
        return iso_str or "Unknown"


def _cwv_bar(before: float, after: float, label: str, unit: str = "s",
             higher_is_worse: bool = True) -> str:
    """Generate HTML for a CWV comparison bar."""
    if before == 0 and after == 0:
        return ""

    if before > 0:
        pct_change = ((after - before) / before) * 100
    else:
        pct_change = 0

    if higher_is_worse:
        color = "#dc2626" if pct_change > 20 else "#d97706" if pct_change > 0 else "#059669"
    else:
        color = "#059669" if pct_change >= 0 else "#dc2626" if pct_change < -20 else "#d97706"

    max_val = max(before, after, 0.01)
    before_width = min((before / max_val) * 100, 100)
    after_width = min((after / max_val) * 100, 100)
    sign = "+" if pct_change > 0 else ""

    return f"""
    <div style="margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: 600; color: #374151;">{label}</span>
            <span style="color: {color}; font-weight: 600;">{sign}{pct_change:.0f}%</span>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
            <span style="width: 60px; text-align: right; color: #6b7280; font-size: 13px;">
                {before}{unit}
            </span>
            <div style="flex: 1; background: #f3f4f6; border-radius: 4px; height: 20px; position: relative;">
                <div style="width: {before_width}%; background: #9ca3af; height: 100%; border-radius: 4px;"></div>
            </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
            <span style="width: 60px; text-align: right; color: {color}; font-size: 13px; font-weight: 600;">
                {after}{unit}
            </span>
            <div style="flex: 1; background: #f3f4f6; border-radius: 4px; height: 20px; position: relative;">
                <div style="width: {after_width}%; background: {color}; height: 100%; border-radius: 4px;"></div>
            </div>
        </div>
    </div>
    """


def _diff_row(diff: dict) -> str:
    """Generate HTML for a single diff row."""
    colors = SEVERITY_COLORS.get(diff["severity"], SEVERITY_COLORS["INFO"])
    element_label = diff["element"].replace(".", " > ").replace("_", " ").title()

    return f"""
    <div style="background: {colors['bg']}; border-left: 4px solid {colors['border']};
                padding: 14px 18px; margin-bottom: 8px; border-radius: 0 6px 6px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-weight: 700; color: {colors['text']}; font-size: 14px;">
                {element_label}
            </span>
            <span style="background: {colors['badge']}; color: white; padding: 2px 10px;
                         border-radius: 12px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;">
                {diff['severity']}
            </span>
        </div>
        <div style="font-size: 13px; color: #4b5563; margin-bottom: 4px;">
            <span style="color: #9ca3af;">Before:</span> {_escape(diff.get('before', ''))}
        </div>
        <div style="font-size: 13px; color: #4b5563; margin-bottom: 8px;">
            <span style="color: #9ca3af;">After:</span>
            <span style="color: {colors['text']}; font-weight: 600;">{_escape(diff.get('after', ''))}</span>
        </div>
        <div style="font-size: 12px; color: #6b7280; background: white; padding: 8px 12px;
                    border-radius: 4px; border: 1px solid #e5e7eb;">
            {_escape(diff.get('recommendation', ''))}
        </div>
    </div>
    """


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_drift_report(
    baseline: dict,
    current: dict,
    diffs: list[dict],
    url: str,
    check_time: str,
) -> str:
    """
    Generate a visual HTML drift report.

    Args:
        baseline: Baseline snapshot data
        current: Current state data
        diffs: List of diff dicts with element, severity, before, after, recommendation
        url: The URL being checked
        check_time: ISO timestamp of the check

    Returns:
        Path to the generated HTML report file.
    """
    init_db()
    domain = urlparse(url).netloc.replace("www.", "")
    timestamp = check_time.replace(":", "-").replace("+", "")[:19]

    critical_count = len([d for d in diffs if d["severity"] == "CRITICAL"])
    warning_count = len([d for d in diffs if d["severity"] == "WARNING"])
    info_count = len([d for d in diffs if d["severity"] == "INFO"])

    # Overall status
    if critical_count > 0:
        status_color = "#dc2626"
        status_text = "DRIFT DETECTED"
        status_bg = "#fef2f2"
    elif warning_count > 0:
        status_color = "#d97706"
        status_text = "CHANGES DETECTED"
        status_bg = "#fffbeb"
    elif info_count > 0:
        status_color = "#059669"
        status_text = "MINOR CHANGES"
        status_bg = "#f0fdf4"
    else:
        status_color = "#059669"
        status_text = "NO DRIFT"
        status_bg = "#f0fdf4"

    # Screenshots
    baseline_img = _img_to_base64(baseline.get("screenshot_path", ""))
    current_img = _img_to_base64(current.get("screenshot_path", ""))

    # Build diff rows
    diff_rows = "\n".join(_diff_row(d) for d in diffs) if diffs else """
        <div style="text-align: center; padding: 40px; color: #059669; font-size: 18px;">
            No SEO drift detected. Page matches baseline.
        </div>
    """

    # Build CWV comparison
    cwv_section = ""
    b_cwv = baseline.get("cwv")
    c_cwv = current.get("cwv")
    if b_cwv and c_cwv:
        cwv_bars = ""
        cwv_bars += _cwv_bar(b_cwv.get("lcp", 0), c_cwv.get("lcp", 0), "LCP (Largest Contentful Paint)", "s")
        cwv_bars += _cwv_bar(b_cwv.get("fcp", 0), c_cwv.get("fcp", 0), "FCP (First Contentful Paint)", "s")
        cwv_bars += _cwv_bar(b_cwv.get("cls", 0), c_cwv.get("cls", 0), "CLS (Cumulative Layout Shift)", "")
        cwv_bars += _cwv_bar(b_cwv.get("tbt", 0), c_cwv.get("tbt", 0), "TBT (Total Blocking Time)", "ms")

        b_score = b_cwv.get("score", 0)
        c_score = c_cwv.get("score", 0)
        score_diff = c_score - b_score
        score_color = "#059669" if score_diff >= 0 else "#dc2626"

        cwv_section = f"""
        <div style="margin-top: 32px;">
            <h2 style="font-size: 18px; color: #111827; margin-bottom: 16px; padding-bottom: 8px;
                       border-bottom: 2px solid #e5e7eb;">
                Core Web Vitals Comparison
            </h2>
            <div style="display: flex; gap: 16px; margin-bottom: 20px;">
                <div style="flex: 1; text-align: center; padding: 16px; background: #f9fafb; border-radius: 8px;">
                    <div style="font-size: 13px; color: #6b7280;">Baseline Score</div>
                    <div style="font-size: 32px; font-weight: 700; color: #374151;">{b_score}</div>
                </div>
                <div style="flex: 1; text-align: center; padding: 16px; background: #f9fafb; border-radius: 8px;">
                    <div style="font-size: 13px; color: #6b7280;">Current Score</div>
                    <div style="font-size: 32px; font-weight: 700; color: {score_color};">{c_score}</div>
                </div>
                <div style="flex: 1; text-align: center; padding: 16px; background: #f9fafb; border-radius: 8px;">
                    <div style="font-size: 13px; color: #6b7280;">Change</div>
                    <div style="font-size: 32px; font-weight: 700; color: {score_color};">
                        {'+' if score_diff > 0 else ''}{score_diff}
                    </div>
                </div>
            </div>
            {cwv_bars}
        </div>
        """

    # Screenshot section
    screenshot_section = ""
    if baseline_img or current_img:
        baseline_img_tag = f'<img src="{baseline_img}" style="width: 100%; border-radius: 6px; border: 1px solid #e5e7eb;">' if baseline_img else '<div style="height: 200px; background: #f3f4f6; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #9ca3af;">No screenshot</div>'
        current_border = "2px solid #dc2626" if critical_count > 0 else "2px solid #d97706" if warning_count > 0 else "1px solid #e5e7eb"
        current_img_tag = f'<img src="{current_img}" style="width: 100%; border-radius: 6px; border: {current_border};">' if current_img else '<div style="height: 200px; background: #f3f4f6; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #9ca3af;">No screenshot</div>'

        screenshot_section = f"""
        <div style="margin: 24px 0;">
            <h2 style="font-size: 18px; color: #111827; margin-bottom: 16px; padding-bottom: 8px;
                       border-bottom: 2px solid #e5e7eb;">
                Visual Comparison
            </h2>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div>
                    <div style="font-size: 12px; color: #6b7280; margin-bottom: 8px; text-align: center;
                                font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">
                        Baseline ({_format_date(baseline.get('created_at', ''))})
                    </div>
                    {baseline_img_tag}
                </div>
                <div>
                    <div style="font-size: 12px; color: #6b7280; margin-bottom: 8px; text-align: center;
                                font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">
                        Current ({_format_date(check_time)})
                    </div>
                    {current_img_tag}
                </div>
            </div>
        </div>
        """

    # Full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Drift Report - {_escape(domain)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #ffffff;
            color: #111827;
            line-height: 1.5;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 32px 24px;
        }}
        @media print {{
            .container {{ padding: 16px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div style="margin-bottom: 32px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                <div>
                    <h1 style="font-size: 24px; font-weight: 800; color: #111827; margin-bottom: 4px;">
                        SEO Drift Report
                    </h1>
                    <div style="font-size: 15px; color: #6b7280;">{_escape(domain)}</div>
                </div>
                <div style="background: {status_bg}; color: {status_color}; padding: 8px 16px;
                            border-radius: 8px; font-weight: 700; font-size: 14px; border: 1px solid {status_color}20;">
                    {status_text}
                </div>
            </div>

            <!-- Summary cards -->
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 16px;">
                <div style="background: #f9fafb; padding: 14px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">
                        Baseline
                    </div>
                    <div style="font-size: 13px; font-weight: 600; color: #374151; margin-top: 4px;">
                        {_format_date(baseline.get('created_at', ''))}
                    </div>
                </div>
                <div style="background: {SEVERITY_COLORS['CRITICAL']['bg']}; padding: 14px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: {SEVERITY_COLORS['CRITICAL']['text']}; text-transform: uppercase;">
                        Critical
                    </div>
                    <div style="font-size: 28px; font-weight: 800; color: {SEVERITY_COLORS['CRITICAL']['badge']};">
                        {critical_count}
                    </div>
                </div>
                <div style="background: {SEVERITY_COLORS['WARNING']['bg']}; padding: 14px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: {SEVERITY_COLORS['WARNING']['text']}; text-transform: uppercase;">
                        Warning
                    </div>
                    <div style="font-size: 28px; font-weight: 800; color: {SEVERITY_COLORS['WARNING']['badge']};">
                        {warning_count}
                    </div>
                </div>
                <div style="background: {SEVERITY_COLORS['INFO']['bg']}; padding: 14px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: {SEVERITY_COLORS['INFO']['text']}; text-transform: uppercase;">
                        Info
                    </div>
                    <div style="font-size: 28px; font-weight: 800; color: {SEVERITY_COLORS['INFO']['badge']};">
                        {info_count}
                    </div>
                </div>
            </div>
        </div>

        <!-- Screenshots -->
        {screenshot_section}

        <!-- Diffs -->
        <div style="margin-top: 32px;">
            <h2 style="font-size: 18px; color: #111827; margin-bottom: 16px; padding-bottom: 8px;
                       border-bottom: 2px solid #e5e7eb;">
                Changes Detected
            </h2>
            {diff_rows}
        </div>

        <!-- CWV Comparison -->
        {cwv_section}

        <!-- Footer -->
        <div style="margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb;
                    font-size: 12px; color: #9ca3af; text-align: center;">
            Generated by SEO Drift Monitor - an extension for
            <a href="https://github.com/AgriciDaniel/claude-seo" style="color: #6b7280;">claude-seo</a>
        </div>
    </div>
</body>
</html>"""

    # Write HTML file
    filename = f"{domain.replace('.', '_')}_{timestamp}_drift.html"
    report_path = os.path.join(REPORTS_DIR, filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Report saved: {report_path}", file=sys.stderr)
    return report_path


if __name__ == "__main__":
    # Quick test with mock data
    mock_baseline = {
        "created_at": "2026-03-20T14:30:00+00:00",
        "screenshot_path": None,
        "cwv": {"score": 72, "lcp": 3.2, "fcp": 1.8, "cls": 0.05, "tbt": 180, "si": 4.1},
    }
    mock_current = {
        "screenshot_path": None,
        "cwv": {"score": 58, "lcp": 4.1, "fcp": 1.9, "cls": 0.04, "tbt": 195, "si": 5.2},
    }
    mock_diffs = [
        {"element": "schema.Organization", "severity": "CRITICAL", "before": "Organization schema present", "after": "Removed", "recommendation": "Re-add Organization JSON-LD schema."},
        {"element": "h1", "severity": "CRITICAL", "before": "Welcome to Example", "after": "New Homepage", "recommendation": "Verify the new H1 contains target keywords."},
        {"element": "cwv.lcp", "severity": "WARNING", "before": "3.2s", "after": "4.1s (+28%)", "recommendation": "LCP regressed by 28%. Check for new unoptimized images."},
        {"element": "content", "severity": "INFO", "before": "Hash: abc123", "after": "Hash: def456", "recommendation": "Page content changed."},
    ]
    path = generate_drift_report(mock_baseline, mock_current, mock_diffs, "https://example.com", "2026-03-22T10:15:00+00:00")
    print(f"Test report: {path}")
