"use strict";
/**
 * Offline unit tests for gate.js — proves the majority-of-5 aggregation +
 * 100%-recall/100%-precision threshold logic deterministically, with
 * hand-written synthetic per-fixture/per-sample result sets. No model API
 * call, no real `promptfoo eval` run (this environment has no
 * `ANTHROPIC_API_KEY`; see README.md's "Status" section).
 *
 * This is the offline proof, required by the task brief, that the gate
 * would actually go RED if a real judge run missed a buried planted error
 * — i.e. that the CI gate "bites" rather than rubber-stamping everything.
 *
 * Run with: node --test evals/prose_numbers/gate.test.js
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  EXPECTED_REPEAT,
  MIN_SAMPLES_FOR_MAJORITY,
  computeMajorityVerdicts,
  computeGateMetrics,
  extractPerSampleResults,
  formatReport,
  runGate,
} = require("./gate.js");

/**
 * Builds EXPECTED_REPEAT (5) synthetic per-sample results for one fixture.
 *
 * @param {string} fixtureId
 * @param {string} category
 * @param {number} passCount - how many of the 5 samples pass (0-5).
 * @returns {Array<{fixture_id: string, category: string, pass: boolean}>}
 */
function samplesFor(fixtureId, category, passCount) {
  return Array.from({ length: EXPECTED_REPEAT }, (_, i) => ({
    fixture_id: fixtureId,
    category,
    pass: i < passCount,
  }));
}

// A small synthetic corpus shaped like the real 19-fixture set: a mix of
// `good`, `seeded-bad-single`, and `seeded-bad-buried` fixtures.
function baselineAllCorrectCorpus() {
  return [
    ...samplesFor("why_PIATAF_good_verbatim", "good", 5),
    ...samplesFor("why_PCSF_good_derived", "good", 4), // majority still passes (4/5 >= 3)
    ...samplesFor("watch_PCSF_good_verbatim", "good", 3), // exactly the majority threshold
    ...samplesFor("why_PCSF_seeded_bad_single", "seeded-bad-single", 5),
    ...samplesFor("why_PSTIF_seeded_bad_buried", "seeded-bad-buried", 5),
    ...samplesFor("watch_PBLNF_seeded_bad_buried", "seeded-bad-buried", 3),
  ];
}

// ── (a) all-correct synthetic corpus -> gate is GREEN ─────────────────────

test("(a) an all-correct synthetic corpus passes the gate (100% recall, 100% precision)", () => {
  const perSample = baselineAllCorrectCorpus();
  const verdicts = computeMajorityVerdicts(perSample);
  const metrics = computeGateMetrics(verdicts);

  assert.equal(metrics.recall, 1);
  assert.equal(metrics.precision, 1);
  assert.deepEqual(metrics.recallMisses, []);
  assert.deepEqual(metrics.precisionMisses, []);
  assert.equal(metrics.gatePass, true);
});

// ── (b) THE OFFLINE GATE-BITES PROOF: one seeded-bad-buried fixture's
//        majority verdict is wrong (the judge missed the buried planted
//        error on a majority of its 5 samples) -> gate goes RED, recall
//        drops below 100%, and the miss is named ────────────────────────

test("(b) a missed seeded-bad-buried fixture (majority verdict wrong) fails the gate with recall < 100%", () => {
  const perSample = [
    ...samplesFor("why_PIATAF_good_verbatim", "good", 5),
    ...samplesFor("why_PCSF_seeded_bad_single", "seeded-bad-single", 5),
    // The acceptance crux: only 2/5 samples caught the buried error (a
    // judge that mostly skims past a claim buried mid-list) — 2 < the
    // MIN_SAMPLES_FOR_MAJORITY (3) threshold, so the majority verdict for
    // this fixture is WRONG: it reads as "entailed" when it should read
    // "contradicted".
    ...samplesFor("why_PSTIF_seeded_bad_buried", "seeded-bad-buried", 2),
  ];
  const verdicts = computeMajorityVerdicts(perSample);
  const metrics = computeGateMetrics(verdicts);

  assert.ok(metrics.recall < 1, `expected recall < 100%, got ${metrics.recall}`);
  assert.deepEqual(metrics.recallMisses, ["why_PSTIF_seeded_bad_buried"]);
  assert.deepEqual(metrics.precisionMisses, [], "precision side should be untouched by a recall miss");
  assert.equal(metrics.precision, 1);
  assert.equal(metrics.gatePass, false, "the gate must go RED when a seeded-bad-buried fixture is missed");
});

test("(b2) exactly at the majority boundary: 3/5 passing catches the error, 2/5 does not", () => {
  const caught = computeGateMetrics(
    computeMajorityVerdicts(samplesFor("buried_x", "seeded-bad-buried", MIN_SAMPLES_FOR_MAJORITY))
  );
  assert.equal(caught.recall, 1);

  const missed = computeGateMetrics(
    computeMajorityVerdicts(samplesFor("buried_x", "seeded-bad-buried", MIN_SAMPLES_FOR_MAJORITY - 1))
  );
  assert.equal(missed.recall, 0);
});

// ── A false positive on a `good` fixture also fails the gate (precision
//    side), independent of the recall side ────────────────────────────────

test("a good fixture failing majority vote fails the gate on precision, not recall", () => {
  const perSample = [
    ...samplesFor("why_PCSF_seeded_bad_single", "seeded-bad-single", 5),
    ...samplesFor("why_PIATAF_good_verbatim", "good", 1), // judge false-positives on correct prose
  ];
  const metrics = computeGateMetrics(computeMajorityVerdicts(perSample));

  assert.equal(metrics.recall, 1);
  assert.ok(metrics.precision < 1);
  assert.deepEqual(metrics.precisionMisses, ["why_PIATAF_good_verbatim"]);
  assert.equal(metrics.gatePass, false);
});

// ── computeMajorityVerdicts: structural guards ─────────────────────────────

test("computeMajorityVerdicts groups by fixture_id, NOT slot_key (slot_key repeats across fixtures)", () => {
  // why.PCSF is intentionally both a `good` and a `seeded-bad-single`
  // fixture in the real corpus (see fixtures/README.md) — this proves
  // gate.js does not collapse them into one bucket.
  const perSample = [
    ...samplesFor("why_PCSF_good_derived", "good", 5),
    ...samplesFor("why_PCSF_seeded_bad_single", "seeded-bad-single", 5),
  ];
  const verdicts = computeMajorityVerdicts(perSample);
  assert.equal(verdicts.length, 2);
  assert.deepEqual(
    verdicts.map((v) => v.fixture_id).sort(),
    ["why_PCSF_good_derived", "why_PCSF_seeded_bad_single"]
  );
});

test("computeMajorityVerdicts throws on a fixture_id with inconsistent category across samples", () => {
  const perSample = [
    { fixture_id: "x", category: "good", pass: true },
    { fixture_id: "x", category: "seeded-bad-single", pass: false },
  ];
  assert.throws(() => computeMajorityVerdicts(perSample), /inconsistent category/);
});

test("computeMajorityVerdicts throws on an empty input rather than silently reporting a green gate", () => {
  assert.throws(() => computeMajorityVerdicts([]), /no per-sample results/);
});

test("computeGateMetrics throws on an empty verdict list", () => {
  assert.throws(() => computeGateMetrics([]), /no fixtures to grade/);
});

// ── extractPerSampleResults: adapts a realistic Promptfoo --output shape ──

test("extractPerSampleResults reads a realistic EvaluateSummaryV3-shaped results.json", () => {
  // Mirrors `interface OutputFile { results: EvaluateSummaryV3 | EvaluateSummaryV2 }`
  // and `interface EvaluateResult` from promptfoo's index.d.ts closely enough
  // to exercise the adapter without needing a live promptfoo run.
  const outputFile = {
    evalId: "eval-abc123",
    results: {
      version: 3,
      timestamp: "2026-07-07T00:00:00.000Z",
      results: [
        {
          description: "good: why.PIATAF (why_PIATAF_good_verbatim.json)",
          testIdx: 0,
          promptIdx: 0,
          vars: { slot_key: "why.PIATAF", category: "good", fixture_id: "why_PIATAF_good_verbatim" },
          success: true,
          score: 1,
          gradingResult: { pass: true, score: 1, reason: "ok" },
        },
        {
          description: "seeded-bad-buried: why.PSTIF (why_PSTIF_seeded_bad_buried.json)",
          testIdx: 1,
          promptIdx: 0,
          vars: { slot_key: "why.PSTIF", category: "seeded-bad-buried", fixture_id: "why_PSTIF_seeded_bad_buried" },
          success: false,
          score: 0,
          gradingResult: { pass: false, score: 0, reason: "missed the buried claim" },
        },
      ],
      stats: { successes: 1, failures: 1, errors: 0, tokenUsage: {} },
    },
    config: {},
    shareableUrl: null,
  };

  const perSample = extractPerSampleResults(outputFile);
  assert.equal(perSample.length, 2);
  assert.deepEqual(perSample[0], { fixture_id: "why_PIATAF_good_verbatim", category: "good", pass: true });
  assert.deepEqual(perSample[1], {
    fixture_id: "why_PSTIF_seeded_bad_buried",
    category: "seeded-bad-buried",
    pass: false,
  });
});

test("extractPerSampleResults falls back to gradingResult.pass when success is absent", () => {
  const outputFile = {
    results: {
      results: [
        {
          vars: { category: "good", fixture_id: "f1" },
          gradingResult: { pass: true },
        },
      ],
    },
  };
  const perSample = extractPerSampleResults(outputFile);
  assert.equal(perSample[0].pass, true);
});

test("extractPerSampleResults throws on a result missing vars.fixture_id", () => {
  const outputFile = { results: { results: [{ vars: { category: "good" }, success: true }] } };
  assert.throws(() => extractPerSampleResults(outputFile), /vars\.fixture_id/);
});

test("extractPerSampleResults throws when no EvaluateResult[] array is found at all", () => {
  assert.throws(() => extractPerSampleResults({ results: {} }), /unexpected `promptfoo eval --output` shape/);
});

// ── formatReport: prints BOTH recall and precision, not just pass/fail ────

test("formatReport prints both recall and precision figures", () => {
  const metrics = computeGateMetrics(computeMajorityVerdicts(baselineAllCorrectCorpus()));
  const report = formatReport(metrics, []);
  assert.match(report, /recall/i);
  assert.match(report, /precision/i);
  assert.match(report, /100\.0%/);
  assert.match(report, /Gate: PASS/);
});

test("formatReport surfaces INCOMPLETE fixtures (fewer than EXPECTED_REPEAT samples) and forces the gate red", () => {
  const metrics = computeGateMetrics(computeMajorityVerdicts(baselineAllCorrectCorpus()));
  const shortGroups = [{ fixture_id: "why_PSTIF_seeded_bad_buried", total: 3 }];
  const report = formatReport(metrics, shortGroups);
  assert.match(report, /INCOMPLETE/);
  assert.match(report, /Gate: FAIL/);
});

// ── runGate: end-to-end over a real temp results.json file ────────────────

test("runGate reads a results.json file from disk and returns a green gate for an all-correct run", () => {
  const tmpFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "gate-test-")), "results.json");
  const outputFile = {
    results: {
      results: [
        ...Array.from({ length: 5 }, () => ({
          vars: { category: "good", fixture_id: "g1" },
          success: true,
        })),
        ...Array.from({ length: 5 }, () => ({
          vars: { category: "seeded-bad-single", fixture_id: "b1" },
          success: true,
        })),
      ],
    },
  };
  fs.writeFileSync(tmpFile, JSON.stringify(outputFile));

  const { gatePass, metrics, shortGroups } = runGate(tmpFile);
  assert.equal(gatePass, true);
  assert.equal(metrics.recall, 1);
  assert.equal(metrics.precision, 1);
  assert.deepEqual(shortGroups, []);
});

test("runGate fails closed when a fixture has fewer than EXPECTED_REPEAT samples (a dropped repeat)", () => {
  const tmpFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "gate-test-")), "results.json");
  const outputFile = {
    results: {
      results: [
        // Only 3 of the expected 5 repeats present for this fixture.
        ...Array.from({ length: 3 }, () => ({
          vars: { category: "good", fixture_id: "g1" },
          success: true,
        })),
        // A complete seeded-bad-* bucket, so this test isolates the
        // short-sample-count path from the (separately tested) empty-bucket
        // fail-closed guard.
        ...Array.from({ length: 5 }, () => ({
          vars: { category: "seeded-bad-single", fixture_id: "b1" },
          success: true,
        })),
      ],
    },
  };
  fs.writeFileSync(tmpFile, JSON.stringify(outputFile));

  const { gatePass, shortGroups } = runGate(tmpFile);
  assert.equal(gatePass, false, "an incomplete sample set must not silently pass the gate");
  assert.equal(shortGroups.length, 1);
  assert.equal(shortGroups[0].fixture_id, "g1");
});

test("runGate throws (fails closed) when the results.json file does not exist", () => {
  assert.throws(() => runGate("/nonexistent/path/results.json"));
});

// ── Fail-closed hardening: an empty bucket or an unrecognized category must
//    never produce a vacuous green gate ────────────────────────────────────

test("runGate fails closed when the seeded-bad-* bucket is empty (only good fixtures present)", () => {
  const tmpFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "gate-test-")), "results.json");
  const outputFile = {
    results: {
      results: Array.from({ length: 5 }, () => ({
        vars: { category: "good", fixture_id: "g1" },
        success: true,
      })),
    },
  };
  fs.writeFileSync(tmpFile, JSON.stringify(outputFile));

  // Without the seeded-bad-* bucket, computeGateMetrics would report a
  // vacuous 100% recall over 0 fixtures — runGate must reject that instead
  // of letting it read as a real green.
  assert.throws(() => runGate(tmpFile), /seeded-bad-\* bucket is empty/);
});

test("runGate fails closed when a result carries an unrecognized category value", () => {
  const tmpFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "gate-test-")), "results.json");
  const outputFile = {
    results: {
      results: [
        ...Array.from({ length: 5 }, () => ({
          vars: { category: "good", fixture_id: "g1" },
          success: true,
        })),
        ...Array.from({ length: 5 }, () => ({
          vars: { category: "seeded-bad-single", fixture_id: "b1" },
          success: true,
        })),
        // A typo'd/unwired category — matches neither the "good" nor the
        // "seeded-bad-*" filter in computeGateMetrics, so it would silently
        // vanish from both denominators if runGate did not police it.
        ...Array.from({ length: 5 }, () => ({
          vars: { category: "seeded-vad-single", fixture_id: "typo1" },
          success: false,
        })),
      ],
    },
  };
  fs.writeFileSync(tmpFile, JSON.stringify(outputFile));

  assert.throws(() => runGate(tmpFile), /unrecognized category/);
});
