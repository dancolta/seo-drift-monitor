# SEO Drift Monitor

**A defensive SEO extension for [claude-seo](https://github.com/AgriciDaniel/claude-seo) that detects when page changes break critical SEO elements.**

While other SEO tools help you *optimize* pages, SEO Drift Monitor *protects* what you've already optimized. Baseline a page, detect regressions, get visual before/after reports with fix recommendations.

> Built as an extension for the [claude-seo](https://github.com/AgriciDaniel/claude-seo) skill ecosystem for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

---

## The Problem

Every SEO team has this story: rankings were great, a developer pushed a redesign, and three weeks later you discover the FAQ schema was removed, the H1 was changed to an H2, and the hero image now takes 5 seconds to load. By then, Google has already re-crawled and your rankings have dropped.

**SEO Drift Monitor catches these breaks instantly** - before Google re-crawls, before rankings drop, before you lose traffic.

---

## What It Does

### 1. Baseline (`/seo-drift baseline <url>`)

Captures a complete "known good" snapshot of every SEO-critical element:

| Element | What's Captured |
|---------|----------------|
| **Title** | Full title tag text |
| **Meta Description** | Description content |
| **Canonical** | Canonical URL |
| **Meta Robots** | robots directives (index, noindex, etc.) |
| **Headings** | Full H1-H3 hierarchy with text |
| **Schema/JSON-LD** | All structured data blocks, parsed and hashed |
| **Open Graph** | All og:* meta tags |
| **Core Web Vitals** | Performance score, LCP, FCP, CLS, TBT via Google PageSpeed Insights API |
| **Screenshot** | Full-page desktop screenshot via Playwright |
| **Status Code** | HTTP response code |

Everything is stored in a local SQLite database for instant comparison.

### 2. Check (`/seo-drift check <url>`)

Re-fetches everything and diffs against the baseline. Every change is classified by severity:

#### CRITICAL (breaks that damage rankings)

| Change | Why It's Critical |
|--------|-------------------|
| Schema block removed | Removes rich snippets from SERPs - CTR drops immediately |
| Canonical changed/removed | Can cause deindexing or split page authority |
| `noindex` added to robots | Removes the page from Google entirely |
| H1 removed or text changed | Primary on-page ranking signal |
| Title tag removed | Most important SEO element gone |
| Status code becomes 4xx/5xx | Page is inaccessible to users and crawlers |

#### WARNING (changes that need review)

| Change | Why It Matters |
|--------|----------------|
| Title text changed | May affect click-through rate and keyword targeting |
| Meta description changed | Affects SERP snippet appearance |
| Core Web Vitals regression >20% | CWV are a ranking factor since 2021 |
| Open Graph tags removed | Breaks social media sharing previews |
| Schema content modified | May invalidate rich results eligibility |

#### INFO (minor changes to note)

| Change | Context |
|--------|---------|
| H2/H3 structure changed | Content restructured |
| Content hash changed | Page text was updated |

### 3. Visual Report

Every check generates an HTML report with:

- **Side-by-side screenshots** - baseline vs. current, with red border highlighting when critical diffs exist
- **Color-coded diff table** - red for critical, amber for warning, green for info
- **Fix recommendations** - specific, actionable guidance for each change
- **CWV comparison bars** - visual performance regression indicators with percentage changes
- **Summary cards** - at-a-glance severity counts

```
+--------------------------------------------------+
|  SEO DRIFT REPORT - example.com                  |
|  Baseline: Mar 20  ->  Check: Mar 22             |
|  2 CRITICAL | 1 WARNING | 1 INFO                 |
+--------------------------------------------------+
|  [Baseline Screenshot]  [Current Screenshot]      |
+--------------------------------------------------+
|  [RED]   Schema removed: Organization             |
|  [RED]   H1 changed: "Welcome" -> "New Homepage"  |
|  [AMBER] LCP: 3.2s -> 4.1s (+28%)                |
|  [GREEN] Content updated                          |
+--------------------------------------------------+
|  CWV: LCP  3.2s -> 4.1s  [=========>]  +28%     |
|       FCP  1.8s -> 1.9s  [==>]          +6%     |
+--------------------------------------------------+
```

### 4. History (`/seo-drift history <url>`)

Timeline view of all baselines and checks for a URL, showing how SEO elements have changed over time.

---

## Architecture

```
~/.claude/skills/seo-drift/          # Skill definition
    SKILL.md                          # Claude Code skill with workflow instructions
    scripts/
        db.py                         # SQLite persistence (baselines + checks)
        cwv.py                        # Google PageSpeed Insights API wrapper
        baseline.py                   # Capture baseline snapshots
        check.py                      # Diff engine + severity classification
        report.py                     # HTML visual report generator

~/.claude/seo-drift/                  # Runtime data (auto-created)
    baselines.db                      # SQLite database
    screenshots/                      # Baseline + check screenshots
    reports/                          # Generated HTML reports
```

### How It Integrates with claude-seo

SEO Drift Monitor is built as a first-class extension of the [claude-seo](https://github.com/AgriciDaniel/claude-seo) ecosystem:

**Reuses existing claude-seo infrastructure:**
- `seo/scripts/fetch_page.py` - HTTP fetching with SSRF prevention and redirect tracking
- `seo/scripts/parse_html.py` - SEO element extraction (title, meta, headings, schema, OG tags)
- `seo/scripts/capture_screenshot.py` - Playwright-based screenshot capture

**Cross-references claude-seo skills for fixes:**
- Schema issues -> recommends `/seo-schema` to regenerate JSON-LD
- Performance regressions -> recommends `/seo-technical` for CWV diagnosis
- Content/heading issues -> recommends `/seo-page` for deep analysis

**Fills a gap in the ecosystem:**
The existing claude-seo skills are all *offensive* tools - they audit, optimize, and generate. SEO Drift Monitor is the first *defensive* tool - it protects what the other skills have already optimized.

```
[claude-seo ecosystem]

  OFFENSIVE (optimize)          DEFENSIVE (protect)
  ==================          ====================
  /seo-audit                  /seo-drift baseline  <-- NEW
  /seo-page                   /seo-drift check     <-- NEW
  /seo-technical              /seo-drift history    <-- NEW
  /seo-schema
  /seo-content
  /seo-sitemap
  ...
```

---

## Installation

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- [claude-seo](https://github.com/AgriciDaniel/claude-seo) skill installed (for shared scripts)
- Python 3.10+

### Install Dependencies

```bash
pip install requests beautifulsoup4 playwright
playwright install chromium
```

### Install the Skill

Clone this repo into your Claude Code skills directory:

```bash
git clone https://github.com/dancolta/seo-drift-monitor.git ~/.claude/skills/seo-drift
```

Or copy manually:

```bash
# Copy skill files
cp -r seo-drift-monitor/ ~/.claude/skills/seo-drift/
```

The skill is immediately available - no registration needed. Claude Code auto-discovers skills in `~/.claude/skills/`.

---

## Usage Examples

### Baseline a page after optimization

```
You: /seo-drift baseline https://example.com/pricing

Claude: Baseline saved for example.com (ID: 1)

  Title: "Pricing Plans | Example"
  H1: "Simple, Transparent Pricing" (1 total)
  Schema: 2 blocks (Organization, WebPage)
  Canonical: https://example.com/pricing
  Robots: none
  OG Tags: 5
  CWV: 72/100 (LCP: 3.2s, FCP: 1.8s, CLS: 0.05)
  Screenshot saved.
```

### Check after a deploy

```
You: /seo-drift check https://example.com/pricing

Claude: Drift Check for example.com
  Baseline: Mar 20, 2026 14:30 UTC | Checked: Mar 22, 2026 10:15 UTC

  CRITICAL (2):
  - Schema > Organization: Organization schema present -> Removed
    Fix: Re-add Organization JSON-LD schema. Use /seo-schema to generate.
  - H1: "Simple, Transparent Pricing" -> "New Pricing Page"
    Fix: Verify the new H1 contains your target keywords.

  WARNING (1):
  - CWV > LCP: 3.2s -> 4.1s (+28%)
    Fix: LCP regressed by 28%. Use /seo-technical to diagnose.

  INFO (1):
  - Content: Page content changed

  Report: ~/.claude/seo-drift/reports/example_com_20260322.html
```

### View history

```
You: /seo-drift history https://example.com/pricing

Claude: History for example.com/pricing:

  Baselines:
  #3  Mar 22, 2026  Title: "New Pricing Page"   Schema: 1 block   CWV: 58/100
  #1  Mar 20, 2026  Title: "Pricing Plans"       Schema: 2 blocks  CWV: 72/100

  Checks:
  #1  Mar 22 vs baseline #1  2 CRITICAL  1 WARNING  1 INFO
```

---

## Technical Details

### SQLite Schema

```sql
-- Stores complete page snapshots as "known good" states
CREATE TABLE baselines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    url_hash        TEXT NOT NULL,           -- SHA256 of normalized URL
    created_at      TEXT NOT NULL,           -- ISO 8601 timestamp
    html_hash       TEXT NOT NULL,           -- SHA256 of full HTML body
    title           TEXT,
    meta_description TEXT,
    canonical       TEXT,
    robots          TEXT,
    headings_json   TEXT NOT NULL,           -- {h1: [...], h2: [...], h3: [...]}
    schema_json     TEXT NOT NULL,           -- Array of parsed JSON-LD blocks
    schema_hash     TEXT NOT NULL,           -- SHA256 of canonical JSON
    og_json         TEXT NOT NULL,           -- Dict of og:* tags
    cwv_json        TEXT,                    -- {score, fcp, lcp, tbt, cls, si}
    screenshot_path TEXT,
    status_code     INTEGER
);

-- Stores each comparison run with detected diffs
CREATE TABLE checks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    baseline_id     INTEGER NOT NULL REFERENCES baselines(id),
    url             TEXT NOT NULL,
    checked_at      TEXT NOT NULL,
    diffs_json      TEXT NOT NULL,           -- Array of classified diffs
    screenshot_path TEXT,
    report_path     TEXT
);
```

### URL Normalization

URLs are normalized before storage and comparison:
- Scheme and host lowercased
- Default ports stripped (80 for HTTP, 443 for HTTPS)
- Trailing slashes removed
- Query parameters sorted alphabetically
- UTM tracking parameters stripped (`utm_source`, `utm_medium`, etc.)

### Core Web Vitals

CWV data is fetched from the **Google PageSpeed Insights API** (not local Lighthouse), which:
- Produces scores that match [pagespeed.web.dev](https://pagespeed.web.dev) exactly
- Gives credible mobile scores (40-70 range vs. artificially low 30-40 from local Lighthouse)
- Includes secondary findings (render-blocking resources, unoptimized images, unused JS)
- Retries 3 times with backoff on failure

### Report Generation

Reports are self-contained HTML files with:
- Screenshots embedded as base64 data URIs (no external dependencies)
- Inline CSS for portability (no external stylesheets)
- Traffic-light color system (red/amber/green)
- Responsive layout that works in any browser

---

## Why This Exists

Most SEO damage isn't caused by bad strategy. It's caused by:

1. **Developer deploys** that accidentally remove schema, change heading hierarchy, or add `noindex`
2. **CMS updates** that alter meta tags, break canonical tags, or change page structure
3. **Content edits** that remove H1 tags or alter title tags without considering SEO impact
4. **Plugin/theme changes** that modify structured data or add render-blocking resources

These breaks are typically discovered **weeks later** when rankings have already dropped. SEO Drift Monitor catches them **immediately** after the change happens.

### The Workflow

```
1. Optimize a page with claude-seo tools
2. Run /seo-drift baseline to lock in the "known good" state
3. After any deploy or content change, run /seo-drift check
4. Fix any CRITICAL/WARNING diffs using the recommended claude-seo skills
5. Re-baseline after fixes to update the "known good" state
```

---

## Project Structure

```
seo-drift-monitor/
  SKILL.md              # Claude Code skill definition
  README.md             # This file
  scripts/
    db.py               # SQLite operations (init, save, query, URL normalization)
    cwv.py              # PageSpeed Insights API wrapper (adapted from proven PSI integration)
    baseline.py         # Baseline capture pipeline (fetch -> parse -> screenshot -> CWV -> store)
    check.py            # Diff engine (compare -> classify -> recommend -> report)
    report.py           # HTML report generator (side-by-side screenshots, diff table, CWV bars)
```

---

## Credits

- Built as an extension for [claude-seo](https://github.com/AgriciDaniel/claude-seo) by [@AgriciDaniel](https://github.com/AgriciDaniel)
- Uses Google [PageSpeed Insights API](https://developers.google.com/speed/docs/insights/v5/get-started) for Core Web Vitals
- Screenshots powered by [Playwright](https://playwright.dev/)
- Built by [Dan Colta](https://github.com/dancolta) at [NodeSparks](https://nodesparks.com)

---

## License

MIT
