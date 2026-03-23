---
name: seo-drift
description: >
  SEO Drift Monitor - detects when page changes break critical SEO elements.
  Baselines a page's SEO state, then checks for regressions in schema, headings,
  meta tags, canonical, and Core Web Vitals. Generates visual before/after reports.
  Use when user says "seo drift", "drift monitor", "baseline", "seo check",
  "did anything break", "seo regression", "before and after", "protect seo",
  "monitor page", or "detect changes".
---

# SEO Drift Monitor

Protect your SEO work from being broken by page changes. Baseline a page, detect regressions, get fix recommendations.

## Commands

| Command | Description |
|---------|-------------|
| `/seo-drift baseline <url>` | Capture a "known good" snapshot of all SEO-critical elements |
| `/seo-drift check <url>` | Compare current state against the most recent baseline |
| `/seo-drift history <url>` | Show all baselines and checks for a URL |

## Baseline Workflow

When the user runs `/seo-drift baseline <url>`:

1. Run the baseline capture script:
   ```bash
   python3 ~/.claude/skills/seo-drift/scripts/baseline.py "<url>"
   ```

2. Parse the JSON output and present a formatted summary:
   ```
   Baseline saved for [domain] (ID: [id])

   Title: [title]
   H1: [h1 text] ([h1_count] total)
   Schema: [schema_count] blocks ([schema_types])
   Canonical: [canonical]
   Robots: [robots or "none"]
   OG Tags: [og_tags count]
   CWV: [score]/100 (LCP: [lcp]s, FCP: [fcp]s, CLS: [cls])
   ```

3. If the script returns an error, display it and suggest fixes.

**Optional flags:**
- Add `--skip-cwv` to skip the PageSpeed Insights API call (faster)

## Check Workflow

When the user runs `/seo-drift check <url>`:

1. Run the check script:
   ```bash
   python3 ~/.claude/skills/seo-drift/scripts/check.py "<url>"
   ```

2. Parse the JSON output. If there's an error about no baseline, tell the user to run `/seo-drift baseline <url>` first.

3. Present diffs grouped by severity:

   ```
   Drift Check for [domain]
   Baseline: [baseline_date] | Checked: [checked_at]

   CRITICAL ([count]):
   - [element]: [before] -> [after]
     Fix: [recommendation]

   WARNING ([count]):
   - [element]: [before] -> [after]
     Fix: [recommendation]

   INFO ([count]):
   - [element]: [before] -> [after]

   Report: [report_path]
   ```

4. For CRITICAL and WARNING diffs, cross-reference the appropriate claude-seo skill:
   - Schema issues -> recommend `/seo-schema` to regenerate
   - CWV regressions -> recommend `/seo-technical` for diagnosis
   - Content/heading issues -> recommend `/seo-page` for analysis
   - Meta tag issues -> recommend `/seo-page` for review

5. If a report was generated, tell the user they can open it in a browser.

## History Workflow

When the user runs `/seo-drift history <url>`:

1. Run:
   ```bash
   python3 -c "
   import sys; sys.path.insert(0, '$HOME/.claude/skills/seo-drift/scripts')
   from db import get_all_baselines, get_check_history, normalize_url
   import json
   url = '$URL'
   baselines = get_all_baselines(url)
   checks = get_check_history(url)
   print(json.dumps({'baselines': baselines, 'checks': checks}, indent=2, default=str))
   "
   ```
   Replace `$URL` with the actual URL.

2. Present as a timeline:
   ```
   History for [domain]:

   Baselines:
   #[id]  [date]  Title: "[title]"  Schema: [count] blocks  CWV: [score]/100
   #[id]  [date]  Title: "[title]"  Schema: [count] blocks  CWV: [score]/100

   Checks:
   #[id]  [date] vs baseline #[baseline_id]  [critical]C [warning]W [info]I
   ```

## Severity Classification

| Change | Severity | Why It Matters |
|--------|----------|----------------|
| Schema block removed | CRITICAL | Removes rich snippets from SERPs |
| Canonical changed/removed | CRITICAL | Can cause deindexing or duplicate content |
| robots noindex added | CRITICAL | Removes page from Google entirely |
| H1 removed or changed | CRITICAL | Primary ranking signal for the page |
| Title removed | CRITICAL | Most important on-page SEO element |
| Status code -> 4xx/5xx | CRITICAL | Page is inaccessible |
| Title text changed | WARNING | May affect click-through rate |
| Description changed | WARNING | Affects SERP snippet appearance |
| CWV regression >20% | WARNING | Core Web Vitals affect rankings |
| OG tags removed | WARNING | Affects social media sharing |
| Schema content modified | WARNING | May invalidate rich results |
| H2/H3 structure changed | INFO | Minor structural change |
| Content hash changed | INFO | Page text was updated |

## Data Storage

- Database: `~/.claude/seo-drift/baselines.db` (SQLite)
- Reports: `~/.claude/seo-drift/reports/`

## Dependencies

This skill requires:
- Python 3.10+
- `requests` (for HTTP fetching)
- `beautifulsoup4` (for HTML parsing)
- `curl` (for PageSpeed Insights API)

Install: `pip install requests beautifulsoup4`

## Integration with claude-seo

This skill extends the [claude-seo](https://github.com/AgriciDaniel/claude-seo) ecosystem by adding a defensive monitoring layer. While other seo-* skills optimize pages, seo-drift protects what's already optimized:

- Uses `seo/scripts/fetch_page.py` for HTTP fetching with SSRF prevention
- Uses `seo/scripts/parse_html.py` for SEO element extraction
- Recommends `seo-schema`, `seo-technical`, and `seo-page` skills for fixing detected issues
