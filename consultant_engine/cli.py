import argparse, json, sqlite3, sys
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from consultant_engine.graph import build_graph


def _thread_id(args) -> str:
    if args.resume:
        return args.resume
    stem = Path(args.profile).stem
    return f"{stem}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser("consultant_engine")
    ap.add_argument("--profile")
    ap.add_argument("--fundmaster")
    ap.add_argument("--macro", default="none")
    ap.add_argument("-o", "--output", default="output/fund_proposals")
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--resume")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    args = ap.parse_args(argv)

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
        out = app.invoke({
            "thread_id": cfg["configurable"]["thread_id"],
            "client_profile": profile,
            "fundmaster_path": args.fundmaster,
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
