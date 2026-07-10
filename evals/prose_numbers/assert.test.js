"use strict";
/**
 * Offline unit tests for assert.js — proves the buried-error reduction logic
 * deterministically, WITHOUT any model API call (this environment has no
 * ANTHROPIC_API_KEY; see docs/superpowers/sdd/task-3-report.md for the live
 * acceptance-crux status). Every test here feeds a hand-written MOCK judge
 * output (the shape a real Claude judge call would return) through
 * `gradeJudgeOutput` / `reduceClaims` and checks the result — no network,
 * no `npx promptfoo eval`.
 *
 * Run with: node --test evals/prose_numbers/assert.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const assertEntryPoint = require("./assert.js");
const {
  parseJudgeOutput,
  reduceClaims,
  gradeJudgeOutput,
  plantedClaimIsFlagged,
} = assertEntryPoint;

const FIXTURES_DIR = path.join(__dirname, "fixtures");

function loadFixture(filename) {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, filename), "utf8"));
}

// Mirrors what tests/load-fixtures.js puts into a promptfoo test case's vars
// — the fields gradeJudgeOutput reads to know what to check the judge's
// output against.
function fixtureVars(fixture) {
  return {
    slot_key: fixture.slot_key,
    expect: fixture.expect,
    offending_sentence: fixture.offending_sentence,
    category: fixture.category,
  };
}

// ── (a) all-entailed per-claim list against a `good` fixture → pass ────────

test("(a) all-entailed claims pass against a good fixture", () => {
  const fixture = loadFixture("why_PIATAF_good_verbatim.json");
  assert.equal(fixture.category, "good");
  assert.equal(fixture.expect, "entailed");

  const mockJudgeOutput = JSON.stringify({
    claims: [
      { text: "Composite Fund Score of 86 out of 100", verdict: "entailed" },
      { text: "the highest of any holding", verdict: "entailed" },
      { text: "6.2% weighted alpha versus its benchmark", verdict: "entailed" },
      { text: "more than any other fund in the lineup", verdict: "entailed" },
      { text: "40% allocation, the largest single position", verdict: "entailed" },
    ],
    entailed: true,
    offending_sentence: null,
  });

  const result = gradeJudgeOutput(mockJudgeOutput, fixtureVars(fixture));
  assert.equal(result.pass, true, result.reason);
  assert.equal(result.metadata.reducedEntailed, true);
  assert.equal(result.metadata.failingClaim, null);
});

// ── (b) one contradicted claim → reduced entailed=false + offending_sentence
//        handling → pass against a seeded-bad-single fixture ──────────────

test("(b) a single contradicted claim reduces to entailed=false and matches a seeded-bad-single fixture", () => {
  const fixture = loadFixture("why_PCSF_seeded_bad_single.json");
  assert.equal(fixture.category, "seeded-bad-single");
  assert.equal(fixture.expect, "contradicted");

  const offendingClaimText =
    "45% of the portfolio and ranked second overall by Composite Fund Score";

  const mockJudgeOutput = JSON.stringify({
    claims: [
      { text: "3.4% weighted alpha", verdict: "entailed" },
      { text: "blended edge of roughly 5% over benchmark", verdict: "entailed" },
      { text: "strongest of the three derived-class buckets", verdict: "entailed" },
      { text: offendingClaimText, verdict: "contradicted" },
    ],
    entailed: false,
    offending_sentence: fixture.offending_sentence,
  });

  const result = gradeJudgeOutput(mockJudgeOutput, fixtureVars(fixture));
  assert.equal(result.pass, true, result.reason);
  assert.equal(result.metadata.reducedEntailed, false);
  assert.equal(result.metadata.failingClaim.text, offendingClaimText);
  // Bonus check: the judge's offending_sentence matches the fixture's planted one.
  assert.equal(result.metadata.plantedClaimFlagged, true);
});

test("(b2) a judge that says entailed=false but supplies no offending_sentence fails the contract check", () => {
  const fixture = loadFixture("why_PCSF_seeded_bad_single.json");

  const mockJudgeOutput = JSON.stringify({
    claims: [
      { text: "3.4% weighted alpha", verdict: "entailed" },
      { text: "45% allocation", verdict: "contradicted" },
    ],
    entailed: false,
    offending_sentence: null, // violates the contract: must be non-null when entailed=false
  });

  const result = gradeJudgeOutput(mockJudgeOutput, fixtureVars(fixture));
  assert.equal(result.pass, false, "must fail: offending_sentence is null despite a contradicted claim");
});

// ── (c) a buried-contradicted list (the acceptance crux) → correct reduction
//        regardless of WHERE in the list the failing claim sits ───────────

test("(c) a contradicted claim buried in the middle of several correct ones still reduces to entailed=false", () => {
  const fixture = loadFixture("why_PSTIF_seeded_bad_buried.json");
  assert.equal(fixture.category, "seeded-bad-buried");
  assert.equal(fixture.expect, "contradicted");

  const buriedClaimText =
    "Combined, PBLNF and PSTIF's Defensive-and-Balanced blend delivers a portfolio-wide weighted alpha of roughly 4%";

  const mockJudgeOutput = JSON.stringify({
    claims: [
      { text: "PSTIF ranks second by Composite Fund Score, at 45 out of 100", verdict: "entailed" },
      { text: "weighted alpha stands at 1.2%", verdict: "entailed" },
      // The planted error sits in the MIDDLE of the list, not first or last —
      // this is exactly the "lost in the middle" shape the per-claim
      // enumeration contract exists to defend against (design spec §7).
      { text: buriedClaimText, verdict: "contradicted" },
      { text: "allocates 35% of the portfolio, second-largest after PBLNF", verdict: "entailed" },
      { text: "65% in fixed income assets", verdict: "entailed" },
    ],
    entailed: false,
    offending_sentence: fixture.offending_sentence,
  });

  const result = gradeJudgeOutput(mockJudgeOutput, fixtureVars(fixture));
  assert.equal(result.pass, true, result.reason);
  assert.equal(result.metadata.reducedEntailed, false);
  assert.equal(result.metadata.failingClaim.text, buriedClaimText);
  assert.equal(result.metadata.plantedClaimFlagged, true);
});

test("(c2) a judge that mislabels its OWN top-level entailed=true is still caught by the code-side reduction", () => {
  // This is the crux the per-claim contract is built to defend against: even
  // if the judge's own holistic boolean says "true" (e.g. it skimmed past
  // the buried claim), a single non-entailed verdict anywhere in `claims`
  // must still fail the reduction, because reduceClaims() NEVER reads
  // parsed.entailed — only parsed.claims.
  const fixture = loadFixture("why_PSTIF_seeded_bad_buried.json");

  const mockJudgeOutput = JSON.stringify({
    claims: [
      { text: "45 out of 100", verdict: "entailed" },
      { text: "1.2% weighted alpha", verdict: "entailed" },
      { text: "portfolio-wide weighted alpha of roughly 4%", verdict: "contradicted" },
      { text: "35% of the portfolio", verdict: "entailed" },
      { text: "65% in fixed income", verdict: "entailed" },
    ],
    entailed: true, // WRONG — the judge's own boolean disagrees with its claims list
    offending_sentence: fixture.offending_sentence,
  });

  const result = gradeJudgeOutput(mockJudgeOutput, fixtureVars(fixture));
  // The fixture expects "contradicted"; the code-side reduction (not the
  // judge's mislabeled top-level boolean) must still land on entailed=false,
  // so this test case correctly PASSES the assertion despite the judge's
  // internal inconsistency.
  assert.equal(result.metadata.reducedEntailed, false);
  assert.equal(result.pass, true, result.reason);
});

// ── Malformed judge output → fail closed, not an uncaught exception ───────

test("malformed (non-JSON) judge output fails the assertion instead of throwing", () => {
  const fixture = loadFixture("why_PIATAF_good_verbatim.json");
  const result = gradeJudgeOutput("Sure! This prose looks entailed to me.", fixtureVars(fixture));
  assert.equal(result.pass, false);
  assert.match(result.reason, /did not parse as JSON/);
});

test("an empty claims array fails closed (never silently passes)", () => {
  const fixture = loadFixture("why_PIATAF_good_verbatim.json");
  const mockJudgeOutput = JSON.stringify({ claims: [], entailed: true, offending_sentence: null });
  const result = gradeJudgeOutput(mockJudgeOutput, fixtureVars(fixture));
  assert.equal(result.metadata.reducedEntailed, false);
  assert.equal(result.pass, false, "an empty claims list must not be treated as vacuously entailed");
});

test("a claims array with an invalid verdict value fails the contract-shape check", () => {
  const fixture = loadFixture("why_PIATAF_good_verbatim.json");
  const mockJudgeOutput = JSON.stringify({
    claims: [{ text: "86 CFS", verdict: "probably-fine" }],
    entailed: true,
    offending_sentence: null,
  });
  const result = gradeJudgeOutput(mockJudgeOutput, fixtureVars(fixture));
  assert.equal(result.pass, false);
  assert.match(result.reason, /violated the per-claim JSON contract/);
});

// ── parseJudgeOutput: tolerant of a ```json fence despite being told not to
//    use one ────────────────────────────────────────────────────────────

test("parseJudgeOutput strips a ```json fence", () => {
  const fenced = "```json\n" + JSON.stringify({ claims: [], entailed: true, offending_sentence: null }) + "\n```";
  const parsed = parseJudgeOutput(fenced);
  assert.deepEqual(parsed.claims, []);
  assert.equal(parsed.entailed, true);
});

test("parseJudgeOutput throws on genuinely unparseable output", () => {
  assert.throws(() => parseJudgeOutput("not json at all, no braces"));
});

// ── reduceClaims: pure-function unit tests, independent of any fixture ────

test("reduceClaims: all entailed -> entailed true, no failing claim", () => {
  const { entailed, failingClaim } = reduceClaims([
    { text: "a", verdict: "entailed" },
    { text: "b", verdict: "entailed" },
  ]);
  assert.equal(entailed, true);
  assert.equal(failingClaim, null);
});

test("reduceClaims: first failing claim wins when multiple fail", () => {
  const { entailed, failingClaim } = reduceClaims([
    { text: "a", verdict: "entailed" },
    { text: "b", verdict: "contradicted" },
    { text: "c", verdict: "underivable" },
  ]);
  assert.equal(entailed, false);
  assert.equal(failingClaim.text, "b");
});

test("reduceClaims: underivable fails just like contradicted", () => {
  const { entailed } = reduceClaims([{ text: "a", verdict: "underivable" }]);
  assert.equal(entailed, false);
});

// ── plantedClaimIsFlagged: bonus fuzzy-match heuristic ────────────────────

test("plantedClaimIsFlagged ignores HTML tags and whitespace/case differences", () => {
  const fixtureSentence =
    "At <strong>45%</strong> of the portfolio and ranked <strong>second</strong> overall by Composite Fund Score, PCSF is the second-largest core holding.";
  const judgeSentence = "at 45% of the portfolio and ranked second overall by composite fund score";
  assert.equal(plantedClaimIsFlagged(judgeSentence, fixtureSentence), true);
});

test("plantedClaimIsFlagged is false for unrelated sentences", () => {
  assert.equal(
    plantedClaimIsFlagged("PIATAF has an 86 CFS score.", "PSTIF allocates 35% to fixed income."),
    false
  );
});

// ── Promptfoo ENTRY-POINT wrapper (`module.exports` itself) ───────────────
//
// Carried over from the Phase 3 review: everything above calls
// `gradeJudgeOutput` directly, but Promptfoo's `javascript` assertion
// (`value: file://assert.js`, no `:functionName` suffix — see
// `loadFromJavaScriptFile` in promptfoo's evaluator) actually invokes
// `module.exports` itself as `(output, context) => GradingResult`,
// destructuring `context.vars`. That thin wrapper
// (`assertProseNumberEntailment` in assert.js) was previously untested.

test("(entry point) module.exports itself grades a realistic promptfoo (output, context) call", () => {
  const fixture = loadFixture("why_PIATAF_good_verbatim.json");
  const mockJudgeOutput = JSON.stringify({
    claims: [
      { text: "Composite Fund Score of 86 out of 100", verdict: "entailed" },
      { text: "6.2% weighted alpha versus its benchmark", verdict: "entailed" },
    ],
    entailed: true,
    offending_sentence: null,
  });
  // Realistic promptfoo assertion-call shape: `context` carries `vars` plus
  // other fields (prompt/test/etc.) assert.js doesn't need and must ignore.
  const context = {
    vars: fixtureVars(fixture),
    prompt: { raw: "judge prompt text", label: "judge.md" },
    test: { description: "good: why.PIATAF" },
  };

  const result = assertEntryPoint(mockJudgeOutput, context);
  assert.equal(result.pass, true, result.reason);
  assert.equal(result.metadata.reducedEntailed, true);
});

test("(entry point) a missing context fails closed rather than throwing", () => {
  const mockJudgeOutput = JSON.stringify({
    claims: [{ text: "some claim", verdict: "entailed" }],
    entailed: true,
    offending_sentence: null,
  });

  // No context at all — assertProseNumberEntailment must default vars to
  // {} rather than throwing on `context.vars`.
  const result = assertEntryPoint(mockJudgeOutput, undefined);
  assert.equal(result.pass, false, "with no fixture context, expect/category are undefined and must not vacuously pass");
});

test("(entry point) a malformed context (vars is null) fails closed rather than throwing", () => {
  const mockJudgeOutput = JSON.stringify({
    claims: [{ text: "some claim", verdict: "entailed" }],
    entailed: true,
    offending_sentence: null,
  });

  const result = assertEntryPoint(mockJudgeOutput, { vars: null });
  assert.equal(result.pass, false);
});
