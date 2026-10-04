"""Seat-balanced local evaluation for the official ``cabt`` engine.

Examples:
    .venv/Scripts/python.exe scripts/run_batch.py --n 20 --opponent random
    .venv/Scripts/python.exe scripts/run_batch.py --n 20 --opponent first
    .venv/Scripts/python.exe scripts/run_batch.py --n 2 --opponent buddy

Every agent and opponent decision is written to an experiment-specific JSONL
file, including the exact live observation, returned action, decision duration,
and remaining overage time observed before the call.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ptcg_agent.eval.harness import run_batch  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate an agent in cabt with alternating seats. Native cabt "
            "chance cannot be seeded, so results are labeled seat-paired."
        )
    )
    parser.add_argument(
        "--agent",
        default=str(ROOT / "submission" / "main.py"),
        help="Python file exposing agent(...) (default: submission/main.py)",
    )
    parser.add_argument(
        "--opponent",
        default="random",
        help="random, first, buddy, refs/buddy-lucario/main.py, or another agent path",
    )
    parser.add_argument("--n", type=int, default=20, help="Exact number of games")
    parser.add_argument("--tag", default="eval", help="Experiment ID suffix")
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help=(
            "Base Python-policy RNG seed. This does not seed native cabt chance; "
            "both seat members of a full pair reuse the same Python seed."
        ),
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "output" / "experiments"),
        help="Experiment summary directory",
    )
    parser.add_argument(
        "--replays",
        default=str(ROOT / "output" / "replays"),
        help="Decision JSONL directory",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Let agent exceptions escape (use only for diagnosis)",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    summary = run_batch(
        n_games=args.n,
        agent_path=args.agent,
        opponent=args.opponent,
        tag=args.tag,
        output_dir=args.out,
        replay_dir=args.replays,
        repo_root=ROOT,
        base_seed=args.seed,
        debug=args.debug,
    )
    result = summary["results"]
    ci = result["win_rate_wilson95"]
    win_rate = result["win_rate"]
    win_rate_text = f"{win_rate:.1%}" if win_rate is not None else "n/a"
    print(f"Experiment: {summary['experiment_id']}")
    print(
        f"Opponent: {summary['opponent_name']} | games={summary['games']} | "
        f"pairing={summary['seed_policy']}"
    )
    print(
        f"W/D/L: {result['wins']}/{result['draws']}/{result['losses']} | "
        f"WR={win_rate_text} | Wilson95=[{ci[0]:.3f}, {ci[1]:.3f}]"
    )
    print(
        f"Invalid={result['invalid']} Timeout={result['timeout']} "
        f"Error={result['error']} RunnerError={result['runner_error']}"
    )
    print(
        "Decision timing (ms): "
        + json.dumps(summary["agent_timing"], sort_keys=True)
    )
    print(f"Mean leftover overage: {result['mean_leftover_overage_s']} s")
    print(f"Summary: {summary['experiment_json']}")
    print(f"Replay: {summary['replay_jsonl']}")


if __name__ == "__main__":
    main()
