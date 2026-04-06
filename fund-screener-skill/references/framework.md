# Fund Code Review Framework — Checkpoints & Engineering Analogies

## The Core Metaphor

The overarching metaphor: reviewing a fund is like reviewing a pull request before merging to production. You wouldn't merge code without checking it against a checklist. You shouldn't invest money without doing the same.

The user (Solid) is a former Head of Engineering who pivoted to stock trading and Public Mutual unit trust consulting. The content bridges both worlds — using engineering language as a hook while keeping the actual analysis accessible to anyone.

---

## Checkpoint 1: Benchmark
**Engineering analogy:** "What is this code supposed to do?" / "What's the reference branch?"

**What to extract:**
- The benchmark index name (e.g. FBM KLCI, S&P Shariah BMI Asia Ex-Japan, MSCI)
- What that benchmark represents in plain language
- Whether the benchmark is appropriate for the fund's strategy

**Key point to make:**
If a fund can't beat its benchmark consistently, you're paying active management fees for index-level returns. Just buy an index fund instead.

---

## Checkpoint 2: Expense Ratio
**Engineering analogy:** "Overhead cost" / "Compute overhead" / "Wasted CPU cycles"

**What to extract:**
- Management fee (% p.a.)
- Trustee fee (% p.a.)
- Total = management + trustee
- Sales charge (one-time entry cost, mention it's negotiable)

**Key point to make:**
The total annual drag comes out of returns every year regardless of market direction. The fund must generate alpha above this drag just to break even for the investor. Frame it as: "The fund needs to beat the benchmark by at least X% per year just to justify its existence."

**Malaysian context:**
- Active equity funds: typically 1.50-1.80% management fee
- Fixed income/bond funds: typically 0.75-1.00%
- Mixed asset: typically 1.25-1.65%

---

## Checkpoint 3: Annualised Returns vs Benchmark
**Engineering analogy:** "Is it consistently outperforming?" / "One good sprint doesn't make a reliable engineer"

**What to extract:**
- Full performance table from MFR (all periods: YTD, 1Y, 3Y, 5Y, 10Y, 20Y, Since Commencement)
- Use ANNUALISED returns, not total returns, for comparison
- Calculate the alpha (difference) for each period

**How to present:**
Show a clean table with Fund vs Benchmark vs Alpha/Difference for each period. Use checkmarks for outperformance and warning flags for underperformance.

**Key point to make:**
- Short-term (1Y, YTD) can be noisy — flag but don't overweight
- Medium-term (3Y, 5Y) shows the current team's execution
- Long-term (10Y, 20Y, Since Commencement) shows structural advantage
- A fund that beats in long periods but lags in 1-year might be in a rough patch — not necessarily broken

---

## Checkpoint 4: Drawdown History
**Engineering analogy:** "What happens when prod goes down?" / "Stress test" / "Chaos engineering" / "Incident postmortem"

**What to extract:**
- Annual calendar year returns (all years available in MFR)
- Identify: worst single year, COVID year (2020), most recent full year
- Count how many years out of N the fund beat the benchmark

**Key scenarios to highlight:**
- **COVID 2020:** This is always the most dramatic data point. The market crashed in Feb-Mar 2020 and recovered. Did the fund navigate it or get crushed?
- **Worst year ever:** What's the maximum pain an investor would have experienced? Frame as: "If you'd invested at the worst possible time..."
- **Most recent year:** Is the fund in a good or bad recent patch?

**Key point to make:**
Active funds that take concentrated bets can swing both ways. A great COVID year doesn't mean you won't have a terrible 2022. The audience needs to understand the trade-off between upside capture and downside risk.

---

## Checkpoint 5: Fund Manager Tenure
**Engineering analogy:** "Who's running the codebase?" / "Senior dev turnover" / "Institutional memory" / "Bus factor"

**What to extract:**
- Fund manager entity (always "Public Mutual Berhad" for Public Mutual funds)
- Fund launch/commencement date → calculate years of operation
- Investment team from publicmutual.com.my/Menu/Corporate/Our-People:
  - CIO name and tenure
  - Relevant Co-Heads / Deputy Directors and their tenure
  - Specialist most likely to manage this specific fund type

**Important transparency note:**
Public Mutual does not publicly disclose which individual manages which specific fund. The Master Prospectus and MFR both list only "Public Mutual Berhad" as the manager. Individual team profiles are on the website but without fund assignments. Always be transparent about this limitation in the content.

**Key point to make:**
Public Mutual uses a team-based model — not a star fund manager model. This reduces "key person risk" but also means you can't easily track if the person who drove past performance is still there. Frame it honestly.

---

## Bonus Checkpoint 6: Volatility Factor
**Engineering analogy:** "Error rate" / "System stability" / "Uptime SLA"

**What to extract:**
- Volatility Factor number (from Lipper Analytics, shown in MFR)
- Classification: Very Low / Low / Moderate / High / Very High

**Context for the audience:**
- Very Low (1-3): Bond/money market funds — smooth ride
- Low (3-6): Conservative mixed asset
- Moderate (6-10): Balanced equity funds
- High (10-15): Aggressive equity, sector funds
- Very High (15+): Concentrated/thematic, emerging markets

---

## Bonus Checkpoint 7: Top Holdings + Sector Concentration
**Engineering analogy:** "Architecture review" / "Monolith vs microservices" / "Single point of failure"

**What to extract:**
- Top 5 holdings (names)
- Top 5 sectors with % weights
- Geographic breakdown (domestic vs foreign, country breakdown of foreign)
- Asset allocation (equity vs fixed income vs money market)

**Key point to make:**
If 50%+ of the fund is in one sector, that's a monolithic architecture — one bad event in that sector takes everything down. Diversification = microservices approach. Neither is inherently better, but the investor needs to know which architecture they're buying into.

---

## Bonus Checkpoint 8: Calendar Year Consistency
**Engineering analogy:** "Sprint velocity consistency" / "Shipping cadence reliability"

**What to extract:**
- For each calendar year in the MFR data, mark whether the fund beat the benchmark
- Calculate: X out of N years beat benchmark

**Key point to make:**
A fund that beats the benchmark 8/10 years is more trustworthy than one that beats it 4/10 years even if both have similar long-term returns. Consistency matters — you want a team that ships reliably, not one that has one great year and coasts.

---

## Verdict Framework

The final verdict should use one of these templates:

**Strong pass:** All 5 core checkpoints green, minor flags only
> "Approved. Ship it for long-term investors."

**Pass with flags:** Most checkpoints green, 1-2 notable flags
> "Approved with flags. [Describe the specific risks]. Suitable if [investor profile]."

**Mixed:** Roughly even green and flags
> "Needs discussion. Strong in [areas] but concerning in [areas]. Depends on your [timeline/risk appetite]."

**Flagged:** More concerns than strengths
> "Flagged for review. The data raises questions about [specific issues]. Needs further investigation before committing."

The verdict should never be "don't buy" or "definitely buy" — it's "here's what the data says, here's the trade-off, you decide." The goal is to build trust as a consultant who teaches thinking, not one who pushes products.

---

## Tone Guidelines

- Use engineering analogies as hooks, not as the entire explanation. The analogy opens the door; the actual insight keeps people reading.
- Be conversational, not academic. Write like you're explaining it to a smart friend over coffee.
- Be honest about bad numbers. Flagging underperformance builds more trust than hiding it.
- End with empowerment: "Use this framework on any fund" — position the audience as capable of doing this themselves.
- Never use: "guaranteed", "sure thing", "can't lose", "best fund". Always use: "track record suggests", "historical data shows", "based on the numbers".
