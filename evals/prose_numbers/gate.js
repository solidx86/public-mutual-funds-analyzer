"use strict";
/**
 * CI gate for the prose-number entailment eval (Phase 4).
 *
 * Consumes Promptfoo's `--output results.json` (an `OutputFile` whose
 * `results.results` is an `EvaluateResult[]` — see
 * `node_modules/promptfoo/dist/src/index.d.ts`, `interface EvaluateResult`)
 * and applies the majority-vote-of-N aggregation rule stated in
 * `promptfooconfig.yaml`'s header comment and `README.md`:
 *
 *   N = 5 (the config's `repeat: 5`)
 *   A fixture's majority verdict is CORRECT iff >= 3 of its 5 repeat
 *   samples pass their per-sample assertion (`assert.js`, which already
 *   reduces the judge's per-claim JSON against the fixture's `expect`).
 *
 * The gate itself is green ONLY when, across all fixtures under majority
 * vote:
 *   - recall on `seeded-bad-*` fixtures (the judge catches every planted
 *     error) is 100%
 *   - precision on `good` fixtures (the judge never false-positives on
 *     correct prose) is 100%
 *
 * `computeMajorityVerdicts` / `computeGateMetrics` are pure functions
 * operating on a normalized `{fixture_id, category, pass}[]` shape so the
 * aggregation/threshold logic can be unit-tested offline with synthetic
 * data (see `gate.test.js`) with no model API call and no real Promptfoo
 * run. `extractPerSampleResults` is the (thin, separately-testable) adapter
 * from Promptfoo's actual output JSON to that normalized shape.
 *
 * Grouping key: `vars.fixture_id`, NOT `vars.slot_key`. `slot_key` is
 * deliberately reused across fixtures (e.g. `why.PCSF` is both a `good` and
 * a `seeded-bad-single` fixture — see `fixtures/README.md`), so it cannot
 * disambiguate one fixture's 5 repeats from another's. `fixture_id` (the
 * frozen fixture file's basename minus `.json`) is unique by construction
 * and is threaded into `vars` by `tests/load-fixtures.js`.
 */

const fs = require("node:fs");

// Aggregation rule constants — keep these in lockstep with the `repeat: 5`
// comment in promptfooconfig.yaml and the "majority-of-5" language in
// README.md. If either N changes, update all three together.
const EXPECTED_REPEAT = 5;
const MIN_SAMPLES_FOR_MAJORITY = 3; // >= 3 of 5 samples passing = majority.

// Category values this gate understands. `computeGateMetrics` buckets
// verdicts by `category.startsWith("seeded-bad-")` / `=== "good"`; a typo'd
// or otherwise unrecognized category value matches neither filter and would
// silently vanish from both the recall and precision denominators. `runGate`
// enforces every verdict's category is one of these before trusting the
// metrics, so an unrecognized category fails closed instead of being dropped.
const RECOGNIZED_CATEGORIES = ["good", "seeded-bad-single", "seeded-bad-buried"];

/**
 * Groups per-sample pass/fail results by fixture and computes each
 * fixture's majority verdict.
 *
 * @param {Array<{fixture_id: string, category: string, pass: boolean}>} perSampleResults
 * @returns {Array<{fixture_id: string, category: string, passCount: number, total: number, majorityPass: boolean}>}
 */
function computeMajorityVerdicts(perSampleResults) {
  if (!Array.isArray(perSampleResults) || perSampleResults.length === 0) {
    throw new Error("computeMajorityVerdicts: no per-sample results to grade");
  }

  const groups = new Map();
  for (const [i, r] of perSampleResults.entries()) {
    if (!r || typeof r.fixture_id !== "string" || !r.fixture_id) {
      throw new Error(`perSampleResults[${i}] is missing a non-empty fixture_id`);
    }
    if (typeof r.category !== "string" || !r.category) {
      throw new Error(`perSampleResults[${i}] (fixture_id=${r.fixture_id}) is missing a category`);
    }
    if (typeof r.pass !== "boolean") {
      throw new Error(`perSampleResults[${i}] (fixture_id=${r.fixture_id}) has a non-boolean pass value`);
    }

    if (!groups.has(r.fixture_id)) {
      groups.set(r.fixture_id, { fixture_id: r.fixture_id, category: r.category, passCount: 0, total: 0 });
    }
    const g = groups.get(r.fixture_id);
    if (g.category !== r.category) {
      // Every sample of the same fixture_id must come from the same frozen
      // fixture, so its category cannot legitimately vary sample-to-sample.
      throw new Error(
        `fixture_id=${r.fixture_id} has inconsistent category across samples: "${g.category}" vs "${r.category}"`
      );
    }
    g.total += 1;
    if (r.pass) g.passCount += 1;
  }

  return [...groups.values()]
    .map((g) => ({ ...g, majorityPass: g.passCount >= MIN_SAMPLES_FOR_MAJORITY }))
    .sort((a, b) => a.fixture_id.localeCompare(b.fixture_id));
}

/**
 * Computes recall (over `seeded-bad-*` fixtures) and precision (over `good`
 * fixtures) from majority verdicts, plus the overall gate pass/fail.
 *
 * Recall/precision are reported even when the relevant fixture set is
 * empty (defaulting to 1 = vacuously satisfied) so this function never
 * crashes on a partial fixture set — it is `runGate`'s job, not this pure
 * function's, to police that `badTotal`/`goodTotal` are non-zero before
 * trusting the resulting metrics as a real green.
 *
 * @param {Array<{fixture_id: string, category: string, majorityPass: boolean}>} majorityVerdicts
 * @returns {{recall: number, precision: number, badTotal: number, badCaught: number, goodTotal: number, goodPassed: number, recallMisses: string[], precisionMisses: string[], gatePass: boolean}}
 */
function computeGateMetrics(majorityVerdicts) {
  if (!Array.isArray(majorityVerdicts) || majorityVerdicts.length === 0) {
    throw new Error("computeGateMetrics: no fixtures to grade");
  }

  const badFixtures = majorityVerdicts.filter((v) => v.category.startsWith("seeded-bad-"));
  const goodFixtures = majorityVerdicts.filter((v) => v.category === "good");

  const badCaught = badFixtures.filter((v) => v.majorityPass).length;
  const goodPassed = goodFixtures.filter((v) => v.majorityPass).length;

  const recall = badFixtures.length === 0 ? 1 : badCaught / badFixtures.length;
  const precision = goodFixtures.length === 0 ? 1 : goodPassed / goodFixtures.length;

  return {
    recall,
    precision,
    badTotal: badFixtures.length,
    badCaught,
    goodTotal: goodFixtures.length,
    goodPassed,
    recallMisses: badFixtures.filter((v) => !v.majorityPass).map((v) => v.fixture_id),
    precisionMisses: goodFixtures.filter((v) => !v.majorityPass).map((v) => v.fixture_id),
    // 100%/100% under majority vote — the CI threshold stated in the design
    // spec §6.4/§11 and the task brief: any miss on either side fails.
    gatePass: recall === 1 && precision === 1,
  };
}

/**
 * Adapts Promptfoo's `--output results.json` (`OutputFile`) into the
 * normalized `{fixture_id, category, pass}[]` shape the pure aggregation
 * functions above consume.
 *
 * Tolerant of both `EvaluateSummaryV3` (`outputFile.results.results`) and a
 * bare `EvaluateResult[]` (`outputFile.results`), since Promptfoo's output
 * schema has changed version-to-version; fails loudly (not silently) if
 * neither shape is found, or if a result is missing the fields this gate
 * depends on.
 *
 * @param {object} outputFile - Parsed JSON from `promptfoo eval --output results.json`.
 * @returns {Array<{fixture_id: string, category: string, pass: boolean}>}
 */
function extractPerSampleResults(outputFile) {
  const nested = outputFile && outputFile.results && outputFile.results.results;
  const flat = outputFile && Array.isArray(outputFile.results) ? outputFile.results : null;
  const evalResults = Array.isArray(nested) ? nested : flat;

  if (!Array.isArray(evalResults)) {
    throw new Error(
      "could not find an EvaluateResult[] array at outputFile.results.results (or outputFile.results) — unexpected `promptfoo eval --output` shape"
    );
  }

  return evalResults.map((r, i) => {
    const vars = (r && r.vars) || {};
    const fixtureId = vars.fixture_id;
    const category = vars.category;
    if (typeof fixtureId !== "string" || !fixtureId) {
      throw new Error(`results[${i}] is missing vars.fixture_id — is tests/load-fixtures.js emitting it?`);
    }
    if (typeof category !== "string" || !category) {
      throw new Error(`results[${i}] (fixture_id=${fixtureId}) is missing vars.category`);
    }
    // `success` is Promptfoo's own per-sample pass/fail (already the output
    // of assert.js's reduction for this one judge call); `gradingResult.pass`
    // is kept as a fallback for robustness across Promptfoo output-schema
    // versions.
    const pass = typeof r.success === "boolean" ? r.success : !!(r.gradingResult && r.gradingResult.pass);
    return { fixture_id: fixtureId, category, pass };
  });
}

/**
 * Formats the human-readable gate report printed in CI job output. Prints
 * BOTH recall and precision (not just the pass/fail bit) per the task
 * brief, so a regression in either direction is visible in the log.
 *
 * @param {ReturnType<typeof computeGateMetrics>} metrics
 * @param {Array<{fixture_id: string, total: number}>} shortGroups - fixtures without exactly EXPECTED_REPEAT samples.
 * @returns {string}
 */
function formatReport(metrics, shortGroups = []) {
  const pct = (x) => `${(x * 100).toFixed(1)}%`;
  const lines = [];
  lines.push("Prose-number eval — majority-of-5 CI gate");
  lines.push(
    `  recall (seeded-bad-* caught):  ${pct(metrics.recall)}  (${metrics.badCaught}/${metrics.badTotal})`
  );
  lines.push(
    `  precision (good passed):       ${pct(metrics.precision)}  (${metrics.goodPassed}/${metrics.goodTotal})`
  );
  if (metrics.recallMisses.length > 0) {
    lines.push(`  MISSED — planted error not caught by majority vote: ${metrics.recallMisses.join(", ")}`);
  }
  if (metrics.precisionMisses.length > 0) {
    lines.push(`  FALSE POSITIVE — good prose failed majority vote: ${metrics.precisionMisses.join(", ")}`);
  }
  if (shortGroups.length > 0) {
    lines.push(
      `  INCOMPLETE — expected ${EXPECTED_REPEAT} samples/fixture, got fewer for: ${shortGroups
        .map((g) => `${g.fixture_id}(${g.total})`)
        .join(", ")}`
    );
  }
  const gatePass = metrics.gatePass && shortGroups.length === 0;
  lines.push(
    `  Gate: ${gatePass ? "PASS" : "FAIL"} (requires recall=100% AND precision=100%, all fixtures complete)`
  );
  return lines.join("\n");
}

/**
 * Reads a Promptfoo `--output results.json` file and runs it through the
 * full gate pipeline (extract -> group -> aggregate -> metrics).
 *
 * @param {string} resultsJsonPath
 * @returns {{metrics: ReturnType<typeof computeGateMetrics>, verdicts: ReturnType<typeof computeMajorityVerdicts>, shortGroups: Array<{fixture_id: string, total: number}>, gatePass: boolean}}
 */
function runGate(resultsJsonPath) {
  const raw = fs.readFileSync(resultsJsonPath, "utf8");
  const outputFile = JSON.parse(raw);
  const perSample = extractPerSampleResults(outputFile);
  const verdicts = computeMajorityVerdicts(perSample);
  // A fixture with fewer than EXPECTED_REPEAT samples (e.g. a dropped
  // repeat from a provider error) means the majority vote itself is on
  // shaky ground — fail closed rather than silently voting on a partial
  // sample, mirroring assert.js's "fail closed on an empty claims list"
  // philosophy.
  const shortGroups = verdicts.filter((v) => v.total !== EXPECTED_REPEAT).map((v) => ({
    fixture_id: v.fixture_id,
    total: v.total,
  }));

  // Fail closed on a category value neither bucket recognizes (a typo, or a
  // fixture whose `category` was never wired through by
  // tests/load-fixtures.js) — otherwise it would silently drop out of BOTH
  // computeGateMetrics denominators and never be graded at all.
  const unrecognized = verdicts.filter((v) => !RECOGNIZED_CATEGORIES.includes(v.category));
  if (unrecognized.length > 0) {
    const names = unrecognized.map((v) => `${v.fixture_id}="${v.category}"`).join(", ");
    throw new Error(
      `::error::runGate: unrecognized category value(s), failing closed rather than dropping them from grading: ${names}`
    );
  }

  const metrics = computeGateMetrics(verdicts);

  // Fail closed if either bucket the gate's threshold depends on is empty —
  // recall=100%/precision=100% is otherwise vacuously true over zero
  // fixtures (see computeGateMetrics), which would print a green gate
  // having graded nothing on that side (a dropped category, a promptfoo
  // partial-output file, etc).
  if (metrics.badTotal === 0) {
    throw new Error(
      "::error::runGate: the seeded-bad-* bucket is empty — recall cannot be certified, failing closed"
    );
  }
  if (metrics.goodTotal === 0) {
    throw new Error("::error::runGate: the good bucket is empty — precision cannot be certified, failing closed");
  }

  return { metrics, verdicts, shortGroups, gatePass: metrics.gatePass && shortGroups.length === 0 };
}

if (require.main === module) {
  const resultsJsonPath = process.argv[2] || "results.json";
  try {
    const { metrics, shortGroups, gatePass } = runGate(resultsJsonPath);
    console.log(formatReport(metrics, shortGroups));
    process.exit(gatePass ? 0 : 1);
  } catch (err) {
    console.error(`gate.js failed: ${err.message}`);
    process.exit(1);
  }
}

module.exports = {
  EXPECTED_REPEAT,
  MIN_SAMPLES_FOR_MAJORITY,
  computeMajorityVerdicts,
  computeGateMetrics,
  extractPerSampleResults,
  formatReport,
  runGate,
};
