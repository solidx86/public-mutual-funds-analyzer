# Proposal Document Template

## Output Format
Generate an HTML file saved as:
```
FundProposal_[Profile]_[MonYYYY].html
```
Example: `FundProposal_Moderate_Apr2026.html`

Save in the Funds project root folder.

## HTML Structure

The HTML document must be a single self-contained file (all CSS inline, no external dependencies).
Use `@media print` CSS for clean PDF output when printing from browser.

### Required Sections (in order)

1. **Cover Page** — title, client profile, date, consultant branding
2. **Executive Summary** — 3-4 bullet points: profile, portfolio composition, weighted alpha, key thesis
3. **Global & Local Macro Context** — on-going events table + medium-to-long horizon themes
4. **Client Risk Profile** — profile description, constraints (max RL, max equity %, min bond %)
5. **Fund Recommendations** — one card per fund with:
   - Fund header (name, abbr, type, RL, VF, AUM, allocation %)
   - Alpha story (beat rate, alpha across periods, alpha score, AE)
   - Macro alignment (how this fund connects to macro themes for medium-long horizon)
   - What to watch (flags/risks)
   - Cost & alpha justification (fees vs alpha = net value-add)
6. **Portfolio Summary** — table with all funds, allocation, alpha, RL, macro thesis
7. **Portfolio Exposure Breakdown** — CSS conic-gradient pie chart of actual underlying asset exposure (see below)
8. **Investment Strategy** — DCA/RSP, distribution policy, rebalancing triggers, tactical playbook
9. **Fee Disclosure** — transparent breakdown of sales charges and annual fees per fund
10. **Disclaimer & Disclosures** — regulatory disclaimer, FIMM compliance note

### Consultant Branding

Load from memory (`user_consultant_details.md`):
- Name: Shoo Kyuk Wei (Solid)
- Phone: +601173381713
- Email: me@engineerdad.my
- FIMM No: F01091705
- Title: Licensed Unit Trust Consultant & Licensed PRS Consultant
- Representative from: Public Mutual Berhad

Display in cover page header and document footer.

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

### Portfolio Exposure Pie Chart

Place between Portfolio Summary and Investment Strategy sections.

**Layout:** Flexbox row — pie chart (280×280px) on the left, legend on the right.

**Pie chart:** CSS-only using `conic-gradient`. Compute cumulative percentages from the weighted
asset exposure across all recommended funds (each fund's asset allocation × its portfolio weight).

```html
<div style="display:flex; align-items:center; gap:40px; margin:24px 0;">
  <div style="width:280px; height:280px; border-radius:50%;
    background:conic-gradient(
      #2b6cb0 0% VAR_DOM_EQ%,
      #2c7a7b VAR_DOM_EQ% VAR_CUM_FOR%,
      #276749 VAR_CUM_FOR% VAR_CUM_FI%,
      #718096 VAR_CUM_FI% VAR_CUM_MM%,
      #b7791f VAR_CUM_MM% 100%
    ); box-shadow:0 2px 8px rgba(0,0,0,0.10);">
  </div>
  <div>
    <!-- Legend: colored square + label + percentage for each slice -->
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
      <span style="display:inline-block;width:16px;height:16px;background:#2b6cb0;border-radius:3px;"></span>
      <span>Equity (Domestic) — XX.X%</span>
    </div>
    <!-- repeat for each asset class -->
  </div>
</div>
```

**Asset class colors:**
| Slice | Color | Hex |
|-------|-------|-----|
| Equity (Domestic) | Blue | #2b6cb0 |
| Equity (Foreign) | Teal | #2c7a7b |
| Fixed Income / Sukuk | Green | #276749 |
| Money Market & Deposits | Grey | #718096 |
| Other | Amber | #b7791f |

**Explanatory note** below the chart:
> "This chart shows the actual underlying asset exposure of your portfolio — looking through each
> fund to what it actually holds, ensuring your real-world risk matches your declared risk profile."

**Print CSS:** Ensure the pie chart renders in print (`-webkit-print-color-adjust: exact; print-color-adjust: exact;`).

### Sources Section
Include all web search sources used for macro context as clickable links at the end of the document.
