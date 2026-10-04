"""Extract one complete, result-linked live game from an evaluation replay.

Records are copied without modifying their observation/action payloads.  The
output is therefore a compact fixture from the real cabt engine, not a mocked
or reconstructed episode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(
    replay_path: Path,
    game_id: str,
    output_path: Path,
) -> dict[str, Any]:
    replay_path = replay_path.resolve()
    output_path = output_path.resolve()
    if not replay_path.is_file():
        raise FileNotFoundError(replay_path)

    selected_lines: list[str] = []
    kinds: dict[str, int] = {}
    for raw_line in replay_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        record = json.loads(raw_line)
        if record.get("game_id") != game_id:
            continue
        kind = str(record.get("kind", "unknown"))
        kinds[kind] = kinds.get(kind, 0) + 1
        selected_lines.append(raw_line)

    if not selected_lines:
        raise ValueError(f"game_id not found in replay: {game_id}")
    if kinds.get("game_end") != 1:
        raise ValueError(
            f"fixture requires exactly one result-linked game_end; found {kinds}"
        )
    if kinds.get("decision", 0) == 0:
        raise ValueError("fixture contains no decisions")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(selected_lines) + "\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "source_replay": replay_path.name,
        "source_replay_sha256": _sha256(replay_path),
        "game_id": game_id,
        "output": output_path.name,
        "output_sha256": _sha256(output_path),
        "records": len(selected_lines),
        "kinds": kinds,
        "bytes": output_path.stat().st_size,
        "payloads_copied_verbatim": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("game_id")
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="optional path for one JSON manifest entry",
    )
    args = parser.parse_args()
    result = extract(args.replay, args.game_id, args.output)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
