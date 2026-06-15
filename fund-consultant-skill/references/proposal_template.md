# Proposal Template (Mode A — Standard Fund Proposal)

> **This template defines the complete HTML skeleton for the standard Fund Proposal output.**
> Every generated proposal must use this skeleton **verbatim** — substitute only the content
> tokens marked `[BRACKETED]`. Do not add, remove, rename, or reorder sections. Do not modify
> CSS classes, colors, or layout primitives. The single source of truth for styling is
> `references/design_system.css` — embed it byte-for-byte in the `<style>` block.
>
> For e-Series Shortlist mode, see `references/shortlist_template.md` (different skeleton).

---

## Output File

```
output/fund_proposals/FundProposal_[Profile]_[MonYYYY]_v[SKILL_VERSION].html
```

Optional client suffix: `FundProposal_[Profile]_[MonYYYY]_[ClientLastName]_v[SKILL_VERSION].html`.
Example: `FundProposal_Moderate_May2026_Tan_v1.25.html`.

The skill-version suffix (`_v[SKILL_VERSION]`) is mandatory — it lets us identify which
generation pass produced any file in `output/fund_proposals/` at a glance, and pairs with
the visible Generator stamp on the cover. Substitute the value from the SKILL.md frontmatter
`version` field (no `v` prefix in the token — the template provides it).

The HTML must be **a single self-contained file** — all CSS inline, no external dependencies,
no Google Fonts, no `<link>` to external stylesheets, no JavaScript.

---

## Document Skeleton (mandatory order)

```
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fund Portfolio Proposal — [Profile] — [Month Year]</title>
  <style>
    /* ↓↓↓ Embed the entire contents of references/design_system.css HERE, verbatim ↓↓↓ */
  </style>
</head>
<body>

  <!-- 1. COVER PAGE -->                       (always)
  <!-- 2. FOUNDATION INTRO -->                 (only if experience_level == "New Investor")
  <div class="page">
    <!-- 3. SECTION 1 — Executive Summary -->
    <!-- 4. SECTION 2 — Global & Local Macro Context -->
    <!-- 5. SECTION 3 — Client Risk Profile -->
    <!-- 6. SECTION 4 — Fund Recommendations -->
    <!-- 7. SECTION 5 — Portfolio Summary -->
    <!-- 8. SECTION 6 — Portfolio Exposure -->
    <!-- 9. SECTION 7 — Investment Strategy -->
    <!-- 10. SECTION 8 — Fee Disclosure -->
    <!-- 11. SECTION 9 — Disclaimer, Sources & References -->
    <!-- 12. DOCUMENT FOOTER -->
  </div>

</body>
</html>
```

**Self-check before finalizing:** count the rendered `<div class="section">` elements — there
must be exactly **9**. The cover, foundation, and document footer are not `.section` blocks.

---

## 1. Cover Page

```html
<div class="cover">
  <div class="cover-top-bar">
    <div class="cover-brand">
      <strong>SOLID</strong>
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
    <div class="cover-subtitle">For [Client Name] &middot; [Profile] Profile</div>
    <div class="cover-meta-grid">
      <div>
        <div class="cover-meta-label">Risk Profile</div>
        <div class="cover-meta-value">[Profile]</div>
      </div>
      <div>
        <div class="cover-meta-label">Return Target</div>
        <div class="cover-meta-value">[E_target]% p.a.</div>
      </div>
      <div>
        <div class="cover-meta-label">Shariah Preference</div>
        <div class="cover-meta-value">[Yes / No / No preference]</div>
      </div>
      <div>
        <div class="cover-meta-label">Data Source</div>
        <div class="cover-meta-value">FundMaster [Mon YYYY]</div>
      </div>
      <div>
        <div class="cover-meta-label">Funds Selected</div>
        <div class="cover-meta-value">[N] of [M] screened</div>
      </div>
      <div>
        <div class="cover-meta-label">Proposal Date</div>
        <div class="cover-meta-value">[DD Mon YYYY]</div>
      </div>
    </div>
  </div>
  <div class="cover-footer">
    <span>FIMM F01091705</span>
    <span>fund-consultant v[SKILL_VERSION]</span>
    <span>Confidential</span>
    <span>Prepared [DD Mon YYYY]</span>
  </div>
</div>
```

**Cover content rules:**
- `cover-eyebrow` = literal string `INVESTMENT PROPOSAL` (uppercase)
- `cover-title` = literal string `Fund Portfolio<br>Proposal`
- `cover-subtitle` = `For [Client Name] &middot; [Profile] Profile` — if no client name yet,
  use `[Profile] Profile &middot; [Month Year]`
- `cover-meta-grid` = exactly **6 cells** in a 3×2 layout. Order is fixed — do not omit or
  reorder.
- `cover-footer` = exactly **4 spans** in this order: `FIMM F01091705` / `fund-consultant
  v[SKILL_VERSION]` / `Confidential` / `Prepared [DD Mon YYYY]`. The version span sits in
  slot 2 between FIMM and Confidential, in the same low-key metadata typography as the
  other three. This is the visible version stamp.
- Consultant credentials block in `cover-contact` is **invariant** — sourced from memory.

---

## 2. Foundation Intro (conditional)

Render this block **only** when `experience_level == "New Investor"`. Place it directly after the
cover, **before** the `<div class="page">` opening for sections.

```html
<div class="page">
  <div class="foundation-section">
    <h2>Before We Start — A Quick Foundation</h2>
    <p style="margin-bottom:8px; color:var(--text-mid);">
      You're new to unit trusts. Four short notes before we dive into the recommendations.
    </p>

    <h3>1. What is a Unit Trust?</h3>
    <p>A unit trust is a pool of money from many investors, professionally managed and invested
    across a basket of assets — stocks, bonds, cash — on your behalf. You own units; the fund
    manager does the work.</p>

    <h3>2. How Returns Work</h3>
    <p>Your investment grows in two ways: the price per unit (NAV) rises as the underlying assets
    appreciate, and some funds distribute income periodically. Reinvesting distributions compounds
    your growth.</p>

    <h3>3. Your Cooling-Off Right</h3>
    <p>As a first-time investor with Public Mutual, you have a <strong>6 business day cooling-off
    period</strong> from the date of your first purchase. If you change your mind, you may redeem
    your units at the original NAV paid — no loss on the principal.</p>

    <h3>4. Why a Starter Portfolio</h3>
    <p>We're starting you with a focused 4-fund portfolio rather than a full 6-fund allocation.
    This keeps the moving parts low, and we can layer in additional funds at your next portfolio
    review once you're comfortable with the basics.</p>
  </div>
</div>
```

Omit the entire block (including its `.page` wrapper) for experienced investors. Sections 1–9
then sit in their own `.page` wrapper.

---

## 3. Section 1 — Executive Summary

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">1</div>
    <div class="section-title">Executive Summary</div>
  </div>
  <div class="section-rule"></div>
  <div class="exec-summary">
    <ul>
      <li><strong>Profile:</strong> [Profile] — [one-sentence positioning].</li>
      <li><strong>Composition:</strong> [N]-fund portfolio &middot; [Asset class mix one-liner, e.g. "55% equity / 30% mixed asset / 10% gold / 5% cash"].</li>
      <li><strong>Weighted CFS:</strong> [XX.X] / 100 &middot; <strong>3Y Alpha:</strong> [+X.XX]% p.a. &middot; <strong>Portfolio VF:</strong> [X.X] ([Volatility class]).</li>
      <li><strong>Thesis:</strong> [one-sentence why this portfolio fits the macro environment + the client's profile].</li>
    </ul>
  </div>
</div>
```

Exactly **4 bullets** in this order — Profile, Composition, Weighted CFS / Alpha / VF, Thesis.

---

## 4. Section 2 — Global & Local Macro Context

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">2</div>
    <div class="section-title">Global &amp; Local Macro Context</div>
  </div>
  <div class="section-rule"></div>

  <p style="margin-bottom:12px; color:var(--text-mid);">
    Recent events shaping our positioning ([Month] [Year]):
  </p>

  <div class="table-wrap">
    <table class="macro-table">
      <thead>
        <tr><th>Event</th><th>Date</th><th>Implication for the Portfolio</th></tr>
      </thead>
      <tbody>
        <tr><td>[Event 1 — short title]</td><td>[DD Mon YYYY]</td><td>[Implication — 1 sentence]</td></tr>
        <tr><td>[Event 2]</td><td>[DD Mon YYYY]</td><td>[Implication]</td></tr>
        <tr><td>[Event 3]</td><td>[DD Mon YYYY]</td><td>[Implication]</td></tr>
        <!-- 3–5 rows total -->
      </tbody>
    </table>
  </div>

  <h4 style="font-size:13px; color:var(--navy); text-transform:uppercase; letter-spacing:0.06em; margin:20px 0 8px;">Medium-Long Horizon Themes</h4>
  <p>[1–2 short paragraphs on structural themes — e.g., AI capex cycle, MY rate path, gold reserve diversification, BRICS de-dollarization. Each theme should connect to a named fund in the portfolio.]</p>
</div>
```

- The `Event | Date | Implication` table is **mandatory** — do not substitute prose-only.
- 3–5 event rows. Use real, dated events from the web search. Cite their source URLs in Section 9.

---

## 5. Section 3 — Client Risk Profile

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">3</div>
    <div class="section-title">Client Risk Profile</div>
  </div>
  <div class="section-rule"></div>

  <table>
    <tbody>
      <tr><td style="width:30%;"><strong>Profile</strong></td><td>[Profile] — [one-line description from Step 0]</td></tr>
      <tr><td><strong>Return Target</strong></td><td>[E_target]% p.a. ([on profile midpoint / above midpoint by X% / below midpoint by X%])</td></tr>
      <tr><td><strong>Shariah Preference</strong></td><td>[Yes / No / No preference]</td></tr>
      <tr><td><strong>Experience Level</strong></td><td>[New Investor / Experienced]</td></tr>
      <tr><td><strong>Risk Level Ceiling</strong></td><td>RL [≤ 2 / ≤ 3 / ≤ 4 / ≤ 5] (per profile rule)</td></tr>
      <tr><td><strong>Target Portfolio VF</strong></td><td>[range from Step 4]</td></tr>
    </tbody>
  </table>
</div>
```

---

## 6. Section 4 — Fund Recommendations

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">4</div>
    <div class="section-title">Fund Recommendations</div>
  </div>
  <div class="section-rule"></div>

  <!-- One <div class="fund-card"> block per recommended fund (3–6 cards depending on profile + experience). -->
  <!-- Cards rendered in order: highest-allocation first, money-market last. -->

</div>
```

### Fund Card — locked structure

```html
<div class="fund-card">
  <div class="fund-card-header [equity|fixed-income|mixed-asset|money-market|gold|alpha-outlier]">
    <h3>[Fund Name] &middot; [Abbr]</h3>
    <span class="alloc">[XX]%</span>
  </div>

  <div class="fund-meta">
    <span><strong>Type:</strong> [Equity/Mixed Asset/FI/MM/Gold]</span>
    <span><strong>RL:</strong> [1–5]</span>
    <span><strong>VF:</strong> [X.X]</span>
    <span><strong>Shariah:</strong> [Yes/No]</span>
    <span><strong>AUM:</strong> RM [X,XXX]M</span>
    <span><strong>Lipper:</strong> [Class]</span>
  </div>

  <div class="fund-card-body">

    <!-- (a) ALPHA WARNING — only if Status == "Disqualified" -->
    <!-- <div class="alpha-warning">[explanation per Step 4 disclosure rule]</div> -->

    <!-- (b) CFS mini-bar -->
    <div class="cfs-bar">
      <div class="cfs-title">COMPOSITE FUND SCORE: <span class="cfs-score">[XX.X]</span> / 100</div>
      <div class="cfs-row">
        <div class="cfs-row-label"><span>Alpha (Manager Skill)</span><span>[XX] / 100 &middot; [W%] weight</span></div>
        <div class="cfs-track"><div class="cfs-fill alpha" style="width:[XX]%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label"><span>Return Fit (vs [E]% target)</span><span>[XX] / 100 &middot; [W%] weight</span></div>
        <div class="cfs-track"><div class="cfs-fill return-fit" style="width:[XX]%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label"><span>Efficiency (Risk-Adjusted)</span><span>[XX] / 100 &middot; [W%] weight</span></div>
        <div class="cfs-track"><div class="cfs-fill efficiency" style="width:[XX]%;"></div></div>
      </div>
      <div class="cfs-row">
        <div class="cfs-row-label"><span>Momentum (ATH Proximity)</span><span>[XX] / 100 &middot; [W%] weight</span></div>
        <div class="cfs-track"><div class="cfs-fill momentum" style="width:[XX]%;"></div></div>
      </div>
    </div>

    <!-- (c) Performance table -->
    <h4>Performance vs Benchmark</h4>
    <div class="table-wrap">
      <table class="perf-table">
        <thead><tr><th>Period</th><th>Fund %</th><th>Bench %</th><th>Alpha %</th></tr></thead>
        <tbody>
          <tr><td>YTD</td><td>[X.XX]</td><td>[X.XX]</td><td class="[alpha-pos|alpha-neg]">[+X.XX]</td></tr>
          <tr><td>1Y</td><td>[X.XX]</td><td>[X.XX]</td><td class="[alpha-pos|alpha-neg]">[+X.XX]</td></tr>
          <tr><td>3Y</td><td>[X.XX]</td><td>[X.XX]</td><td class="[alpha-pos|alpha-neg]">[+X.XX]</td></tr>
          <tr><td>5Y</td><td>[X.XX]</td><td>[X.XX]</td><td class="[alpha-pos|alpha-neg]">[+X.XX]</td></tr>
        </tbody>
      </table>
    </div>

    <!-- (d) Cost & Alpha mini-card — verbatim PHS source values, see Step 6 PHS Lookup Rule -->
    <h4>Cost &amp; Alpha</h4>
    <div class="cost-alpha-mini">
      <div class="cell"><span class="label">Sales Charge</span><span class="value">[X.X]%</span></div>
      <div class="cell"><span class="label">Mgmt Fee p.a.</span><span class="value">[X.XX]%</span></div>
      <div class="cell"><span class="label">Trustee Fee p.a.</span><span class="value">[X.XX]%</span></div>
      <div class="cell"><span class="label">Annual Cost</span><span class="value">[X.XX]%</span></div>
      <div class="cell"><span class="label">3Y Alpha</span><span class="value [pos|neg]">[+X.XX]%</span></div>
      <div class="cell"><span class="label">Net Value-Add</span><span class="value [pos|neg]">[+X.XX]%</span></div>
      <div class="source">Fees sourced verbatim from <code>[Abbr]_PHS.pdf</code> &middot; PHS dated [Mon YYYY]</div>
    </div>

    <!-- (e) Why we chose it -->
    <h4>Why We Chose It</h4>
    <p>[2–4 sentences. Lead with the strongest selling point — alpha, return capability, macro fit, or diversification role. Tie to the client's profile.]</p>

    <!-- (f) What to watch -->
    <h4>What to Watch</h4>
    <ul>
      <li>[Watch item 1 — e.g., concentration risk, RL escalation, benchmark-hugger flag, drawdown depth, distribution policy]</li>
      <li>[Watch item 2]</li>
      <li>[Watch item 3 if relevant]</li>
    </ul>

  </div>
</div>
```

**Fund card rules:**
- Block order is fixed: header → fund-meta → ALPHA WARNING (conditional) → CFS bar →
  Performance table → Cost & Alpha mini-card → Why We Chose It → What to Watch.
- For new investors, on the **first** CFS mini-bar in the document, append parenthetical
  definitions to each label (e.g., `Alpha (Manager Skill — how much this fund beat its benchmark)`).
  Subsequent cards use the labels alone.
- For **Exposure Gap** funds, wrap with `<div class="fund-card exposure-gap">` and force the
  header to `mixed-asset`. Title prefix: `⚠ EXPOSURE GAP PICK — `.

---

## 7. Section 5 — Portfolio Summary

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">5</div>
    <div class="section-title">Portfolio Summary</div>
  </div>
  <div class="section-rule"></div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Fund</th><th>Type</th><th>Alloc %</th><th>CFS</th><th>3Y Alpha</th><th>Risk Level</th></tr>
      </thead>
      <tbody>
        <tr><td>[Abbr]</td><td>[Type]</td><td>[XX]%</td><td>[XX.X]</td><td class="[alpha-pos|alpha-neg]">[+X.XX]%</td><td>[1-5]</td></tr>
        <!-- one row per fund -->
        <tr class="highlight-row">
          <td>PORTFOLIO</td><td></td><td>100%</td><td>[Wtd CFS]</td><td>[Wtd Alpha]</td><td>[Wtd RL]</td>
        </tr>
      </tbody>
    </table>
  </div>

  <p style="font-size:12px; color:var(--text-mid); margin-top:8px;">
    Weighted Portfolio CFS: <strong>[XX.X] / 100</strong> &middot;
    Weighted Portfolio Alpha (3Y): <strong>[+X.XX]%</strong> &middot;
    Weighted Portfolio VF: <strong>[X.X] ([Volatility Class])</strong>
  </p>
</div>
```

Exactly 6 columns. Highlight row is mandatory.

---

## 8. Section 6 — Portfolio Exposure

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">6</div>
    <div class="section-title">Portfolio Exposure</div>
  </div>
  <div class="section-rule"></div>

  <p style="color:var(--text-mid); margin-bottom:12px;">
    Look-through to what the portfolio actually holds — not the fund types, but the underlying
    asset classes and countries.
  </p>

  <div class="exposure-chart-wrap">

    <div class="exposure-chart-block">
      <div class="exposure-chart-title">Asset Class</div>
      <div class="pie-chart" style="background: conic-gradient(
        var(--equity)       0% [a]%,
        var(--teal)         [a]% [a+b]%,
        var(--fixed-income) [a+b]% [a+b+c]%,
        var(--money-market) [a+b+c]% [a+b+c+d]%,
        var(--gold)         [a+b+c+d]% 100%
      );"></div>
      <div class="legend">
        <div class="legend-item"><span class="legend-swatch" style="background:var(--equity);"></span>     <span class="legend-label">Equity (Domestic)</span> <span class="legend-pct">[X.X]%</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--teal);"></span>       <span class="legend-label">Equity (Foreign)</span>  <span class="legend-pct">[X.X]%</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--fixed-income);"></span><span class="legend-label">Fixed Income / Sukuk</span><span class="legend-pct">[X.X]%</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--money-market);"></span><span class="legend-label">Money Market &amp; Cash</span><span class="legend-pct">[X.X]%</span></div>
        <div class="legend-item"><span class="legend-swatch" style="background:var(--gold);"></span>       <span class="legend-label">Gold / Other</span> <span class="legend-pct">[X.X]%</span></div>
      </div>
    </div>

    <div class="exposure-chart-block">
      <div class="exposure-chart-title">Geographic</div>
      <div class="pie-chart" style="background: conic-gradient( /* slices per Step 7c color map */ );"></div>
      <div class="legend">
        <!-- legend items: slices ≥ 2% only, plus a single "Other" slice for combined < 2% slices -->
      </div>
    </div>

  </div>

  <p class="exposure-note">
    Asset-class slices are the weighted average of each fund's underlying asset allocation.
    Geographic slices treat Malaysian-issued bonds as Malaysia exposure. Slices below 2% are
    merged into "Other" for readability.
  </p>
</div>
```

**Pie-chart rules (locked):**
- Both pies use CSS `conic-gradient` only — no JavaScript, no SVG.
- Legend percentages: **1 decimal place** (e.g., `12.4%`, not `12%` or `12.41%`).
- Slices `< 2%` of the portfolio are merged into a single "Other" slice for legend display
  (already required by SKILL.md Step 7c).
- For the Asset Class chart, the slice order is fixed: domestic equity → foreign equity →
  fixed income → money market → gold/other.

---

## 9. Section 7 — Investment Strategy

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">7</div>
    <div class="section-title">Investment Strategy</div>
  </div>
  <div class="section-rule"></div>

  <div class="strategy-card">
    <h4>1. Regular Savings Plan (RSP)</h4>
    <p>[DCA cadence + amount recommendation tied to E_target and capital]</p>
  </div>

  <div class="strategy-card">
    <h4>2. Distribution Policy</h4>
    <p>[Distributions per fund, reinvest vs payout recommendation, tax note]</p>
  </div>

  <div class="strategy-card">
    <h4>3. Rebalancing Triggers</h4>
    <p>[Time-based cadence + drift threshold + event triggers per Step 5]</p>
  </div>

  <div class="strategy-card">
    <h4>4. Tactical Dip-Capture Playbook</h4>
    <p>[Money market dry-powder rule: when index drops X% from ATH, deploy Y% from PeCDF-A into the equity sleeve]</p>
  </div>
</div>
```

Exactly 4 strategy-cards in this order.

---

## 10. Section 8 — Fee Disclosure

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">8</div>
    <div class="section-title">Fee Disclosure</div>
  </div>
  <div class="section-rule"></div>

  <p style="color:var(--text-mid); margin-bottom:8px;">
    Every fee shown is sourced verbatim from each fund's Product Highlight Sheet (PHS).
    No values are inferred or carried over from prior proposals.
  </p>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Fund</th>
          <th>Sales Charge</th>
          <th>Mgmt Fee p.a.</th>
          <th>Trustee Fee p.a.</th>
          <th>Annual Cost</th>
          <th>3Y Alpha</th>
          <th>Net Value-Add</th>
          <th>PHS Date</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>[Abbr]</strong></td>
          <td>[X.X]%</td>
          <td>[X.XX]%</td>
          <td>[X.XX]%</td>
          <td>[X.XX]%</td>
          <td class="[alpha-pos|alpha-neg]">[+X.XX]%</td>
          <td class="[alpha-pos|alpha-neg]">[+X.XX]%</td>
          <td>[Mon YYYY]</td>
        </tr>
        <!-- one row per fund -->
      </tbody>
    </table>
  </div>

  <p style="font-size:12px; color:var(--text-muted); margin-top:8px;">
    <strong>Annual Cost</strong> = Mgmt Fee + Trustee Fee. <strong>Net Value-Add</strong> = 3Y Alpha − Annual Cost.
    Sales Charge is a one-time entry load. Switching fee, redemption fee, and full disclosures are in each fund's PHS and Master Prospectus.
  </p>
</div>
```

Exactly **8 columns** in this exact order. Annual Cost and Net Value-Add are computed
client-side from the PHS values — do not invent.

---

## 11. Section 9 — Disclaimer, Sources & References

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">9</div>
    <div class="section-title">Disclaimer, Sources &amp; References</div>
  </div>
  <div class="section-rule"></div>

  <div class="disclaimer">
    <h4>AI-Generated Document</h4>
    <p>This document was generated with the assistance of an AI-driven analysis and drafting
    tool (fund-consultant skill, version [SKILL_VERSION]) developed by the consultant. All
    fund data is sourced from Public Mutual's official Monthly Fund Review (MFR) and Product
    Highlight Sheet (PHS) publications. The Composite Fund Score and fund recommendations
    reflect a combination of quantitative scoring and the consultant's professional judgment;
    the licensed consultant has reviewed and approved all recommendations before delivery.
    Clients should treat this document as a starting point for discussion — please consult
    the licensed UTC for any clarifications or to adjust the recommendations to your specific
    circumstances.</p>

    <h4>Regulatory Disclaimer</h4>
    <p>Past performance is not indicative of future results. This analysis is based on historical
    fund data and current market conditions. It should not be considered personal financial advice.
    Please consult with a licensed financial advisor and review the fund's Product Highlight Sheet
    (PHS) and Master Prospectus before making any investment decision. All investments carry risk,
    including the possible loss of principal.</p>

    <h4>Cooling-Off Right</h4>
    <p>First-time investors with Public Mutual are entitled to a 6 business day cooling-off period
    from the date of the first purchase, during which units may be redeemed at the original NAV
    paid.</p>

    <h4>Conflict of Interest</h4>
    <p>Shoo Kyuk Wei (Solid) is a Licensed Unit Trust Consultant and Licensed Private Retirement
    Scheme (PRS) Consultant representing Public Mutual Berhad (FIMM No: F01091705). Recommendations
    are limited to funds within the Public Mutual range.</p>
  </div>

  <div class="sources">
    <h4>Sources &amp; References</h4>
    <ul>
      <li>FundMaster workbook — <code>[filename].xlsx</code> (MFR data, [Month Year])</li>
      <li>Product Highlight Sheets — <code>unit-trust/product-highlight-sheet-phs/[Abbr]_PHS.pdf</code> (one entry per recommended fund)</li>
      <!-- web search sources (one <li> per URL) -->
      <li><a href="[URL]">[Source title — publication, date]</a></li>
    </ul>
  </div>
</div>
```

The four disclaimer sub-headings (AI-Generated Document / Regulatory Disclaimer / Cooling-Off
Right / Conflict of Interest) are mandatory and rendered in this exact order — the AI-Generated
Document block is always first so the reader sees the attribution before the rest of the
regulatory text. Sources sub-headings are optional grouping; one `<li>` per URL.

---

## 12. Document Footer

```html
<div class="doc-footer">
  <div class="credit-line">
    <strong>Shoo Kyuk Wei (Solid)</strong> &middot; Licensed UTC &amp; PRS Consultant &middot; Public Mutual Berhad
  </div>
  <div>+601173381713 &middot; me@engineerdad.my &middot; FIMM No: F01091705</div>
  <div>Confidential — prepared [DD Mon YYYY]</div>
</div>
```

---

## Banned

- **No Google Fonts** — no `@import`, no `<link>` to external font services.
- **No serif fonts** anywhere.
- **No gradient backgrounds** except `conic-gradient` for pie charts.
- **No diagonal stripes, decorative blobs, drop shadows, or bevels.**
- **No box-shadow on cards.**
- **No external CSS files** — copy `design_system.css` into the `<style>` block byte-for-byte.
- **No JavaScript.**
- **No custom colors** — only the `:root` variables defined in `design_system.css`.
- **No section reordering, renaming, or omission** (except the conditional Foundation block).
- **No fee values copied from a prior proposal** — every value must come from the current PHS.
