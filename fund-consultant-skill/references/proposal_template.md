# Proposal Document Template

## Output Format

Generate an HTML file saved as:
```
output/fund_proposals/FundProposal_[Profile]_[MonYYYY].html
```
Example: `output/fund_proposals/FundProposal_Moderate_Apr2026.html`

**e-Series Shortlist Mode:**
```
output/fund_proposals/FundShortlist_[Profile]_[ClientName]_[MonYYYY].html
```
Example: `output/fund_proposals/FundShortlist_Moderate_AhmadRazif_Apr2026.html`

Save all output files in the `output/fund_proposals/` directory.

## HTML Structure

The HTML document must be a single self-contained file (all CSS inline, no external dependencies).
Fixed 900px width — no responsive/mobile design needed. Output is viewed in desktop Chrome and
printed to PDF via Chrome Print.

### Required Sections (in order)

See **SKILL.md Step 7** for the authoritative section list, ordering, and content requirements.
The sections are: Cover Page → New Investor Foundation (if applicable) → Executive Summary →
Macro Context → Risk Profile → Fund Recommendations → Portfolio Summary → Portfolio Exposure
Breakdown → Investment Strategy → Fee Disclosure → Disclaimer.

---

## Design System — CSS Stylesheet

> **CRITICAL:** The following CSS **must be included VERBATIM** in every generated proposal HTML
> file. Do NOT modify colors, fonts, sizes, or spacing. Do NOT add Google Fonts imports, gradient
> backgrounds, decorative pseudo-elements, serif fonts, or diagonal stripe patterns. The design
> is intentionally minimal and flat. Copy this stylesheet exactly.

```css
:root {
  /* ── Primary ── */
  --navy: #1a365d;
  --blue: #2b6cb0;
  --white: #ffffff;

  /* ── Neutral ── */
  --text: #1a202c;
  --text-mid: #4a5568;
  --text-muted: #718096;
  --border: #e2e8f0;
  --bg-subtle: #f7fafc;

  /* ── Fund Type Accents ── */
  --equity: #2b6cb0;
  --fixed-income: #276749;
  --mixed-asset: #975a16;
  --money-market: #4a5568;
  --gold: #b7791f;
  --teal: #2c7a7b;

  /* ── Semantic ── */
  --positive: #276749;
  --positive-bg: #f0fff4;
  --negative: #c53030;
  --negative-bg: #fff5f5;
  --amber: #b7791f;
  --amber-bg: #fffff0;
  --info-bg: #ebf4ff;
  --info-border: #bee3f8;

  /* ── CFS Dimension Colors ── */
  --cfs-alpha: #1a365d;
  --cfs-return: #2c7a7b;
  --cfs-efficiency: #276749;
  --cfs-momentum: #b7791f;

  /* ── Typography ── */
  --font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SF Mono', SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;

  /* ── Spacing (8px base) ── */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;
  --space-3xl: 64px;
}

/* ── Reset & Base ── */
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.65;
  color: var(--text);
  background: var(--white);
}

.page {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px;
}

/* ── Cover Page ── */
.cover {
  min-height: 100vh;
  background: var(--navy);  /* FLAT. No gradient. No pattern. */
  color: var(--white);
  display: flex;
  flex-direction: column;
  padding: 0;
  page-break-after: always;
}

.cover-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 36px 48px 24px;
  border-bottom: 1px solid rgba(255,255,255,0.12);
}

.cover-brand {
  font-size: 13px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.6);
}

.cover-brand strong {
  color: rgba(255,255,255,0.95);
  display: block;
  font-size: 18px;
  margin-bottom: 2px;
  letter-spacing: 0.04em;
}

.cover-contact {
  text-align: right;
  font-size: 12px;
  color: rgba(255,255,255,0.55);
  line-height: 1.7;
}

.cover-contact strong {
  color: rgba(255,255,255,0.85);
  font-size: 13px;
}

.cover-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 60px 48px;
}

.cover-eyebrow {
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.4);
  margin-bottom: 16px;
}

.cover-divider {
  width: 60px;
  height: 3px;
  background: var(--blue);
  margin-bottom: 32px;
  border-radius: 0;
}

.cover-title {
  font-size: 42px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--white);
  margin-bottom: 12px;
}

.cover-subtitle {
  font-size: 16px;
  color: rgba(255,255,255,0.6);
  margin-bottom: 48px;
}

.cover-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, auto);
  gap: 8px 48px;
  width: fit-content;
}

.cover-meta-label {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.35);
  margin-bottom: 2px;
}

.cover-meta-value {
  font-size: 15px;
  color: var(--white);
  font-weight: 600;
}

.cover-footer {
  padding: 20px 48px;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: rgba(255,255,255,0.4);
  letter-spacing: 0.04em;
}

/* ── Section Headers ── */
.section {
  margin-bottom: var(--space-2xl);
  padding-top: var(--space-xl);
  page-break-inside: avoid;
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  margin-bottom: var(--space-sm);
}

.section-num {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--navy);
  color: var(--white);
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--navy);
  letter-spacing: 0;
}

.section-rule {
  height: 1px;
  background: var(--border);
  margin-bottom: var(--space-lg);
}

/* ── Executive Summary ── */
.exec-summary {
  background: var(--info-bg);
  border-left: 4px solid var(--blue);
  padding: 20px 24px;
  border-radius: 0 4px 4px 0;
}

.exec-summary ul { list-style: none; padding: 0; }

.exec-summary li {
  padding: 6px 0 6px 20px;
  position: relative;
}

.exec-summary li::before {
  content: "\25B8";
  position: absolute;
  left: 0;
  color: var(--blue);
  font-weight: bold;
}

/* ── Tables ── */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

th {
  background: var(--navy);
  color: var(--white);
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.02em;
}

td {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

tr:nth-child(even) td { background: var(--bg-subtle); }

/* ── Fund Cards ── */
.fund-card {
  border: 1px solid var(--border);
  border-radius: 4px;
  margin: var(--space-lg) 0;
  overflow: hidden;
  page-break-inside: avoid;
}

.fund-card-header {
  padding: 14px 20px;
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.fund-card-header h3 { color: var(--white); margin: 0; font-size: 15px; font-weight: 700; }
.fund-card-header .alloc { font-size: 24px; font-weight: 700; }

.fund-card-header.equity       { background: var(--equity); }
.fund-card-header.fixed-income { background: var(--fixed-income); }
.fund-card-header.mixed-asset  { background: var(--mixed-asset); }
.fund-card-header.money-market { background: var(--money-market); }
.fund-card-header.gold         { background: var(--gold); }
.fund-card-header.alpha-outlier { background: var(--teal); }

.fund-meta {
  display: flex;
  gap: 16px;
  padding: 10px 20px;
  background: var(--bg-subtle);
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
}

.fund-meta span { white-space: nowrap; }

.fund-card-body { padding: 16px 20px; }

.fund-card-body h4 {
  font-size: 13px;
  color: var(--navy);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 14px 0 6px;
}

.fund-card-body h4:first-child { margin-top: 0; }
.fund-card-body ul { padding-left: 18px; margin: 4px 0; }
.fund-card-body li { margin: 3px 0; font-size: 13px; }

/* ── Performance Table (inside fund cards) ── */
.perf-table { margin: 8px 0; font-size: 12px; }

.perf-table th {
  background: var(--navy);
  color: var(--white);
  padding: 6px 10px;
  font-size: 11px;
  text-align: right;
}

.perf-table th:first-child { text-align: left; }

.perf-table td {
  padding: 5px 10px;
  text-align: right;
  font-family: var(--font-mono);
  font-size: 12px;
}

.perf-table td:first-child {
  text-align: left;
  font-family: var(--font-body);
  font-weight: 600;
  color: var(--navy);
}

.alpha-pos { color: var(--positive); font-weight: 700; background: var(--positive-bg); }
.alpha-neg { color: var(--negative); font-weight: 700; background: var(--negative-bg); }

/* ── Info Boxes ── */
.cost-box {
  background: var(--positive-bg);
  border: 1px solid #c6f6d5;
  border-radius: 4px;
  padding: 10px 14px;
  margin: 8px 0;
  font-size: 13px;
}

.cost-box .net-value { font-weight: 700; color: var(--positive); }

.watch-box {
  background: var(--amber-bg);
  border: 1px solid #fefcbf;
  border-radius: 4px;
  padding: 10px 14px;
  margin: 8px 0;
  font-size: 13px;
}

.macro-box {
  background: var(--info-bg);
  border: 1px solid var(--info-border);
  border-radius: 4px;
  padding: 10px 14px;
  margin: 8px 0;
  font-size: 13px;
}

/* ── Portfolio Summary Highlight ── */
.highlight-row { background: var(--navy) !important; color: var(--white) !important; font-weight: 700; }
.highlight-row td { color: var(--white) !important; border-bottom: none; }

/* ── Strategy Cards ── */
.strategy-card {
  background: var(--bg-subtle);
  border-radius: 4px;
  padding: 16px 20px;
  margin: 12px 0;
}

.strategy-card h4 { color: var(--navy); margin-bottom: 8px; }

/* ── Pie Charts ── */
.exposure-chart-wrap {
  display: flex;
  align-items: flex-start;
  gap: 40px;
  margin: 24px 0;
}

.pie-chart {
  width: 280px;
  height: 280px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 14px;
}

.legend-swatch {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 2px;
  flex-shrink: 0;
}

.legend-pct {
  font-weight: 700;
  min-width: 50px;
  text-align: right;
}

.exposure-note {
  font-size: 13px;
  color: var(--text-muted);
  font-style: italic;
  margin-top: 16px;
  line-height: 1.6;
}

/* ── Disclaimer ── */
.disclaimer {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 20px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.7;
  margin-top: 30px;
}

/* ── Sources ── */
.sources { font-size: 11px; color: var(--text-muted); margin-top: 20px; }
.sources a { color: var(--blue); text-decoration: none; }
.sources a:hover { text-decoration: underline; }

/* ── Document Footer ── */
.doc-footer {
  text-align: center;
  font-size: 11px;
  color: var(--text-muted);
  padding: 20px 0;
  border-top: 1px solid var(--border);
  margin-top: 40px;
}

/* ── New Investor Foundation ── */
.foundation-section {
  background: var(--info-bg);
  border-left: 4px solid var(--blue);
  border-radius: 0 4px 4px 0;
  padding: 24px 28px;
  margin: 24px 0;
  page-break-inside: avoid;
}

.foundation-section h2 {
  color: var(--blue);
  font-size: 20px;
  margin-bottom: 16px;
}

.foundation-section h3 {
  color: var(--navy);
  font-size: 15px;
  margin: 16px 0 6px;
}

.foundation-section p {
  font-size: 14px;
  margin: 6px 0;
}

/* ── Exposure Gap Card ── */
.fund-card.exposure-gap {
  border: 2px dashed var(--amber);
}

.fund-card.exposure-gap .fund-card-header {
  background: var(--mixed-asset);
}

.alpha-warning {
  background: var(--amber-bg);
  border: 1px solid #fefcbf;
  border-radius: 4px;
  padding: 10px 14px;
  margin: 8px 0;
  font-size: 13px;
}

/* ── Print Styles ── */
@media print {
  body { font-size: 12px; }
  .cover { min-height: auto; padding: 48px; page-break-after: always; }
  .page { padding: 20px; }
  .section { page-break-inside: avoid; }
  .fund-card { page-break-inside: avoid; }
  .section-title { page-break-after: avoid; }
  .pie-chart, .legend-swatch {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  th, .fund-card-header, .section-num, .highlight-row, .highlight-row td {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
}
```

---

## Cover Page — HTML Structure

Both proposal types use the **same cover layout**. Only the text content differs.

### Standard Proposal Cover

```html
<div class="cover">
  <div class="cover-top-bar">
    <div class="cover-brand">
      <strong>Solid</strong>
      Public Mutual Berhad
    </div>
    <div class="cover-contact">
      <strong>Shoo Kyuk Wei (Solid)</strong><br>
      Licensed Unit Trust Consultant &amp; Licensed PRS Consultant<br>
      +601173381713 &middot; me@engineerdad.my<br>
      FIMM No: F01091705
    </div>
  </div>
  <div class="cover-body">
    <div class="cover-eyebrow">INVESTMENT PROPOSAL</div>
    <div class="cover-divider"></div>
    <div class="cover-title">Fund Portfolio<br>Proposal</div>
    <div class="cover-subtitle">[Profile] Profile &mdash; [Month Year]</div>
    <div class="cover-meta-grid">
      <div>
        <div class="cover-meta-label">Risk Profile</div>
        <div class="cover-meta-value">[Profile]</div>
      </div>
      <div>
        <div class="cover-meta-label">Funds Screened</div>
        <div class="cover-meta-value">[N] screened &rarr; [N] qualified &rarr; [N] selected</div>
      </div>
      <div>
        <div class="cover-meta-label">Data Source</div>
        <div class="cover-meta-value">FundMaster [Mon YYYY]</div>
      </div>
    </div>
  </div>
  <div class="cover-footer">
    <span>FIMM F01091705</span>
    <span>Confidential</span>
    <span>[Month Year]</span>
  </div>
</div>
```

### e-Series Shortlist Cover

Same structure — only these text values change:

- `cover-eyebrow`: `E-SERIES FUND SHORTLIST`
- `cover-title`: `Fund Shortlist`
- `cover-subtitle`: `For [Client Name] &mdash; Allocation Not Finalised`
- `cover-meta-grid`: Replace "Funds Screened" with `Candidates: 3`

---

## Consultant Branding

- Name: Shoo Kyuk Wei (Solid)
- Phone: +601173381713
- Email: me@engineerdad.my
- FIMM No: F01091705
- Title: Licensed Unit Trust Consultant & Licensed PRS Consultant
- Representative from: Public Mutual Berhad

Display in cover page top bar and document footer.

---

## Component Specifications

### CFS Mini-Bar (Fund Card Component)

After the performance table, include a CFS mini-bar for each fund card.
Use the CSS classes from the stylesheet above — all styling is handled by the design system.
The mini-bar uses inline styles for the dynamic progress bar widths only:

```html
<div style="background:var(--bg-subtle); border:1px solid var(--border); border-radius:4px; padding:14px 16px; margin:12px 0;">
  <div style="font-weight:700; font-size:13px; color:var(--navy); margin-bottom:10px;">
    COMPOSITE FUND SCORE: <span style="font-size:16px;">[XX.X]</span> / 100
  </div>
  <!-- Repeat for each dimension -->
  <div style="margin-bottom:6px;">
    <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-mid); margin-bottom:2px;">
      <span>Alpha (Manager Skill)</span>
      <span>[XX] / 100 &nbsp;&middot;&nbsp; [X%] weight</span>
    </div>
    <div style="background:var(--border); border-radius:2px; height:8px;">
      <div style="background:var(--cfs-alpha); width:[XX]%; height:8px; border-radius:2px;"></div>
    </div>
  </div>
  <div style="margin-bottom:6px;">
    <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-mid); margin-bottom:2px;">
      <span>Return Fit (vs [X%] target)</span>
      <span>[XX] / 100 &nbsp;&middot;&nbsp; [X%] weight</span>
    </div>
    <div style="background:var(--border); border-radius:2px; height:8px;">
      <div style="background:var(--cfs-return); width:[XX]%; height:8px; border-radius:2px;"></div>
    </div>
  </div>
  <div style="margin-bottom:6px;">
    <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-mid); margin-bottom:2px;">
      <span>Efficiency (Risk-Adjusted)</span>
      <span>[XX] / 100 &nbsp;&middot;&nbsp; [X%] weight</span>
    </div>
    <div style="background:var(--border); border-radius:2px; height:8px;">
      <div style="background:var(--cfs-efficiency); width:[XX]%; height:8px; border-radius:2px;"></div>
    </div>
  </div>
  <div>
    <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-mid); margin-bottom:2px;">
      <span>Momentum (ATH Proximity)</span>
      <span>[XX] / 100 &nbsp;&middot;&nbsp; [X%] weight</span>
    </div>
    <div style="background:var(--border); border-radius:2px; height:8px;">
      <div style="background:var(--cfs-momentum); width:[XX]%; height:8px; border-radius:2px;"></div>
    </div>
  </div>
</div>
```

**Dimension colors (reference):**
- Alpha: `var(--cfs-alpha)` — Navy `#1a365d`
- Return Fit: `var(--cfs-return)` — Teal `#2c7a7b`
- Efficiency: `var(--cfs-efficiency)` — Green `#276749`
- Momentum: `var(--cfs-momentum)` — Amber `#b7791f`

**For new investors** (Layer 1 jargon rule): on the fund's first CFS mini-bar in the document,
add parenthetical definitions after each label — e.g., "Alpha (Manager Skill — how much this
fund beat its benchmark)". Subsequent fund cards use the labels alone.

### Portfolio Summary Table

Include a CFS column between Alloc% and 3Y Alpha. Show weighted portfolio CFS in the footer row:

```html
<table>
  <thead>
    <tr>
      <th>Fund</th><th>Type</th><th>Alloc %</th><th>CFS</th><th>3Y Alpha</th><th>Risk Level</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>[Abbr]</td><td>Equity</td><td>XX%</td><td>XX.X</td><td>+X.XX%</td><td>[1-5]</td></tr>
    <!-- ... -->
    <tr class="highlight-row">
      <td>PORTFOLIO</td><td></td><td>100%</td><td>[Wtd CFS]</td><td>[Wtd Alpha]</td><td>[Wtd RL]</td>
    </tr>
  </tbody>
</table>
<p style="font-size:12px; color:var(--text-mid);">
  Weighted Portfolio CFS: <strong>[XX.X] / 100</strong> &nbsp;|&nbsp;
  Weighted Portfolio Alpha (3Y): <strong>[+X.XX%]</strong> &nbsp;|&nbsp;
  Weighted Portfolio VF: <strong>[X.XX] ([Volatility Class])</strong>
</p>
```

### Exposure Gap Fund Cards

When a portfolio includes an Exposure Gap pick (Step 4b), use the `.fund-card.exposure-gap` class:

```html
<div class="fund-card exposure-gap">
  <div class="fund-card-header mixed-asset">
    <h3>⚠ EXPOSURE GAP PICK — [Fund Name]</h3>
    <span class="alloc">[XX]%</span>
  </div>
  <div class="fund-card-body">
    <div class="alpha-warning">
      [Explain alpha weakness and why the fund is included for exposure only]
    </div>
    <!-- rest of card content -->
  </div>
</div>
```

### Portfolio Exposure Breakdown (Two Charts)

See **SKILL.md Steps 7b–7c** for calculation logic, data sources, color maps, and grouping rules
for both the Asset Class and Geographic pie charts.

**Implementation notes (HTML/CSS only):**
- Layout: flexbox row (side by side), using `.exposure-chart-wrap`
- Each chart: 280×280px, CSS `conic-gradient` — no JavaScript
- Legend: `.legend-swatch` (16×16px, 2px radius) + label + `.legend-pct`
- Print CSS handles `print-color-adjust: exact`

### Sources Section

Include all web search sources used for macro context as clickable links at the end of the document.

### New Investor Foundation Section

**When to include:** Only when the consultant declares this is a new investor. Omit for experienced investors.

**Placement:** Immediately after the Cover Page, before Executive Summary.

**Contents (in order):**

1. **What is a Unit Trust?**
   > "A unit trust is a pool of money from many investors, professionally managed and invested across a basket of assets — stocks, bonds, cash — on your behalf. You own units; the fund manager does the work."

2. **How Does Your Investment Grow?**
   > "Your investment grows in two ways: the price per unit (NAV) rises as the underlying assets appreciate, and some funds distribute income periodically. Reinvesting distributions compounds your growth tax-free in Malaysia."

3. **Your Cooling-Off Right**
   > "As a first-time investor with Public Mutual, you have a 6 business day cooling-off period from the date of your first purchase. If you change your mind, you may redeem your units at the original NAV paid — no loss on the principal."

4. **Realistic Expectations**
   > "Unit trusts are medium-to-long term investments (3–5+ years). Short-term price fluctuations are normal — the data in this proposal reflects historical performance over full market cycles, which is what matters."

**Styling:** Use the `.foundation-section` class from the stylesheet.

---

## What NOT to Include

The following are **explicitly banned** from all generated proposals:

- **No Google Fonts** — no `@import url(...)`, no `<link>` to fonts.googleapis.com
- **No serif fonts** — no Georgia, Times New Roman, Garamond, Baskerville, Libre Baskerville, EB Garamond, Cormorant
- **No gradient backgrounds** — no `linear-gradient`, `radial-gradient` on cover or anywhere (only `conic-gradient` for pie charts)
- **No diagonal stripe patterns** — no `repeating-linear-gradient` for decoration
- **No decorative circles, blobs, or radial shapes**
- **No box-shadows on cards** — flat design only
- **No creative variations** — follow the stylesheet exactly as provided above
- **No custom color palettes** — use only the CSS variables defined in `:root`
