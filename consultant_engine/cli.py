"""Command-line entry point for the consultant engine.

Parses arguments, opens the SQLite checkpointer, builds the graph, and invokes it
— either starting a fresh run from a profile + FundMaster or resuming a paused run
with ``--resume``. See ``python -m consultant_engine --help`` for the full flag and
profile-field reference.
"""

import argparse, json, re, sqlite3, sys
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from consultant_engine import __version__
from consultant_engine.graph import build_graph

# PublicMutual_FundMaster_<Mon><YYYY>_v<major>.<minor>.xlsx
_FM_RE = re.compile(r"PublicMutual_FundMaster_([A-Za-z]{3})(\d{4})_v(\d+)\.(\d+)\.xlsx$")
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def _fm_sort_key(name: str):
    """(year, month, major, minor) for a FundMaster filename, or None if it doesn't match."""
    m = _FM_RE.search(name)
    if not m:
        return None
    mon, year, major, minor = m.groups()
    return (int(year), _MONTHS.get(mon, 0), int(major), int(minor))


def _latest_fundmaster(search_dirs=None) -> str:
    """Resolve the newest FundMaster workbook when --fundmaster is omitted.

    Searches the live screener output dir first (the canonical target, a private-repo
    symlink on real installs), then the tracked public examples. The first directory
    that contains any FundMaster wins; within it, 'newest' = max by (year, month,
    version) parsed from the filename. Raises SystemExit if none is found.
    """
    root = Path(__file__).resolve().parent.parent
    dirs = search_dirs or [root / "output" / "fundmasters",
                           root / "output" / "examples" / "fundmasters"]
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        cands = [(k, p) for p in d.glob("PublicMutual_FundMaster_*.xlsx")
                 if (k := _fm_sort_key(p.name)) is not None]
        if cands:
            return str(max(cands, key=lambda kp: kp[0])[1])
    raise SystemExit(
        "No --fundmaster given and no PublicMutual_FundMaster_*.xlsx found under "
        "output/fundmasters/ or output/examples/fundmasters/."
    )


def _thread_id(args) -> str:
    """Checkpoint thread id: the --resume value, else the profile filename stem."""
    if args.resume:
        return args.resume
    stem = Path(args.profile).stem
    return f"{stem}"


_DESCRIPTION = """\
Generate an HTML investment proposal for a Public Mutual unit-trust client.

Reads a client risk profile (JSON) and a screened FundMaster workbook (.xlsx),
runs the consulting pipeline (CFS scoring -> macro context -> portfolio build ->
proposal draft), and writes a formatted HTML proposal into the output directory.

Review gate (default): the engine pauses after drafting, writes
data/review/<thread_id>.json plus a preview .html, and exits. Edit that JSON,
then re-run with --resume <thread_id> to finish. Pass --no-review to skip the
gate for evals, CI, or batch runs.
"""

_EPILOG = """\
examples:
  # Quickstart: bundled example profile, newest FundMaster, review gate on
  python -m consultant_engine --profile data/profiles/moderate.json

  # Finish a paused run after editing data/review/moderate.json
  python -m consultant_engine --resume moderate

  # One-shot, skip the review gate (CI / batch)
  python -m consultant_engine --profile data/profiles/aggressive.json --no-review

  # Fast offline run — stub every LLM call
  CONSULTANT_ENGINE_FAKE_LLM=1 \\
      python -m consultant_engine --profile data/profiles/moderate.json --no-review

profile JSON fields (see data/profiles/*.json for full examples):
  risk_level          Conservative | Moderate | Moderately Aggressive | Aggressive
  shariah             true | false | null   (null = no Shariah preference)
  experience          "new" | "experienced"  (tunes how much is explained)
  upfront_capital_rm  initial investable amount, in RM
  target_annual_return_pct            target expected annual return, in % p.a. (e.g. 5.0)
  goals               free-text client objective (optional)

thread_id: derived from the profile filename stem (moderate.json -> "moderate").
It names the review JSON and is the value you pass to --resume.
"""


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser (grouped flags, rich help text, --version)."""
    ap = argparse.ArgumentParser(
        prog="consultant_engine",
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    inp = ap.add_argument_group("inputs")
    inp.add_argument(
        "--profile", metavar="FILE",
        help="Client risk-profile JSON (fields listed below). Required unless "
             "--resume is given. Bundled examples live in data/profiles/.")
    inp.add_argument(
        "--fundmaster", metavar="FILE",
        help="Screened FundMaster workbook (.xlsx). Optional — defaults to the "
             "newest PublicMutual_FundMaster_*.xlsx under output/fundmasters/ "
             "(else output/examples/fundmasters/).")
    inp.add_argument(
        "--macro", metavar="SOURCE", default="none",
        help="Macro-context source tag (default: none). Informational — macro "
             "events are loaded from the bundled fixture.")

    out = ap.add_argument_group("output")
    out.add_argument(
        "-o", "--output", metavar="DIR", default="output/fund_proposals",
        help="Directory for the generated proposal "
             "(default: output/fund_proposals).")

    rev = ap.add_argument_group("review workflow")
    rev.add_argument(
        "--no-review", action="store_true",
        help="Skip the human review gate and write the final proposal in one pass.")
    rev.add_argument(
        "--resume", metavar="THREAD_ID",
        help="Resume a paused run after editing data/review/<THREAD_ID>.json. "
             "THREAD_ID is the profile filename stem (e.g. 'moderate').")

    mdl = ap.add_argument_group("model")
    mdl.add_argument(
        "--model", metavar="NAME", default="claude-sonnet-4-6",
        help="LLM for narrative slots (default: claude-sonnet-4-6). Set "
             "CONSULTANT_ENGINE_FAKE_LLM=1 to stub all LLM calls for offline runs.")

    ap.add_argument("--version", action="version",
                    version=f"%(prog)s {__version__}")
    return ap


def main(argv=None) -> int:
    """Run the CLI: parse args, build the graph, invoke it, and report the outcome.

    Starts a fresh run (profile + FundMaster) or resumes a paused one. Prints the
    review-gate instructions when the run pauses, else the output proposal path.

    Returns:
        Process exit code (0 on success / clean pause).
    """
    ap = _build_parser()
    args = ap.parse_args(argv)
    if not args.resume and not args.profile:
        ap.error("--profile is required unless you pass --resume <thread_id>")

    Path("data/review").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect("data/review/checkpoints.sqlite", check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()  # ensure checkpoint tables exist
    app = build_graph(saver)
    cfg = {"configurable": {"thread_id": _thread_id(args)}}

    if args.resume:
        from langgraph.types import Command
        from consultant_engine.nodes.review_gate import read_resume_payload
        out = app.invoke(Command(resume=read_resume_payload(args.resume)), cfg)
    else:
        profile = json.loads(Path(args.profile).read_text())
        fundmaster = args.fundmaster or _latest_fundmaster()
        out = app.invoke({
            "thread_id": cfg["configurable"]["thread_id"],
            "client_profile": profile,
            "fundmaster_path": fundmaster,
            "macro_context": {"source": args.macro},
            "no_review": args.no_review,
            "model": args.model,
            "output_dir": args.output,
        }, cfg)

    if "__interrupt__" in out:
        tid = cfg["configurable"]["thread_id"]
        print(f"  Paused for consultant review.\n"
              f"      Edit  data/review/{tid}.json\n"
              f"      Resume: python -m consultant_engine --resume {tid}")
        return 0
    print(f"  Done. Proposal written to {out.get('output_path')}")
    return 0
