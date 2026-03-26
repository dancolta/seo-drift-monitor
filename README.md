# SEO Drift Monitor

**Detect when page changes break your SEO.** A defensive extension for [claude-seo](https://github.com/AgriciDaniel/claude-seo).

Other SEO tools optimize. This one protects what you've already optimized.

> Extension for the [claude-seo](https://github.com/AgriciDaniel/claude-seo) skill ecosystem for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

---

## How It Works

Think of it like git for SEO. You **baseline** a page when it's in a good state, then **check** it later to see what broke.

```
1. Optimize a page with claude-seo
2. /seo-drift baseline <url>       -- save the "known good" state
3. Developer pushes changes...
4. /seo-drift check <url>          -- compare against the baseline
5. Fix issues using recommended claude-seo skills
6. /seo-drift baseline <url>       -- save the new "known good"
7. Repeat after every deploy
```

**The baseline is explicit.** You choose when to save it. Each check compares against the most recent baseline for that URL. You can create multiple baselines over time -- the check always uses the latest one.

---

## Commands

| Command | What it does |
|---------|-------------|
| `/seo-drift baseline <url>` | Snapshot all SEO-critical elements as "known good" |
| `/seo-drift check <url>` | Compare current state against the latest baseline |
| `/seo-drift history <url>` | Show all baselines and checks for a URL |

---

## What Gets Checked

Intentionally focused on the elements most commonly broken by deploys, CMS updates, and content edits. No full crawl, no content quality analysis, no image audits -- just the things that silently tank rankings when someone changes them without checking.

### Elements Captured in Every Baseline

| Element | What's stored | Why it matters |
|---------|---------------|----------------|
| **Title tag** | Full `<title>` text | Most important on-page ranking signal. Changes affect keyword targeting and SERP CTR |
| **Meta description** | `<meta name="description">` content | Controls SERP snippet appearance. Removal or bad rewording hurts CTR |
| **Canonical URL** | `<link rel="canonical">` href | Incorrect canonical can deindex the page or split link authority across duplicates |
| **Meta robots** | `<meta name="robots">` directives | An accidental `noindex` removes the page from Google entirely |
| **H1 heading** | All `<h1>` text (count + content) | Primary on-page heading signal. Removal or change alters keyword relevance |
| **H2 headings** | All `<h2>` text (count + content) | Content structure and topical coverage signal |
| **H3 headings** | All `<h3>` text (count + content) | Supporting content structure |
| **Schema / JSON-LD** | All `<script type="application/ld+json">` blocks, parsed + hashed | Powers rich snippets (stars, FAQs, breadcrumbs). Removing a schema type kills its rich result |
| **Open Graph tags** | All `og:*` meta tags | Controls how the page appears when shared on social media (Facebook, LinkedIn, Twitter cards) |
| **Core Web Vitals** | Performance score, LCP, FCP, CLS, TBT via PageSpeed Insights API | Performance is a ranking factor. CWV regressions >20% indicate deploy-introduced issues |
| **HTTP status code** | Response status (200, 301, 404, 500, etc.) | A page returning 4xx/5xx is completely invisible to search engines |
| **HTML hash** | SHA-256 of full page HTML | Catch-all change detector. If nothing else triggers but the hash changed, content was modified |
| **Schema hash** | SHA-256 of serialized JSON-LD | Detects subtle schema content changes even when the same @types are present |

### URL Normalization

Before storing or comparing, every URL is normalized to prevent false positives:

- Lowercases scheme and hostname
- Strips default ports (80/443)
- Removes trailing slashes
- Sorts query parameters alphabetically
- Removes `utm_*` tracking parameters

This means `https://Example.com/page/?utm_source=twitter&b=2&a=1` and `https://example.com/page?a=1&b=2` are treated as the same URL.

---

## Severity Classification

Every change detected by `/seo-drift check` is classified into one of three severity levels.

### CRITICAL -- breaks that damage rankings

These are changes that can cause immediate, measurable ranking loss or complete deindexing. Action required.

| Change detected | What the diff engine checks | SEO impact |
|----------------|----------------------------|------------|
| **Schema block removed** | Compares `@type` values between baseline and current. Any type present in baseline but missing in current triggers this | Rich snippets (stars, FAQs, breadcrumbs, etc.) disappear from SERPs. Can take weeks to recover |
| **Canonical changed** | Compares normalized canonical URLs (strips protocol + trailing slash) | Incorrect canonical tells Google to index a different URL. Splits link equity, can cause deindexing |
| **Canonical removed** | Baseline had a canonical, current has none | Without a canonical, Google may choose a duplicate as the "primary" version |
| **noindex added** | Checks if `noindex` appears in current robots but not baseline | Removes the page from Google's index entirely. Most common accidental SEO disaster |
| **H1 removed** | Baseline had H1(s), current has none | Primary heading signal is gone. Google loses context on what the page is about |
| **H1 changed** | Case-insensitive text comparison of first H1 | Primary ranking signal altered. New text may not contain target keywords |
| **Title removed** | Baseline had a title, current is empty | Most important on-page element is missing. Google will auto-generate a title (usually poorly) |
| **Status code 4xx/5xx** | Baseline was < 400, current is >= 400 | Page is completely inaccessible. Will be dropped from index after repeated crawl failures |

### WARNING -- changes that need review

These changes may be intentional but should be verified. They affect rankings, CTR, or social sharing.

| Change detected | What the diff engine checks | SEO impact |
|----------------|----------------------------|------------|
| **Title text changed** | String comparison (baseline vs current) | Affects keyword targeting and SERP click-through rate |
| **Description changed** | String comparison, truncated to 100 chars in diff display | Alters SERP snippet. Bad rewording can drop CTR significantly |
| **CWV metric regressed >20%** | Per-metric comparison: LCP, FCP, CLS, TBT. Triggers when `(current - baseline) / baseline > 0.20` | Core Web Vitals are a ranking factor. >20% regression indicates a real performance problem, not noise |
| **CWV score dropped 10+ points** | Overall PageSpeed score comparison | Aggregate performance decline. Indicates multiple contributing issues |
| **OG tags removed** | Compares OG tag keys between baseline and current | Broken social sharing cards on Facebook, LinkedIn, Twitter |
| **Schema content modified** | Same `@type` values exist but `schema_hash` differs | Schema content changed (e.g., different business name, address, or FAQ answers). May invalidate rich results |

### INFO -- noted, no action needed

Low-severity changes that are tracked for awareness but rarely require intervention.

| Change detected | What the diff engine checks | SEO impact |
|----------------|----------------------------|------------|
| **New schema type added** | `@type` present in current but not in baseline | New structured data. Should be validated with Google's Rich Results Test |
| **H2 structure changed** | List comparison of all H2 texts | Content was restructured. Review for keyword relevance |
| **Content hash changed** | SHA-256 of full HTML differs, but no other diffs triggered | Catch-all: page content was updated but no specific SEO element was broken |

---

## Report Output

### Visual HTML/PDF Report

Every check generates a self-contained HTML report at `~/.claude/seo-drift/reports/`:

- **Header card**: domain, baseline date -> check date, severity pill counts (red/amber/green), status badge ("Drift detected" / "Changes found" / "No issues")
- **Changes section**: color-coded cards grouped by severity, each showing:
  - Element name
  - Before/after values in monospace side-by-side grid
  - Fix recommendation
- **CWV comparison**: score delta display + per-metric bar charts (LCP, FCP, CLS, TBT) with percentage change
- **PDF export**: download button at bottom generates a PDF via Playwright screenshot (retina quality, 150 DPI)

The report auto-opens in the browser when generated. Dark theme (`#0a0a0a` background), Inter + Fira Code fonts.

### Chat Output

The check script outputs JSON to stdout which Claude presents as a severity-grouped summary:

```
Drift Check for example.com
Baseline: Mar 20, 2026 | Checked: Mar 22, 2026

CRITICAL (2):
  schema.Organization: Organization schema present -> Removed
    Fix: Re-add Organization JSON-LD schema. Use /seo-schema to generate the correct markup.
  canonical: /products/shoes -> (removed)
    Fix: Canonical tag was removed. Add it back to prevent duplicate content issues.

WARNING (1):
  cwv.lcp: 3.2s -> 4.1s (+28%)
    Fix: LCP regressed by 28%. Use /seo-technical to diagnose performance issues.

INFO (1):
  headings.h2: 4 H2 headings -> 6 H2 headings
    Review for keyword relevance.

Report: ~/.claude/seo-drift/reports/example_com_2026-03-22T10-15-00_drift.html
```

---

## Usage Examples

**Baseline after optimization:**
```
/seo-drift baseline https://example.com/pricing

Baseline saved for example.com (ID: 1)

Title: "Pricing Plans | Example"
H1: "Simple, Transparent Pricing" (1 total)
Schema: 2 blocks (Organization, WebPage)
Canonical: https://example.com/pricing
Robots: index, follow
OG Tags: 6
CWV: 72/100 (LCP: 3.2s, FCP: 1.8s, CLS: 0.05)
```

**Check after a deploy:**
```
/seo-drift check https://example.com/pricing

Drift Check for example.com
Baseline: Mar 20, 2026 | Checked: Mar 22, 2026

CRITICAL (2):
  Schema > Organization: present -> Removed
  H1: "Simple, Transparent Pricing" -> "New Pricing Page"

WARNING (1):
  LCP: 3.2s -> 4.1s (+28%)

Report: ~/.claude/seo-drift/reports/example_com_20260322.html
```

**View history:**
```
/seo-drift history https://example.com/pricing

Baselines:
  #3  Mar 22  "New Pricing Page"   1 schema   58/100
  #1  Mar 20  "Pricing Plans"      2 schemas  72/100

Checks:
  #1  Mar 22 vs baseline #1  2C 1W 1I
```

---

## Installation

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) + [claude-seo](https://github.com/AgriciDaniel/claude-seo) + Python 3.10+

```bash
# Install dependencies
pip3 install requests beautifulsoup4 playwright Pillow

# Install Playwright browser
python3 -m playwright install chromium

# Install the skill
git clone https://github.com/dancolta/seo-drift-monitor.git ~/.claude/skills/seo-drift
```

Immediately available -- Claude Code auto-discovers skills in `~/.claude/skills/`.

---

## Architecture

```
~/.claude/skills/seo-drift/       # Skill definition
    SKILL.md                       # Claude workflow instructions
    README.md                      # This file
    requirements.txt               # Python dependencies
    scripts/
        db.py                      # SQLite persistence + URL normalization
        cwv.py                     # PageSpeed Insights API wrapper (3 retries, 10s/20s backoff)
        baseline.py                # Capture snapshots
        check.py                   # Diff engine + severity classification
        report.py                  # Dark-themed HTML report generator
        pdf.py                     # Playwright screenshot -> Pillow PDF conversion

~/.claude/seo-drift/              # Runtime data (auto-created on first use)
    baselines.db                   # SQLite database (baselines + checks tables)
    reports/                       # Generated HTML + PDF drift reports
```

### Data Flow

```
BASELINE:
  URL -> fetch HTML -> parse SEO elements -> compute hashes -> fetch CWV -> save to SQLite

CHECK:
  URL -> load latest baseline -> fetch HTML -> parse -> fetch CWV
       -> compute_diffs() (13 comparison rules, 3 severity levels)
       -> generate HTML report -> convert to PDF -> auto-open browser
       -> save check to SQLite -> output JSON summary
```

### Database Schema

**baselines** table: `id`, `url`, `url_hash` (indexed), `created_at` (indexed), `html_hash`, `title`, `meta_description`, `canonical`, `robots`, `headings_json`, `schema_json`, `schema_hash`, `og_json`, `cwv_json`, `screenshot_path`, `status_code`

**checks** table: `id`, `baseline_id` (FK, indexed), `url`, `checked_at`, `diffs_json`, `screenshot_path`, `report_path`

### External Dependencies

Imports from the parent `seo` skill:
- `~/.claude/skills/seo/scripts/fetch_page.py` -- HTTP fetching with SSRF prevention (falls back to `curl -sk` on SSL errors)
- `~/.claude/skills/seo/scripts/parse_html.py` -- SEO element extraction (title, meta, canonical, robots, h1-h3, JSON-LD, Open Graph)

### CWV Data Source

Uses **Google PageSpeed Insights API v5** (not local Lighthouse). Results match [pagespeed.web.dev](https://pagespeed.web.dev) so prospects can verify independently. Mobile strategy by default. API key required (hardcoded in `cwv.py`). 3 retries with 10s/20s exponential backoff.

---

## Integration with claude-seo

**Reuses claude-seo infrastructure:**
- `seo/scripts/fetch_page.py` -- HTTP fetching with SSRF prevention
- `seo/scripts/parse_html.py` -- SEO element extraction

**Cross-references claude-seo skills for fixes:**
- Schema issues -> `/seo-schema`
- Performance regressions -> `/seo-technical`
- Content/heading issues -> `/seo-page`

**Fills a gap in the ecosystem:**

```
OFFENSIVE (optimize)          DEFENSIVE (protect)
/seo-audit                    /seo-drift baseline  <-- THIS SKILL
/seo-page                     /seo-drift check     <-- THIS SKILL
/seo-technical                /seo-drift history    <-- THIS SKILL
/seo-schema
/seo-content
/seo-sitemap
```

---

## Credits

- Extension for [claude-seo](https://github.com/AgriciDaniel/claude-seo) by [@AgriciDaniel](https://github.com/AgriciDaniel)
- [PageSpeed Insights API](https://developers.google.com/speed/docs/insights/v5/get-started) for Core Web Vitals
- Built by [Dan Colta](https://github.com/dancolta) at [NodeSparks](https://nodesparks.com)

## License

MIT
