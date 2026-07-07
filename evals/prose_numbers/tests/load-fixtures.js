"use strict";
/**
 * Converts the 19 frozen fixture JSON files under `evals/prose_numbers/fixtures/`
 * into Promptfoo test cases — one fixture file, one test case, one judge call,
 * one slot instance (the 1:1 mapping is load-bearing; see the design spec's
 * §5 and the task brief's Global Constraints).
 *
 * Referenced from `promptfooconfig.yaml` as `tests: - file://tests/load-fixtures.js`.
 * Promptfoo's `readJavascriptTestCases` requires a JS test file to either
 * export a function (called with the resolved config) or export the test-case
 * array directly; this module exports the array directly since the fixture
 * set is static and needs no config-time parameterization.
 *
 * The fixtures themselves are NOT reshaped here beyond what's needed to fit
 * Promptfoo's `{vars, assert}` test-case shape — `figures` is pretty-printed
 * to a JSON string so `{{figures}}` renders as readable JSON in the judge
 * prompt (Nunjucks would otherwise stringify a raw object as `[object
 * Object]`). Every other fixture field passes through unmodified so the
 * frozen fixture JSON remains the single source of truth (see
 * `evals/prose_numbers/fixtures/README.md`).
 */

const fs = require("node:fs");
const path = require("node:path");

const FIXTURES_DIR = path.join(__dirname, "..", "fixtures");

function loadFixtureTestCases() {
  const files = fs
    .readdirSync(FIXTURES_DIR)
    .filter((f) => f.endsWith(".json"))
    .sort();

  if (files.length === 0) {
    throw new Error(`no fixture JSON files found under ${FIXTURES_DIR}`);
  }

  return files.map((file) => {
    const fullPath = path.join(FIXTURES_DIR, file);
    const fixture = JSON.parse(fs.readFileSync(fullPath, "utf8"));

    for (const key of ["slot_key", "figures", "prose", "expect", "category"]) {
      if (!(key in fixture)) {
        throw new Error(`fixture ${file} is missing required key "${key}"`);
      }
    }

    return {
      description: `${fixture.category}: ${fixture.slot_key} (${file})`,
      vars: {
        slot_key: fixture.slot_key,
        prose: fixture.prose,
        // Pretty-printed so the judge prompt's {{figures}} block renders as
        // readable JSON rather than "[object Object]".
        figures: JSON.stringify(fixture.figures, null, 2),
        // Pass-through fields the assertion (assert.js) reads from
        // context.vars to grade this test case against its own fixture.
        expect: fixture.expect,
        offending_sentence: fixture.offending_sentence,
        category: fixture.category,
      },
      assert: [
        {
          type: "javascript",
          value: "file://assert.js",
        },
      ],
    };
  });
}

module.exports = loadFixtureTestCases();
