"use strict";
/**
 * Reduction + assertion logic for the prose-number entailment eval's judge.
 *
 * This module is deliberately separated from `promptfooconfig.yaml` so the
 * buried-error reduction can be unit-tested with hand-written MOCK judge
 * outputs, with no model API call and no `ANTHROPIC_API_KEY` (see
 * `assert.test.js`). Promptfoo's `javascript` assertion loads this file via
 * `value: file://assert.js` (no `:functionName` suffix), which requires
 * `module.exports` to itself be the callable `(output, context) => GradingResult`
 * entry point — see `loadFromJavaScriptFile` in promptfoo's evaluator, which
 * falls through to `typeof requiredModule === "function"` when no function
 * name is given. The individual pieces (`parseJudgeOutput`, `reduceClaims`,
 * `gradeJudgeOutput`) are attached as properties of that same function export
 * so both promptfoo and `assert.test.js` can reach them from one `require()`.
 *
 * ── The reduction is the structural mitigation (design spec §6.3/§7) ──
 * The judge is asked to also emit its own top-level `entailed` boolean, but
 * this module NEVER trusts that field for the pass/fail decision — `entailed`
 * is always recomputed here from the per-claim `claims` list. That is the
 * whole point of the per-claim-list output contract: even if the judge's own
 * holistic boolean is wrong (e.g. it rubber-stamps `entailed: true` after
 * only skimming the first claim), a single `contradicted`/`underivable` verdict
 * anywhere in `claims` still fails the reduction in code, deterministically.
 */

const VALID_VERDICTS = new Set(["entailed", "contradicted", "underivable"]);

/**
 * Parses a judge's raw text response into the per-claim JSON contract.
 *
 * Tolerant of the judge wrapping the JSON in a ```json ... ``` fence despite
 * being told not to (models do this often enough that failing hard on it
 * would make the eval flaky for a cosmetic reason, not a judging failure).
 * Anything else that isn't valid, parseable JSON is a genuine judge failure
 * and is left to throw.
 *
 * @param {string} raw - The judge model's raw text output.
 * @returns {{claims: Array<{text: string, verdict: string}>, entailed: boolean, offending_sentence: string|null}}
 * @throws {Error} if `raw` cannot be parsed as JSON at all.
 */
function parseJudgeOutput(raw) {
  if (typeof raw !== "string") {
    throw new Error(`judge output must be a string, got ${typeof raw}`);
  }
  let text = raw.trim();
  // Strip a ```json ... ``` or ``` ... ``` fence if the judge added one
  // despite the "return ONLY this JSON" instruction.
  const fenced = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  if (fenced) {
    text = fenced[1].trim();
  }
  // If there's stray text around a JSON object (rare, but seen in the wild),
  // fall back to the first {...} span rather than failing outright.
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    const firstBrace = text.indexOf("{");
    const lastBrace = text.lastIndexOf("}");
    if (firstBrace === -1 || lastBrace === -1 || lastBrace <= firstBrace) {
      throw new Error(`judge output is not valid JSON: ${err.message}`);
    }
    parsed = JSON.parse(text.slice(firstBrace, lastBrace + 1));
  }
  return parsed;
}

/**
 * Validates the parsed judge output against the per-claim contract's shape
 * (not its verdict content — that's `reduceClaims`'s job).
 *
 * @param {unknown} parsed
 * @returns {{ok: boolean, reason?: string}}
 */
function validateContractShape(parsed) {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { ok: false, reason: "judge output is not a JSON object" };
  }
  if (!Array.isArray(parsed.claims)) {
    return { ok: false, reason: "judge output is missing a `claims` array" };
  }
  for (const [i, claim] of parsed.claims.entries()) {
    if (!claim || typeof claim !== "object") {
      return { ok: false, reason: `claims[${i}] is not an object` };
    }
    if (typeof claim.text !== "string" || !claim.text.trim()) {
      return { ok: false, reason: `claims[${i}].text is missing or empty` };
    }
    if (!VALID_VERDICTS.has(claim.verdict)) {
      return {
        ok: false,
        reason: `claims[${i}].verdict=${JSON.stringify(claim.verdict)} is not one of entailed/contradicted/underivable`,
      };
    }
  }
  return { ok: true };
}

/**
 * The reduction: slot-level `entailed` is true iff every claim's own verdict
 * is "entailed"; false if any claim is "contradicted" or "underivable".
 *
 * Fails CLOSED on an empty claims list. Every fixture's prose in this corpus
 * contains at least one numeric claim by construction (see
 * `evals/prose_numbers/fixtures/README.md`), so a judge returning zero claims
 * for such prose is a judge/parsing failure, not a legitimate "nothing to
 * check" case — treating it as entailed would silently pass a broken judge
 * call.
 *
 * @param {Array<{text: string, verdict: string}>} claims
 * @returns {{entailed: boolean, failingClaim: {text: string, verdict: string}|null}}
 */
function reduceClaims(claims) {
  if (!Array.isArray(claims) || claims.length === 0) {
    return { entailed: false, failingClaim: null };
  }
  const failingClaim = claims.find(
    (c) => c && (c.verdict === "contradicted" || c.verdict === "underivable")
  );
  return { entailed: !failingClaim, failingClaim: failingClaim || null };
}

/**
 * Strips HTML tags and normalizes whitespace/case for a fuzzy, tag-agnostic
 * sentence comparison (fixtures embed `<strong>` markup; the judge may or may
 * not echo the tags back verbatim).
 *
 * @param {string} s
 * @returns {string}
 */
function normalizeSentence(s) {
  return String(s || "")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/**
 * Bonus (non-gating) check: does the judge's flagged offending sentence
 * plausibly correspond to the fixture's known planted offending sentence?
 * Containment either direction (after tag/whitespace/case normalization)
 * covers both "judge quoted the whole sentence" and "judge quoted only the
 * clause carrying the number".
 *
 * @param {string|null|undefined} judgeOffending
 * @param {string|null|undefined} fixtureOffending
 * @returns {boolean}
 */
function plantedClaimIsFlagged(judgeOffending, fixtureOffending) {
  const a = normalizeSentence(judgeOffending);
  const b = normalizeSentence(fixtureOffending);
  if (!a || !b) return false;
  return a.includes(b) || b.includes(a);
}

/**
 * The full grading pipeline: parse -> validate shape -> reduce -> assert
 * against the fixture's expected verdict. Returns a promptfoo GradingResult
 * shape (`{pass, score, reason, componentResults, metadata}`) regardless of
 * which stage failed, so a malformed judge response is a clean assertion
 * failure rather than an uncaught exception.
 *
 * @param {string} rawOutput - The judge model's raw text response.
 * @param {{expect: string, category: string, offending_sentence: string|null, slot_key?: string}} fixtureVars
 * @returns {{pass: boolean, score: number, reason: string, componentResults: Array, metadata: object}}
 */
function gradeJudgeOutput(rawOutput, fixtureVars) {
  const expectEntailed = fixtureVars.expect === "entailed";
  const category = fixtureVars.category;
  const fixtureOffending = fixtureVars.offending_sentence || null;

  let parsed;
  try {
    parsed = parseJudgeOutput(rawOutput);
  } catch (err) {
    return {
      pass: false,
      score: 0,
      reason: `judge output did not parse as JSON: ${err.message}`,
      componentResults: [],
      metadata: { slot_key: fixtureVars.slot_key, category, parseError: err.message },
    };
  }

  const shape = validateContractShape(parsed);
  if (!shape.ok) {
    return {
      pass: false,
      score: 0,
      reason: `judge output violated the per-claim JSON contract: ${shape.reason}`,
      componentResults: [],
      metadata: { slot_key: fixtureVars.slot_key, category, contractError: shape.reason },
    };
  }

  const { entailed: reducedEntailed, failingClaim } = reduceClaims(parsed.claims);

  const componentResults = [];

  const entailedMatches = reducedEntailed === expectEntailed;
  componentResults.push({
    pass: entailedMatches,
    score: entailedMatches ? 1 : 0,
    reason: `reduced entailed=${reducedEntailed} (from ${parsed.claims.length} claim(s)), expected=${expectEntailed}`,
  });

  // For seeded-bad-* fixtures, the reduction must have actually flagged a
  // failing claim, and the judge must have surfaced a non-null
  // offending_sentence (part of the output contract, not just the reduction).
  let offendingSentenceOk = true;
  if (!expectEntailed) {
    const hasFailingClaim = !!failingClaim;
    const hasOffendingSentence =
      typeof parsed.offending_sentence === "string" && parsed.offending_sentence.trim().length > 0;
    offendingSentenceOk = hasFailingClaim && hasOffendingSentence;
    componentResults.push({
      pass: offendingSentenceOk,
      score: offendingSentenceOk ? 1 : 0,
      reason: offendingSentenceOk
        ? "a failing claim was flagged and offending_sentence is non-null"
        : `expected a flagged failing claim + non-null offending_sentence (failingClaim=${JSON.stringify(
            failingClaim
          )}, offending_sentence=${JSON.stringify(parsed.offending_sentence)})`,
    });
  }

  // Bonus, NON-GATING: does the flagged sentence match the specific planted
  // error (not just "some claim failed")? Recorded in metadata/reason for
  // visibility; deliberately does not affect `pass` per the task brief
  // ("bonus: that the planted claim is the one flagged").
  let plantedClaimFlagged = null;
  if (!expectEntailed && fixtureOffending) {
    plantedClaimFlagged = plantedClaimIsFlagged(parsed.offending_sentence, fixtureOffending);
  }

  const pass = entailedMatches && offendingSentenceOk;
  const reasonParts = componentResults.map((c) => c.reason);
  if (plantedClaimFlagged !== null) {
    reasonParts.push(
      plantedClaimFlagged
        ? "(bonus) planted claim matched the flagged offending_sentence"
        : "(bonus, non-gating) flagged offending_sentence did not match the planted claim's sentence"
    );
  }

  return {
    pass,
    score: pass ? 1 : 0,
    reason: reasonParts.join(" | "),
    componentResults,
    metadata: {
      slot_key: fixtureVars.slot_key,
      category,
      reducedEntailed,
      failingClaim,
      plantedClaimFlagged,
      claims: parsed.claims,
    },
  };
}

/**
 * Promptfoo `javascript` assertion entry point: `(output, context) => GradingResult`.
 * `context.vars` carries the fixture's own fields (`expect`, `category`,
 * `offending_sentence`, `slot_key`) because the test-case loader
 * (`tests/load-fixtures.js`) puts them there verbatim from the frozen fixture
 * JSON — see that file for the 1:1 fixture-to-test-case mapping.
 *
 * @param {string} output
 * @param {{vars: Record<string, unknown>}} context
 * @returns {{pass: boolean, score: number, reason: string, componentResults: Array, metadata: object}}
 */
function assertProseNumberEntailment(output, context) {
  const vars = (context && context.vars) || {};
  return gradeJudgeOutput(output, vars);
}

module.exports = assertProseNumberEntailment;
module.exports.parseJudgeOutput = parseJudgeOutput;
module.exports.validateContractShape = validateContractShape;
module.exports.reduceClaims = reduceClaims;
module.exports.normalizeSentence = normalizeSentence;
module.exports.plantedClaimIsFlagged = plantedClaimIsFlagged;
module.exports.gradeJudgeOutput = gradeJudgeOutput;
