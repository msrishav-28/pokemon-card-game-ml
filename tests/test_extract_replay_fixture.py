import json

import pytest

from scripts.extract_replay_fixture import extract


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def test_extract_copies_only_complete_result_linked_game(tmp_path):
    source = tmp_path / "source.jsonl"
    records = [
        {"kind": "decision", "game_id": "g1", "observation": {"live": True}, "action": [0]},
        {"kind": "decision", "game_id": "g2", "observation": {"live": True}, "action": [1]},
        {"kind": "game_end", "game_id": "g1", "outcome": "win"},
        {"kind": "game_end", "game_id": "g2", "outcome": "loss"},
    ]
    _write_jsonl(source, records)
    output = tmp_path / "fixture.jsonl"

    manifest = extract(source, "g1", output)
    copied = [json.loads(line) for line in output.read_text().splitlines()]

    assert copied == [records[0], records[2]]
    assert manifest["kinds"] == {"decision": 1, "game_end": 1}
    assert manifest["payloads_copied_verbatim"] is True


def test_extract_rejects_unfinished_game(tmp_path):
    source = tmp_path / "source.jsonl"
    _write_jsonl(source, [{"kind": "decision", "game_id": "g1"}])

    with pytest.raises(ValueError, match="game_end"):
        extract(source, "g1", tmp_path / "fixture.jsonl")
