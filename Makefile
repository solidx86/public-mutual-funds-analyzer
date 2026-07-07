.PHONY: eval-prose-numbers

# Prose-number entailment eval (ENH-10) — Promptfoo harness.
# See evals/prose_numbers/README.md for the API-key story and current phase status.
eval-prose-numbers:
	cd evals/prose_numbers && npx promptfoo eval -c promptfooconfig.yaml
