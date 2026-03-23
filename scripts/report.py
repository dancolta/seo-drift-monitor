#!/usr/bin/env python3
"""
Visual HTML report generator for SEO Drift Monitor.

Dark-themed drift report — data-first, no fluff.
"""

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from db import REPORTS_DIR, init_db


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt_date(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except (ValueError, AttributeError):
        return iso_str or "—"


def open_report(path: str):
    """Open a report file in the default browser."""
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif platform.system() == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # silently fail if no browser available


# --- Colors ---

SEV_COLORS = {
    "CRITICAL": {"accent": "#e5484d", "dim": "#e5484d30", "text": "#ff9592"},
    "WARNING":  {"accent": "#f5a623", "dim": "#f5a62330", "text": "#ffc96b"},
    "INFO":     {"accent": "#46a758", "dim": "#46a75830", "text": "#4cc38a"},
}


def _header(domain, b_date, c_date, crit, warn, info):
    total = crit + warn + info
    if crit > 0:
        tag, tag_c = "Drift detected", "#e5484d"
    elif warn > 0:
        tag, tag_c = "Changes found", "#f5a623"
    else:
        tag, tag_c = "No issues", "#46a758"

    def _count_pill(label, n, color):
        o = "1" if n > 0 else "0.3"
        return f'''<div style="display:flex;align-items:center;gap:6px;opacity:{o}">
            <span style="width:7px;height:7px;border-radius:50%;background:{color};display:inline-block"></span>
            <span style="font-variant-numeric:tabular-nums;font-weight:600;color:#ededed">{n}</span>
            <span style="color:#999">{label}</span>
        </div>'''

    return f'''
    <div style="margin-bottom:32px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
            <div style="font-size:15px;font-weight:600;color:#ededed;letter-spacing:-0.2px">{_escape(domain)}</div>
            <div style="font-size:11px;font-weight:600;color:{tag_c};background:{tag_c}15;
                        padding:3px 10px;border-radius:4px;border:1px solid {tag_c}30">{tag}</div>
        </div>
        <div style="display:flex;gap:20px;font-size:12px;color:#999;margin-bottom:16px">
            <div><span style="color:#aaa">Baseline</span> {_fmt_date(b_date)}</div>
            <div style="color:#555">&#x2192;</div>
            <div><span style="color:#aaa">Checked</span> {_fmt_date(c_date)}</div>
        </div>
        <div style="display:flex;gap:20px;font-size:12px;padding:10px 0;border-top:1px solid #1a1a1a;border-bottom:1px solid #1a1a1a">
            {_count_pill("critical", crit, SEV_COLORS["CRITICAL"]["accent"])}
            {_count_pill("warning", warn, SEV_COLORS["WARNING"]["accent"])}
            {_count_pill("info", info, SEV_COLORS["INFO"]["accent"])}
            <div style="margin-left:auto;color:#777">{total} total</div>
        </div>
    </div>'''


def _changes(diffs):
    if not diffs:
        return '''<div style="text-align:center;padding:40px 0;color:#46a758;font-size:13px">
            No drift detected &mdash; all SEO elements match baseline.</div>'''

    out = ""
    cur_sev = None
    for d in diffs:
        sev = d["severity"]
        c = SEV_COLORS.get(sev, SEV_COLORS["INFO"])
        if sev != cur_sev:
            cur_sev = sev
            out += f'''<div style="font-size:11px;font-weight:600;color:{c["accent"]};
                margin:24px 0 8px;text-transform:uppercase;letter-spacing:0.5px">{sev}</div>'''

        el = d["element"].replace("_", " ").replace(".", " &rsaquo; ")
        before = _escape(d.get("before", ""))
        after = _escape(d.get("after", ""))
        rec = _escape(d.get("recommendation", ""))

        out += f'''
        <div style="border-left:2px solid {c["accent"]};padding:12px 16px;margin-bottom:2px;
                    background:#111;border-radius:0 4px 4px 0">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
                <span style="font-size:13px;font-weight:600;color:#ccc">{el}</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#1a1a1a;
                        border-radius:4px;overflow:hidden;margin-bottom:8px;font-size:12px;
                        font-family:'SF Mono','Fira Code','Consolas',monospace">
                <div style="background:#0d0d0d;padding:8px 10px">
                    <div style="color:#777;font-size:9px;font-weight:600;text-transform:uppercase;
                                letter-spacing:0.8px;margin-bottom:3px;font-family:Inter,sans-serif">before</div>
                    <div style="color:#bbb;word-break:break-word;line-height:1.5">{before}</div>
                </div>
                <div style="background:#0d0d0d;padding:8px 10px">
                    <div style="color:{c["accent"]};font-size:9px;font-weight:600;text-transform:uppercase;
                                letter-spacing:0.8px;margin-bottom:3px;font-family:Inter,sans-serif">after</div>
                    <div style="color:{c["text"]};word-break:break-word;line-height:1.5">{after}</div>
                </div>
            </div>
            <div style="font-size:11px;color:#888;line-height:1.5">{rec}</div>
        </div>'''

    return f'''<div style="margin-bottom:32px">
        <div style="font-size:12px;font-weight:600;color:#aaa;margin-bottom:4px;
                    text-transform:uppercase;letter-spacing:0.5px">Changes</div>
        {out}
    </div>'''


def _cwv(b_cwv, c_cwv):
    if not b_cwv or not c_cwv:
        return ""

    bs = b_cwv.get("score", 0)
    cs = c_cwv.get("score", 0)
    diff = cs - bs
    sc = "#46a758" if diff >= 0 else "#f5a623" if diff > -10 else "#e5484d"

    rows = ""
    for abbr, bk in [("LCP","lcp"), ("FCP","fcp"), ("CLS","cls"), ("TBT","tbt")]:
        bv = b_cwv.get(bk, 0)
        cv = c_cwv.get(bk, 0)
        if bv == 0 and cv == 0:
            continue
        unit = "ms" if bk == "tbt" else "" if bk == "cls" else "s"
        pct = ((cv - bv) / bv) * 100 if bv > 0 else 0
        mc = "#e5484d" if pct > 20 else "#f5a623" if pct > 0 else "#46a758"
        mx = max(bv, cv, 0.001)
        bw = max(min(bv / mx * 100, 100), 3)
        aw = max(min(cv / mx * 100, 100), 3)
        sign = "+" if pct > 0 else ""

        rows += f'''
        <div style="margin-bottom:12px">
            <div style="display:flex;justify-content:space-between;margin-bottom:5px;font-size:12px">
                <span style="color:#bbb;font-weight:500">{abbr}</span>
                <span style="color:{mc};font-weight:600;font-variant-numeric:tabular-nums">{sign}{pct:.0f}%</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                <span style="width:48px;text-align:right;font-size:11px;color:#888;
                             font-family:'SF Mono',monospace;font-variant-numeric:tabular-nums">{bv}{unit}</span>
                <div style="flex:1;background:#1a1a1a;border-radius:2px;height:6px;overflow:hidden">
                    <div style="width:{bw}%;background:#333;height:100%;border-radius:2px"></div>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
                <span style="width:48px;text-align:right;font-size:11px;color:{mc};font-weight:500;
                             font-family:'SF Mono',monospace;font-variant-numeric:tabular-nums">{cv}{unit}</span>
                <div style="flex:1;background:#1a1a1a;border-radius:2px;height:6px;overflow:hidden">
                    <div style="width:{aw}%;background:{mc};height:100%;border-radius:2px"></div>
                </div>
            </div>
        </div>'''

    return f'''
    <div style="margin-bottom:32px">
        <div style="font-size:12px;font-weight:600;color:#aaa;margin-bottom:12px;
                    text-transform:uppercase;letter-spacing:0.5px">Core Web Vitals</div>
        <div style="display:flex;align-items:baseline;gap:12px;margin-bottom:20px;
                    padding:14px;background:#111;border-radius:6px">
            <div style="flex:1;text-align:center">
                <div style="font-size:9px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:2px">Baseline</div>
                <div style="font-size:28px;font-weight:700;color:#ccc;font-variant-numeric:tabular-nums">{bs}</div>
            </div>
            <div style="font-size:18px;font-weight:700;color:{sc};font-variant-numeric:tabular-nums">
                {"+" if diff > 0 else ""}{diff}<span style="font-size:10px;color:#888;margin-left:2px">pts</span>
            </div>
            <div style="flex:1;text-align:center">
                <div style="font-size:9px;color:#888;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:2px">Current</div>
                <div style="font-size:28px;font-weight:700;color:{sc};font-variant-numeric:tabular-nums">{cs}</div>
            </div>
        </div>
        {rows}
    </div>'''


def generate_drift_report(baseline, current, diffs, url, check_time):
    """Generate HTML drift report. Returns path. Auto-opens in browser."""
    init_db()
    domain = urlparse(url).netloc.replace("www.", "")
    ts = check_time.replace(":", "-").replace("+", "")[:19]

    crit = len([d for d in diffs if d["severity"] == "CRITICAL"])
    warn = len([d for d in diffs if d["severity"] == "WARNING"])
    inf  = len([d for d in diffs if d["severity"] == "INFO"])

    header = _header(domain, baseline.get("created_at", ""), check_time, crit, warn, inf)
    changes = _changes(diffs)
    cwv = _cwv(baseline.get("cwv"), current.get("cwv"))

    filename = f"{domain.replace('.', '_')}_{ts}_drift.html"
    pdf_filename = filename.replace(".html", ".pdf")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Drift Report &mdash; {_escape(domain)}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
    font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
    background:#0a0a0a;color:#999;line-height:1.5;
    -webkit-font-smoothing:antialiased;font-size:13px
}}
.r{{max-width:680px;margin:0 auto;padding:32px 24px 48px}}
.dl{{
    position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:100;
    display:flex;align-items:center;gap:6px;
    padding:8px 16px;background:#1a1a1a;color:#888;
    border:1px solid #222;border-radius:6px;
    font:500 12px/1 'Inter',sans-serif;cursor:pointer;
    transition:border-color .15s,color .15s
}}
.dl:hover{{border-color:#444;color:#ccc}}
.dl svg{{width:14px;height:14px}}
@media print{{
    body{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
    .dl{{display:none!important}}
    .r{{padding:16px;max-width:100%}}
    @page{{size:A4;margin:10mm}}
}}
@media(max-width:640px){{.r{{padding:20px 14px 36px}}.dl{{bottom:14px}}}}
</style>
</head>
<body>
<div class="r">
{header}
{changes}
{cwv}
<div style="padding-top:16px;border-top:1px solid #1a1a1a;font-size:10px;color:#666;text-align:center">
    <a href="https://github.com/dancolta/seo-drift-monitor" style="color:#777;text-decoration:none">seo-drift-monitor</a>
    <span style="margin:0 6px">/</span>
    <a href="https://github.com/AgriciDaniel/claude-seo" style="color:#777;text-decoration:none">claude-seo</a>
</div>
</div>
<a class="dl" href="{pdf_filename}" download="{pdf_filename}" title="Download PDF" style="text-decoration:none">
<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2v8M5 7l3 3 3-3M3 12h10"/></svg>
PDF
</a>
</body>
</html>'''

    report_path = os.path.join(REPORTS_DIR, filename)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Report saved: {report_path}", file=sys.stderr)

    # Generate PDF alongside HTML
    try:
        from pdf import html_to_pdf
        html_to_pdf(report_path)
    except Exception as e:
        print(f"  [WARN] PDF generation skipped: {e}", file=sys.stderr)

    # Auto-open in browser
    open_report(report_path)

    return report_path


if __name__ == "__main__":
    mock_baseline = {
        "created_at": "2026-03-20T14:30:00+00:00",
        "cwv": {"score": 72, "lcp": 3.2, "fcp": 1.8, "cls": 0.05, "tbt": 180},
    }
    mock_current = {
        "cwv": {"score": 58, "lcp": 4.1, "fcp": 1.9, "cls": 0.04, "tbt": 195},
    }
    mock_diffs = [
        {"element": "schema.Organization", "severity": "CRITICAL",
         "before": "Organization schema present", "after": "Removed",
         "recommendation": "Re-add Organization JSON-LD schema."},
        {"element": "canonical", "severity": "CRITICAL",
         "before": "https://example.com/services", "after": "(removed)",
         "recommendation": "Canonical tag was removed. Add it back to prevent duplicate content issues."},
        {"element": "h1", "severity": "CRITICAL",
         "before": "Professional Web Design Services", "after": "(removed)",
         "recommendation": "H1 heading was removed. Every page needs exactly one H1."},
        {"element": "robots", "severity": "CRITICAL",
         "before": "index, follow", "after": "noindex, nofollow",
         "recommendation": "noindex was added. This will remove the page from Google."},
        {"element": "title", "severity": "WARNING",
         "before": "Acme Digital Agency | Web Design & SEO", "after": "Acme Digital",
         "recommendation": "Title tag changed. Ensure target keywords are included."},
        {"element": "meta_description", "severity": "WARNING",
         "before": "Transform your online presence with data-driven SEO and stunning web design...",
         "after": "(removed)",
         "recommendation": "Meta description was removed."},
        {"element": "cwv.lcp", "severity": "WARNING",
         "before": "3.2s", "after": "4.1s (+28%)",
         "recommendation": "LCP regressed by 28%."},
        {"element": "open_graph", "severity": "WARNING",
         "before": "6 OG tags", "after": "2 OG tags (removed: og:image, og:title, og:type, og:description)",
         "recommendation": "Open Graph tags were removed."},
        {"element": "schema.WebSite", "severity": "INFO",
         "before": "(not present)", "after": "WebSite schema added",
         "recommendation": "New schema added. Validate with Rich Results Test."},
        {"element": "headings.h2", "severity": "INFO",
         "before": "4 H2 headings", "after": "6 H2 headings",
         "recommendation": "H2 structure changed."},
        {"element": "content", "severity": "INFO",
         "before": "Content hash: a1b2c3d4e5f6", "after": "Content hash: f6e5d4c3b2a1",
         "recommendation": "Page content changed."},
    ]

    path = generate_drift_report(
        mock_baseline, mock_current, mock_diffs,
        "https://seo-drift-demo.vercel.app", "2026-03-23T10:15:00+00:00",
    )
    print(f"Report: {path}")
