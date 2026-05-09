# Shortlist Template (Mode B — e-Series Fund Shortlist)

> **This template defines the complete HTML skeleton for the e-Series Fund Shortlist output**
> (Step 4e: new investor with upfront capital < RM 1,000). It is structurally distinct from the
> standard Fund Proposal — there is no allocation, no portfolio summary, no investment strategy.
> The artefact is a decision-making document for the consultant's first client meeting.
>
> Every generated shortlist must use this skeleton **verbatim** — substitute only the content
> tokens marked `[BRACKETED]`. Do not add, remove, rename, or reorder sections. Embed
> `references/design_system.css` byte-for-byte in the `<style>` block (same stylesheet as the
> standard Proposal — single source of truth).
>
> For the standard committed-allocation proposal, see `references/proposal_template.md`.

---

## Output File

```
output/fund_proposals/FundShortlist_[Profile]_[ClientLastName]_[MonYYYY]_v[SKILL_VERSION].html
```

Example: `FundShortlist_Moderate_AhmadRazif_May2026_v1.25.html`.

The skill-version suffix (`_v[SKILL_VERSION]`) is mandatory — same convention as proposal mode.
Substitute the value from the SKILL.md frontmatter `version` field (no `v` prefix in the token —
the template provides it).

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
  <title>e-Series Fund Shortlist — [Client] — [Month Year]</title>
  <style>
    /* ↓↓↓ Embed the entire contents of references/design_system.css HERE, verbatim ↓↓↓ */
  </style>
</head>
<body>

  <!-- 1. COVER PAGE -->                       (always)
  <!-- 2. FOUNDATION INTRO -->                 (always — Step 4e is new-investor by definition)
  <div class="page">
    <!-- 3. SECTION 1 — Why a Shortlist -->
    <!-- 4. SECTION 2 — Global & Local Macro Context -->
    <!-- 5. SECTION 3 — Client Risk Profile -->
    <!-- 6. SECTION 4 — Candidate Funds (3 cards) -->
    <!-- 7. SECTION 5 — Candidate Comparison -->
    <!-- 8. SECTION 6 — Fee Disclosure -->
    <!-- 9. SECTION 7 — Disclaimer, Sources & References -->
    <!-- 10. DOCUMENT FOOTER -->
  </div>

</body>
</html>
```

**Self-check before finalizing:** count the rendered `<div class="section">` elements — there
must be exactly **7**. The cover, foundation, and document footer are not `.section` blocks.
Section 4 must contain exactly **3** `<div class="fund-card">` blocks (Candidates 1, 2, 3).

**Sections explicitly omitted vs the standard Proposal:** Portfolio Summary, Portfolio Exposure
(portfolio-weighted), Investment Strategy. Those decisions are deferred to the client meeting
and the post-selection committed proposal.

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
    <div class="cover-eyebrow">E-SERIES FUND SHORTLIST</div>
    <div class="cover-divider"></div>
    <div class="cover-title">Fund<br>Shortlist</div>
    <div class="cover-subtitle">For [Client Name] &mdash; Allocation Not Finalised</div>
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
        <div class="cover-meta-label">Upfront Capital</div>
        <div class="cover-meta-value">RM [XXX]</div>
      </div>
      <div>
        <div class="cover-meta-label">Candidates</div>
        <div class="cover-meta-value">3 of [N] e-series</div>
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
    <span>Confidential — Consultant Review</span>
    <span>Prepared [DD Mon YYYY]</span>
  </div>
</div>
```

**Cover content rules (vs standard Proposal — these are the only differences):**
- `cover-eyebrow` = literal string `E-SERIES FUND SHORTLIST`
- `cover-title` = literal string `Fund<br>Shortlist`
- `cover-subtitle` = literal `For [Client Name] &mdash; Allocation Not Finalised`
- `cover-meta-grid` cells differ at positions 4 (`Upfront Capital`) and 5 (`Candidates`).
  Total = 6 cells, identical 3×2 layout to standard Proposal.
- `cover-footer` slot 3 reads `Confidential — Consultant Review`. Slots 1, 2, 4 are
  identical to standard Proposal (FIMM / version stamp / Prepared date).
- Consultant `cover-contact` block is **invariant** — identical to standard Proposal.

---

## 2. Foundation Intro

Render this block always (Step 4e is new-investor by definition). Same structure as the
standard Proposal — see `proposal_template.md` Section 2 for the locked HTML.

The "Why a Starter Portfolio" sub-paragraph is replaced with this shortlist-specific note:

```html
<h3>4. Why a Shortlist</h3>
<p>Your starting capital sits below Public Mutual's standard RM 1,000 minimum, so we're working
with the e-Series funds — Public Mutual's digital-channel range with lower entry minimums.
This document presents three candidates that fit your profile. We will pick the final
allocation together at our first meeting once we discuss your goals in person.</p>
```

All other sub-blocks (What is a Unit Trust / How Returns Work / Cooling-Off Right) are identical.

---

## 3. Section 1 — Why a Shortlist

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">1</div>
    <div class="section-title">Why a Shortlist</div>
  </div>
  <div class="section-rule"></div>

  <div class="exec-summary">
    <ul>
      <li><strong>Constraint:</strong> upfront capital of RM [XXX] sits below the RM 1,000 minimum for standard unit trust subscriptions.</li>
      <li><strong>Solution:</strong> Public Mutual's <strong>e-Series</strong> range supports lower minimums via digital channels — these candidates are all e-Series funds.</li>
      <li><strong>This document:</strong> 3 candidates ranked by Composite Fund Score, all suited to a [Profile] profile. No allocation is committed yet.</li>
      <li><strong>Next step:</strong> at our first meeting we'll discuss your goals and decide which 1–2 to subscribe to first, then layer in the rest as your portfolio grows.</li>
    </ul>
  </div>
</div>
```

Exactly 4 bullets in this order — Constraint, Solution, This document, Next step.

---

## 4. Section 2 — Global & Local Macro Context

Same locked structure as the standard Proposal — see `proposal_template.md` Section 4.
Section number stays **2** (numbered in shortlist's own 1–7 sequence).

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">2</div>
    <div class="section-title">Global &amp; Local Macro Context</div>
  </div>
  <div class="section-rule"></div>
  <!-- macro table + medium-long horizon themes — identical to proposal_template.md -->
</div>
```

---

## 5. Section 3 — Client Risk Profile

Same locked structure as the standard Proposal — see `proposal_template.md` Section 5.
Section number stays **3**. Add one extra row at the bottom of the profile table:

```html
<tr><td><strong>Upfront Capital</strong></td><td>RM [XXX] (e-Series shortlist mode)</td></tr>
```

---

## 6. Section 4 — Candidate Funds

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">4</div>
    <div class="section-title">Candidate Funds</div>
  </div>
  <div class="section-rule"></div>

  <p style="color:var(--text-mid); margin-bottom:16px;">
    Three e-Series funds shortlisted by Composite Fund Score. Ranked highest to lowest. Each
    card includes the fund's own asset-class and geographic exposure (no portfolio-level
    weighting — allocation is decided at our meeting).
  </p>

  <!-- exactly 3 candidate cards, in CFS-rank order -->
</div>
```

### Candidate Card — locked structure

The candidate card is structurally a fund-card with these differences vs the standard Proposal
fund-card:

1. **Header:** no `.alloc` badge. Replace with a `.candidate-num` ribbon.
2. **Body:** add a `.fund-pies` block (asset class + geographic, both sized `.pie-chart.small`)
   immediately after the CFS bar. These are the fund's own holdings — not portfolio-weighted.

```html
<div class="fund-card">
  <div class="fund-card-header [equity|fixed-income|mixed-asset|money-market|gold|alpha-outlier]">
    <h3>[Fund Name] &middot; [Abbr]</h3>
    <span class="candidate-num">CANDIDATE [1|2|3]</span>
  </div>

  <div class="fund-meta">
    <span><strong>Type:</strong> [Equity/Mixed Asset/FI/MM/Gold]</span>
    <span><strong>RL:</strong> [1–5]</span>
    <span><strong>VF:</strong> [X.X]</span>
    <span><strong>Shariah:</strong> [Yes/No]</span>
    <span><strong>AUM:</strong> RM [X,XXX]M</span>
    <span><strong>Min Initial:</strong> RM [XXX]</span>
  </div>

  <div class="fund-card-body">

    <!-- (a) ALPHA WARNING — only if Status == "Disqualified" -->

    <!-- (b) CFS mini-bar — identical structure to proposal_template.md Section 6 -->
    <div class="cfs-bar">
      <div class="cfs-title">COMPOSITE FUND SCORE: <span class="cfs-score">[XX.X]</span> / 100</div>
      <!-- 4 cfs-row blocks — same as proposal -->
    </div>

    <!-- (c) Per-fund pie pair (NEW vs proposal) -->
    <h4>Fund Exposure — [Abbr]</h4>
    <div class="fund-pies">
      <div class="exposure-chart-block">
        <div class="exposure-chart-title">Asset Class</div>
        <div class="pie-chart small" style="background: conic-gradient( /* this fund's own asset-class slices */ );"></div>
        <div class="legend">
          <!-- legend items for THIS fund's asset allocation -->
        </div>
      </div>
      <div class="exposure-chart-block">
        <div class="exposure-chart-title">Geographic</div>
        <div class="pie-chart small" style="background: conic-gradient( /* this fund's own country slices */ );"></div>
        <div class="legend">
          <!-- legend items for THIS fund's geographic exposure (slices < 5% of fund merged into "Other") -->
        </div>
      </div>
    </div>

    <!-- (d) Performance table — same as proposal -->
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

    <!-- (e) Cost & Alpha mini-card — same as proposal -->
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

    <!-- (f) Why we're shortlisting it -->
    <h4>Why It's a Candidate</h4>
    <p>[2–4 sentences. Lead with the strongest selling point. Frame as "this is one of three options" — not "we chose this".]</p>

    <!-- (g) What to discuss -->
    <h4>To Discuss at Our Meeting</h4>
    <ul>
      <li>[Open question 1 — e.g., comfort with this fund's geographic concentration, distribution preference, RL acceptance]</li>
      <li>[Open question 2]</li>
    </ul>

  </div>
</div>
```

**Per-candidate pie rules:**
- Each pie is a **`.pie-chart.small`** (200×200) — half the proposal-mode size to keep the
  3-card section scannable.
- Asset Class chart uses the fund's **own** allocation columns (cols 35–40), no weighting.
- Geographic chart uses the fund's **own** GEO BREAKDOWN columns (cols 41–52). Slices < 5%
  of the fund are merged into "Other" (note: 5% per-fund, not the 2% portfolio threshold).
- Use the same color maps from SKILL.md Steps 7b–7c.

**Card order:** Candidate 1 (highest CFS) → Candidate 2 → Candidate 3 (lowest of the 3).

---

## 7. Section 5 — Candidate Comparison

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">5</div>
    <div class="section-title">Candidate Comparison</div>
  </div>
  <div class="section-rule"></div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Fund Name</th>
          <th>Type</th>
          <th>RL</th>
          <th>CFS</th>
          <th>Wtd Alpha</th>
          <th>3Y Return</th>
          <th>Key Strength</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>1</td>
          <td><strong>[Abbr]</strong></td>
          <td>[Type]</td>
          <td>[1–5]</td>
          <td>[XX.X]</td>
          <td class="[alpha-pos|alpha-neg]">[+X.XX]%</td>
          <td>[X.XX]%</td>
          <td>[1-line strength, e.g. "Highest 3Y alpha; AI capex leverage"]</td>
        </tr>
        <tr>
          <td>2</td>
          <td><strong>[Abbr]</strong></td>
          <td>[Type]</td>
          <td>[1–5]</td>
          <td>[XX.X]</td>
          <td class="[alpha-pos|alpha-neg]">[+X.XX]%</td>
          <td>[X.XX]%</td>
          <td>[1-line strength]</td>
        </tr>
        <tr>
          <td>3</td>
          <td><strong>[Abbr]</strong></td>
          <td>[Type]</td>
          <td>[1–5]</td>
          <td>[XX.X]</td>
          <td class="[alpha-pos|alpha-neg]">[+X.XX]%</td>
          <td>[X.XX]%</td>
          <td>[1-line strength]</td>
        </tr>
      </tbody>
    </table>
  </div>

  <p style="font-size:12px; color:var(--text-mid); margin-top:8px;">
    Ranked by Composite Fund Score (CFS). No allocation has been assigned — the choice between
    these three is made together at the client meeting.
  </p>
</div>
```

Exactly **8 columns** in this exact order. Exactly **3 rows** (one per candidate).

---

## 8. Section 6 — Fee Disclosure

Same locked structure as `proposal_template.md` Section 10 — same 8-column table, same PHS-sourcing
note. Section number is **6** in shortlist's 1–7 sequence. Three rows total (one per candidate).

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">6</div>
    <div class="section-title">Fee Disclosure</div>
  </div>
  <div class="section-rule"></div>
  <!-- identical 8-col table from proposal_template.md, 3 candidate rows -->
</div>
```

---

## 9. Section 7 — Disclaimer, Sources & References

Same locked structure as `proposal_template.md` Section 11. Section number is **7**. The
disclaimer block contains **four** mandatory `<h4>` sub-headings in this exact order:

1. **AI-Generated Document** (first — names the tool, embeds version, frames consultant review)
2. Regulatory Disclaimer
3. Cooling-Off Right
4. Conflict of Interest

The AI-Generated Document paragraph in shortlist mode is identical to proposal mode (it
references `fund-consultant skill, version [SKILL_VERSION]` regardless of output mode).

```html
<div class="section">
  <div class="section-header">
    <div class="section-num">7</div>
    <div class="section-title">Disclaimer, Sources &amp; References</div>
  </div>
  <div class="section-rule"></div>
  <!-- identical disclaimer + sources block from proposal_template.md (all 4 sub-headings) -->
</div>
```

---

## 10. Document Footer

Identical to `proposal_template.md` — see Section 12 there for the locked HTML.

---

## Banned

Identical ban list to `proposal_template.md`. Specifically for shortlist mode, **also** banned:

- **No `.alloc` badge** in candidate card headers (use `.candidate-num` ribbon instead).
- **No portfolio-weighted pie charts** — exposure pies are per-fund only.
- **No Investment Strategy section** — deferred to post-selection.
- **No Portfolio Summary section** — there is no portfolio yet.
- **No phrasing that implies allocation is final** — always frame as "candidates" / "shortlist" / "to be decided at meeting".
