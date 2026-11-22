"""job-match --resume resume.txt --job job.txt [--llm] [--out report.md]"""

from __future__ import annotations

import argparse
from pathlib import Path

from .llm import OpenAICompatibleClient
from .pipeline import run_pipeline, to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="job-match", description="Multi-agent resume vs job-description analyzer")
    parser.add_argument("--resume", required=True, help="Plain-text or Markdown resume")
    parser.add_argument("--job", required=True, help="Plain-text job description")
    parser.add_argument("--llm", action="store_true", help="Use an OpenAI-compatible LLM for extraction and coaching")
    parser.add_argument("--out", help="Write the Markdown report here (default: print)")
    args = parser.parse_args(argv)

    state = run_pipeline(Path(args.resume).read_text(encoding="utf-8"),
                         Path(args.job).read_text(encoding="utf-8"),
                         OpenAICompatibleClient() if args.llm else None)
    report = to_markdown(state)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Match score {state.score}/100 — report written to {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
