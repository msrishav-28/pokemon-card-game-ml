"""Print an evidence-safe diagnostic summary for one or more replay JSONL files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ptcg_agent.replay.diagnostics import (  # noqa: E402
    analyze_jsonl,
    discover_jsonl_paths,
    render_plain_text,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit cabt replay evidence without inferring outcomes from board state."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        default=[str(ROOT / "output" / "replays")],
        help="JSONL file, directory, or glob (default: output/replays)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the complete machine-readable report instead of plain text",
    )
    args = parser.parse_args()

    try:
        paths = discover_jsonl_paths(args.inputs)
        if not paths:
            parser.error("no JSONL replay files found")
        report = analyze_jsonl(paths)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_plain_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
