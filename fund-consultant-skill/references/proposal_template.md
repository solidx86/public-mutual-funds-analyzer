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
Use `@media print` CSS for clean PDF output when printing from browser.

### Required Sections (in order)

See **SKILL.md Step 7** for the authoritative section list, ordering, and content requirements.
The sections are: Cover Page → New Investor Foundation (if applicable) → Executive Summary →
Macro Context → Risk Profile → Fund Recommendations → Portfolio Summary → Portfolio Exposure
Breakdown → Investment Strategy → Fee Disclosure → Disclaimer.

Below are the **HTML/CSS implementation details** for key sections.

### Consultant Branding

Load from memory (`user_consultant_details.md`):
- Name: Shoo Kyuk Wei (Solid)
- Phone: +601173381713
- Email: me@engineerdad.my
- FIMM No: F01091705
- Title: Licensed Unit Trust Consultant & Licensed PRS Consultant
- Representative from: Public Mutual Berhad

Display in cover page header and document footer.

### CFS Mini-Bar (Fund Card Component)

After the performance table, before the score breakdown narrative, include a CFS mini-bar for each
fund card. Use CSS-only horizontal bars — no JavaScript:

```html
<div style="background:#f7fafc; border:1px solid #e2e8f0; border-radius:6px; padding:14px 16px; margin:12px 0;">
  <div style="font-weight:700; font-size:13px; color:#1a365d; margin-bottom:10px;">
    COMPOSITE FUND SCORE: <span style="font-size:16px;">[XX.X]</span> / 100
  </div>
  <!-- Repeat for each dimension -->
  <div style="margin-bottom:6px;">
    <div style="display:flex; justify-content:space-between; font-size:12px; color:#4a5568; margin-bottom:2px;">
      <span>Alpha (Manager Skill)</span>
      <span>[XX] / 100 &nbsp;·&nbsp; [X%] weight</span>
    </div>
    <div style="background:#e2e8f0; border-radius:3px; height:8px;">
      <div style="background:#1a365d; width:[XX]%; height:8px; border-radius:3px;"></div>
    </div>
  </div>
  <div style="margin-bottom:6px;">
    <div style="display:flex; justify-content:space-between; font-size:12px; color:#4a5568; margin-bottom:2px;">
      <span>Return Fit (vs [X%] target)</span>
      <span>[XX] / 100 &nbsp;·&nbsp; [X%] weight</span>
    </div>
    <div style="background:#e2e8f0; border-radius:3px; height:8px;">
      <div style="background:#2c7a7b; width:[XX]%; height:8px; border-radius:3px;"></div>
    </div>
  </div>
  <div style="margin-bottom:6px;">
    <div style="display:flex; justify-content:space-between; font-size:12px; color:#4a5568; margin-bottom:2px;">
      <span>Efficiency (Risk-Adjusted)</span>
      <span>[XX] / 100 &nbsp;·&nbsp; [X%] weight</span>
    </div>
    <div style="background:#e2e8f0; border-radius:3px; height:8px;">
      <div style="background:#276749; width:[XX]%; height:8px; border-radius:3px;"></div>
    </div>
  </div>
  <div>
    <div style="display:flex; justify-content:space-between; font-size:12px; color:#4a5568; margin-bottom:2px;">
      <span>Momentum (ATH Proximity)</span>
      <span>[XX] / 100 &nbsp;·&nbsp; [X%] weight</span>
    </div>
    <div style="background:#e2e8f0; border-radius:3px; height:8px;">
      <div style="background:#b7791f; width:[XX]%; height:8px; border-radius:3px;"></div>
    </div>
  </div>
</div>
```

**Dimension colors:**
- Alpha: Navy `#1a365d`
- Return Fit: Teal `#2c7a7b`
- Efficiency: Green `#276749`
- Momentum: Amber `#b7791f`

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
    <tr style="font-weight:700; background:#ebf8ff;">
      <td>PORTFOLIO</td><td></td><td>100%</td><td>[Wtd CFS]</td><td>[Wtd Alpha]</td><td>[Wtd RL]</td>
    </tr>
  </tbody>
</table>
<p style="font-size:12px; color:#4a5568;">
  Weighted Portfolio CFS: <strong>[XX.X] / 100</strong> &nbsp;|&nbsp;
  Weighted Portfolio Alpha (3Y): <strong>[+X.XX%]</strong> &nbsp;|&nbsp;
  Weighted Portfolio VF: <strong>[X.XX] ([Volatility Class])</strong>
</p>
```

### Exposure Gap Fund Cards

When a portfolio includes an Exposure Gap pick (Step 4b), style its fund card differently:
- **Border:** 2px dashed amber (#b7791f) instead of solid
- **Header banner:** Amber background (#975a16) with "⚠ EXPOSURE GAP PICK" label
- **Alpha Warning box:** Distinct amber/yellow background (#fffff0) with border (#fefcbf),
  clearly stating the fund's alpha weakness and why it's included for exposure only

### Styling Guidelines

- **Color palette:** Professional navy (#1a365d) headers, white background, accent blue (#2b6cb0) for tables
- **Fund cards:** Bordered cards with light background, colored left border by fund type:
  - Equity: blue (#2b6cb0)
  - Fixed Income: green (#276749)
  - Mixed Asset: amber (#975a16)
  - Money Market: grey (#4a5568)
- **Alpha indicators:** Green for positive, red for negative
- **Tables:** Zebra-striped rows, clear headers
- **Print CSS:** Page breaks before major sections, hide non-essential decorative elements
- **Typography:** System fonts (Arial/Helvetica), clean readable sizes
- **Alpha bar charts:** CSS-only horizontal bars showing alpha magnitude per period

### Portfolio Exposure Breakdown (Two Charts)

See **SKILL.md Steps 7b–7c** for calculation logic, data sources, color maps, and grouping rules
for both the Asset Class and Geographic pie charts.

**Implementation notes (HTML/CSS only):**
- Layout: flexbox row (side by side on wide screens), stacked on print
- Each chart: 280×280px, CSS `conic-gradient` — no JavaScript
- Legend: colored square (16×16px, border-radius 3px) + label + percentage
- Print CSS: `print-color-adjust: exact; -webkit-print-color-adjust: exact;`

### Sources Section
Include all web search sources used for macro context as clickable links at the end of the document.

---

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

**Styling:**
```html
<div style="background:#ebf8ff; border-left:4px solid #2b6cb0; border-radius:4px;
  padding:20px 24px; margin:24px 0;">
  <h2 style="color:#2b6cb0; margin-top:0;">Your Investment Basics</h2>
  <!-- section content -->
</div>
```

Label it clearly as an introductory section — not part of the formal recommendation. Use plain language throughout; avoid jargon.
