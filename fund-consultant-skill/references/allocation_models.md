# Portfolio Allocation Models

## Alpha-Anchored Multi-Factor Philosophy

Raw return is vanity. **Alpha is sanity.** But alpha alone is an incomplete answer.

A fund returning 8% when its benchmark returned 3% has alpha of +5% — genuine skill. But for an
aggressive investor targeting 15% p.a., that 8% absolute return is still insufficient regardless
of how excellent the alpha is. Both dimensions matter.

You are paying 1.50–1.80% annually for active management. Alpha must justify the cost — and the
fund's absolute return must match the investor's goals. The selection engine weights both.

---

## Fund Selection Engine — 5 Layers

### Layer 1: Universe Filter
- **Qualified only** — must beat benchmark in ≥60% of available periods
- **Shariah filter** — apply based on SA Q8 response
- **Risk Level ceiling** — fund Risk Level must be ≤ profile maximum

### Layer 2: Composite Fund Score (CFS) Ranking

Funds are ranked by CFS = weighted combination of four normalised dimensions:

```
CFS = (w_A × Alpha_N) + (w_R × ReturnFit_N) + (w_E × Efficiency_N) + (w_M × Momentum_N)
```

All dimensions normalised 0–100 within each derived class (Equity-equivalent / Balanced / Defensive).

**Dimension 1 — Alpha (Manager Skill):**

| Period | Weight | Rationale |
|--------|--------|-----------|
| 3Y Alpha | 40% | Current team's track record — most reliable signal |
| 5Y Alpha | 30% | Market cycle smoothing — structural edge |
| 1Y Alpha | 20% | Recent execution and momentum |
| YTD Alpha | 10% | Very recent direction — lowest weight due to noise |

Penalties: halve score if 3Y or 5Y alpha is negative; flag "benchmark-hugger" if all periods < 1%.

**Dimension 2 — Return Fit (Absolute Return vs E_target):**
- Primary period: 5Y annualised fund return (long-term pitch)
- Score 100 if Return_Ratio ≥ 1.5; 80 if = 1.0; 50 if = 0.75; 20 if = 0.5; 0 if negative
- Return_Ratio = Fund_Return_5Y / E_target

**Dimension 3 — Efficiency (Risk-Adjusted Skill):**
- `3Y Alpha / Volatility Factor` — normalised within derived class
- High score = manager earns alpha without taking excessive risk

**Dimension 4 — Momentum (ATH Proximity):**
- Base score from ATH Drawdown (0% to −5% = 80, >−40% = 10)
- Recovery velocity bonus: <30 days from ATH = +15, >365 days = −10

**Profile-Adaptive Weights:**

| Dimension | Conservative | Moderate | Mod. Aggressive | Aggressive |
|---|---|---|---|---|
| Alpha `w_A` | 40% | 35% | 30% | 25% |
| Return Fit `w_R` | 15% | 25% | 30% | 35% |
| Efficiency `w_E` | 35% | 25% | 20% | 15% |
| Momentum `w_M` | 10% | 15% | 20% | 25% |

Weights shift further based on E_target deviation from profile midpoint (up to ±10%).
See SKILL.md Step 3 for full specification.

**Tiebreaker:** CFS within 2 points → break by Alpha_N, then Efficiency_N.

### Layer 3: Alpha Efficiency (embedded in CFS Dimension 3)
After selecting top-ranked funds per category, verify:
- No single sector > 40% of total equity allocation
- No single country > 60% of total equity allocation (Malaysia exception: up to 80%)
- At least 2 different fund types in portfolio
- At least 3 different sectors represented across equity picks

If portfolio is over-concentrated, swap the least-diversifying fund for the next-ranked alternative.

### Layer 5: ATH Momentum Overlay
Final adjustment based on current market positioning:

| Drawdown Range | Signal | Action |
|----------------|--------|--------|
| 0% to -5% | Strong momentum — near ATH | Favor for Moderately Aggressive/Aggressive profiles |
| -5% to -15% | Neutral | No adjustment — rely on alpha ranking |
| -15% to -30% | Recovery potential | Neutral to positive for long-horizon profiles |
| > -30% | Deep value / contrarian | Only for Aggressive + horizon >10Y; flag the risk |

---

## Portfolio Templates by Risk Profile

### Conservative (Score 7–11)

| Category | Allocation | # Funds | Selection Priority |
|----------|-----------|---------|-------------------|
| Bond / Sukuk | 40–50% | 2 | Highest alpha, lowest VF |
| Money Market | 10–20% | 1 | Capital preservation (PMMF, PeMMF, etc.) |
| Mixed Asset (conservative) | 20–30% | 1 | Low equity component (30-40% type) |
| Equity (dividend/income) | 10–20% | 1 | Low VF, income-oriented, RL 1-2 only |

**Geographic bias:** 80%+ Malaysia (strongest qualification rates, lowest FX risk)
**Target weighted VF:** < 7.0 (Low volatility band)

### Moderate (Score 12–17)

| Category | Allocation | # Funds | Selection Priority |
|----------|-----------|---------|-------------------|
| Equity (diversified) | 30–40% | 2 | Highest alpha, RL ≤ 3, diversified sectors |
| Mixed Asset (balanced) | 20–25% | 1 | Built-in diversification, moderate equity split |
| Bond / Sukuk | 20–30% | 1-2 | Alpha-positive, income component |
| Money Market | 5–10% | 1 | Liquidity buffer |

**Geographic bias:** 70% Malaysia, 15–20% Asia/Greater China, 10% Global (US/Europe)
**Target weighted VF:** 7.0–10.0 (Moderate volatility band)

### Moderately Aggressive (Score 18–23)

| Category | Allocation | # Funds | Selection Priority |
|----------|-----------|---------|-------------------|
| Equity (core) | 40–55% | 2-3 | Top alpha + alpha efficiency, RL ≤ 4 |
| Equity (satellite) | 10–15% | 1 | Asia/Greater China or Global exposure for diversification |
| Mixed Asset (growth) | 15–20% | 1 | Higher equity component (60-70% type) |
| Bond / Sukuk | 10–15% | 1 | Ballast during equity corrections |
| Money Market | 5% | 0-1 | Tactical dry powder |

**Geographic bias:** 55–60% Malaysia, 20–25% Asia/Greater China, 15% Global (US/Europe), 5% Emerging (ex-Asia)
**Target weighted VF:** 9.0–12.0 (Moderate-High band)

### Aggressive (Score 24–28)

| Category | Allocation | # Funds | Selection Priority |
|----------|-----------|---------|-------------------|
| Equity (core — high alpha) | 50–60% | 2-3 | Absolute top alpha generators, any RL |
| Equity (thematic/sector) | 15–20% | 1-2 | Sector conviction plays (tech, small-cap, US/global) |
| Equity (regional) | 10–15% | 1 | Asia/Greater China or Global alpha plays |
| Bond / Sukuk | 5–10% | 1 | Minimal ballast |
| Money Market | 0–5% | 0 | Optional |

**Geographic bias:** 45–50% Malaysia, 20–25% Asia/Greater China, 20–25% Global (US/Europe), 5–10% Emerging (ex-Asia)
**Target weighted VF:** 11.0+ (High band acceptable)

---

## Fee Transparency Framework

For every recommended fund, calculate and present:

```
Annual cost   = Management Fee + Trustee Fee (typically 1.50–1.80% equity, 0.75–1.00% bond)
Entry cost    = Sales Charge (up to 5–6.5% equity, 0% money market)
Alpha earned  = 3Y annualised alpha
Net value-add = Alpha earned − Annual cost
```

**Decision rule for the client:**
- Net value-add > 0 → "The fund manager is earning their fee and then some"
- Net value-add ≈ 0 → "Breaking even on fees — consider cheaper alternatives if available"
- Net value-add < 0 → Should not be recommended (already filtered out by qualification screen)

---

## Distribution Strategy by Profile

| Profile | Distribution Preference | Rationale |
|---------|------------------------|-----------|
| Conservative | Payout (for income-seeking) or Reinvest | Income supplements living expenses |
| Moderate | Reinvest (default) | Compounding effect, tax-exempt in Malaysia |
| Moderately Aggressive | Reinvest | Maximize compounding over long horizon |
| Aggressive | Reinvest | Maximum capital accumulation |

---

## Rebalancing Triggers

Recommend portfolio review when:
1. **Time-based:** Every 6 months (minimum), or quarterly for Moderately Aggressive/Aggressive
2. **Drift-based:** Any fund category drifts >10% from target allocation
3. **Life event:** Job change, marriage, child, property purchase, retirement
4. **Market event:** Major correction (>15% broad market drawdown) — opportunity to top up equity
5. **New MFR data:** When a new fund screener run produces updated qualification results
