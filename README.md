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

## What Gets Captured

Intentionally focused on the elements most commonly broken by deploys, CMS updates, and content edits. No full crawl, no content quality analysis, no image audits — just the things that silently tank rankings when someone changes them without checking.

Every baseline stores:

| Element | Detail |
|---------|--------|
| Title | Full title tag |
| Meta Description | Description content |
| Canonical | Canonical URL |
| Meta Robots | index/noindex directives |
| Headings | H1-H3 hierarchy with text |
| Schema/JSON-LD | All structured data blocks, parsed + hashed |
| Open Graph | All og:* tags |
| Core Web Vitals | Score, LCP, FCP, CLS, TBT (via PageSpeed Insights API) |
| Status Code | HTTP response |

Stored in a local SQLite database at `~/.claude/seo-drift/baselines.db`.

---

## Severity Classification

Every change detected by `/seo-drift check` is classified:

### CRITICAL -- breaks that damage rankings

| Change | Impact |
|--------|--------|
| Schema block removed | Rich snippets disappear from SERPs |
| Canonical changed/removed | Can deindex the page or split authority |
| `noindex` added | Removes page from Google entirely |
| H1 removed or changed | Primary ranking signal altered |
| Title removed | Most important on-page element gone |
| Status code 4xx/5xx | Page inaccessible |

### WARNING -- changes that need review

| Change | Impact |
|--------|--------|
| Title text changed | Affects CTR and keyword targeting |
| Description changed | Alters SERP snippet |
| CWV regression >20% | Performance is a ranking factor |
| OG tags removed | Breaks social sharing |
| Schema modified | May invalidate rich results |

### INFO -- noted, no action needed

| Change | Context |
|--------|---------|
| H2/H3 changed | Content restructured |
| Content hash changed | Page text updated |

---

## Visual Report

Every check generates an HTML report:

- Severity summary cards (at-a-glance counts)
- Color-coded change list (red/amber/green) with before/after values in monospace
- Fix recommendations per change
- CWV comparison bars with percentage changes

```
+--------------------------------------------------+
|  SEO DRIFT REPORT - example.com                  |
|  Baseline: Mar 20  ->  Check: Mar 22             |
|  2 CRITICAL | 1 WARNING | 1 INFO                 |
+--------------------------------------------------+
|  [RED]   Schema removed: Organization             |
|          Before: present  After: Removed           |
|  [RED]   H1: "Welcome" -> "New Homepage"          |
|  [AMBER] LCP: 3.2s -> 4.1s (+28%)                |
|  [GREEN] Content updated                          |
+--------------------------------------------------+
|  CWV: Score 72 -> 58 (-14pts)                    |
|       LCP  3.2s -> 4.1s  [=========>]  +28%     |
+--------------------------------------------------+
```

Self-contained HTML with inline CSS. No screenshots needed — all changes are code/backend elements shown as structured data. Open in any browser.

---

## Usage Examples

**Baseline after optimization:**
```
/seo-drift baseline https://example.com/pricing

Baseline saved (ID: 1)
  Title: "Pricing Plans | Example"
  H1: "Simple, Transparent Pricing"
  Schema: 2 blocks (Organization, WebPage)
  CWV: 72/100 (LCP: 3.2s)
```

**Check after a deploy:**
```
/seo-drift check https://example.com/pricing

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
pip install requests beautifulsoup4

# Install the skill
git clone https://github.com/dancolta/seo-drift-monitor.git ~/.claude/skills/seo-drift
```

Immediately available -- Claude Code auto-discovers skills in `~/.claude/skills/`.

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
/seo-audit                    /seo-drift baseline  <-- NEW
/seo-page                     /seo-drift check     <-- NEW
/seo-technical                /seo-drift history    <-- NEW
/seo-schema
/seo-content
/seo-sitemap
```

---

## Architecture

```
~/.claude/skills/seo-drift/       # Skill definition
    SKILL.md                       # Workflow instructions
    scripts/
        db.py                      # SQLite persistence + URL normalization
        cwv.py                     # PageSpeed Insights API wrapper
        baseline.py                # Capture snapshots
        check.py                   # Diff engine + severity classification
        report.py                  # HTML report generator

~/.claude/seo-drift/              # Runtime data (auto-created)
    baselines.db                   # SQLite database
    reports/                       # Generated HTML reports
```

### Technical Notes

**URL normalization:** Lowercase scheme/host, strip default ports, remove trailing slashes, sort query params, strip UTM parameters.

**CWV source:** Google PageSpeed Insights API (not local Lighthouse). Scores match [pagespeed.web.dev](https://pagespeed.web.dev). 3 retries with backoff.

**HTTP fetching:** Tries `requests` first, falls back to `curl -sk` on SSL certificate errors.

---

## Credits

- Extension for [claude-seo](https://github.com/AgriciDaniel/claude-seo) by [@AgriciDaniel](https://github.com/AgriciDaniel)
- [PageSpeed Insights API](https://developers.google.com/speed/docs/insights/v5/get-started) for Core Web Vitals
- Built by [Dan Colta](https://github.com/dancolta) at [NodeSparks](https://nodesparks.com)

## License

MIT
