"""Evaluation-support code that is coupled to the engine internals.

Currently just ``figures_extractor``. The language-agnostic prose-number eval
harness (fixtures, judge prompt, Promptfoo config) lives under the repo-root
``evals/prose_numbers/`` directory instead — the two are joined only by the
frozen fixture JSON, never by a Python import.
"""
