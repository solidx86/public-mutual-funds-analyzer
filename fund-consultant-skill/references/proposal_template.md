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
7. **Investment Strategy** — DCA/RSP, distribution policy, rebalancing triggers, tactical playbook
8. **Fee Disclosure** — transparent breakdown of sales charges and annual fees per fund
9. **Disclaimer & Disclosures** — regulatory disclaimer, FIMM compliance note

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

### Sources Section
Include all web search sources used for macro context as clickable links at the end of the document.
