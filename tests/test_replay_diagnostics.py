"""Focused tests for replay diagnostics using replay records, not cabt fixtures."""

from __future__ import annotations

import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ptcg_agent.replay.diagnostics import analyze_jsonl, render_plain_text


def _write_jsonl(tmp_path, records):
    path = tmp_path / "records.jsonl"
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def test_terminal_reward_links_only_through_explicit_game_id(tmp_path):
    path = _write_jsonl(tmp_path, [
        {
            "kind": "decision",
            "game_id": "g-1",
            "role": "agent",
            "context": "MAIN",
            "action": [1],
            "legal_options": [{"type": 14}, {"type": 13}],
            "scores": [0.0, 10.0],
            "contract": {"ok": True, "expected_count": 1},
        },
        {
            "kind": "game_end",
            "game_id": "g-1",
            "outcome": "loss",
            "agent_status": "DONE",
            "opponent_status": "DONE",
            "rewards": [-1, 1],
            "agent_seat": 0,
            "runner_error": None,
        },
    ])

    report = analyze_jsonl([path])

    assert report["grouping"]["confirmed_terminal_games"] == 1
    assert report["terminal"]["outcomes"] == {"loss": 1}
    assert report["loss_attribution_coverage"]["with_linked_decisions"] == 1
    assert (
        report["loss_attribution_coverage"][
            "with_scores_and_options_same_decision"
        ]
        == 1
    )
    # Scores/options alone do not make a causal label.  The terminal record
    # would need an explicit causal decision reference as well.
    assert report["loss_attribution_coverage"]["attribution_ready_losses"] == 0
    assert report["terminal"]["failure_buckets"] == {
        "gameplay loss; decision cause unclassifiable": 1
    }


def test_prize_snapshot_without_terminal_is_unclassifiable(tmp_path):
    path = _write_jsonl(tmp_path, [{
        "episode_id": "ep-1",
        "context": "MAIN",
        "maxCount": 1,
        "chosen": [0],
        "scores": [5.0],
        "brief_state": {
            "my_prizes_remaining": 4,
            "opp_prizes_remaining": 0,
        },
    }])

    report = analyze_jsonl([path])

    assert report["terminal"]["outcomes"] == {}
    assert report["terminal"]["failure_buckets"] == {}
    assert report["terminal"]["unclassifiable_groups"] == {
        "no terminal metadata linked by explicit ID": 1
    }
    assert report["groups"][0]["classification"].startswith("unclassifiable:")


def test_engine_timeout_gets_evidence_based_failure_bucket(tmp_path):
    path = _write_jsonl(tmp_path, [
        {
            "kind": "decision",
            "game_id": "g-timeout",
            "role": "agent",
            "context": "MAIN",
            "action": [0],
            "contract": {"ok": True, "expected_count": 1},
        },
        {
            "kind": "game_end",
            "game_id": "g-timeout",
            "outcome": "loss",
            "agent_status": "TIMEOUT",
            "opponent_status": "DONE",
        },
    ])

    report = analyze_jsonl([path])

    assert report["terminal"]["failure_buckets"] == {
        "timeout / overage exhaustion (engine status TIMEOUT)": 1
    }


def test_schema_split_reports_no_scored_legal_option_decisions(tmp_path):
    path = _write_jsonl(tmp_path, [
        {
            "episode_id": "policy-episode",
            "context": "MAIN",
            "maxCount": 1,
            "chosen": [0],
            "scores": [2.0, 1.0],
        },
        {
            "kind": "decision",
            "game_id": "eval-game",
            "role": "agent",
            "context": "MAIN",
            "action": [0],
            "legal_options": [{"type": 14}, {"type": 13}],
            "contract": {"ok": True, "expected_count": 1},
        },
        {
            "kind": "game_end",
            "game_id": "eval-game",
            "outcome": "loss",
            "agent_status": "DONE",
        },
    ])

    report = analyze_jsonl([path])

    assert report["decisions"]["score_vector_decisions"] == 1
    assert report["decisions"]["legal_option_payload_decisions"] == 1
    assert report["decisions"]["scored_legal_option_decisions"] == 0
    assert report["loss_attribution_coverage"]["with_score_vectors"] == 0
    assert any("no shared identifier" in item for item in report["limitations"])


def test_plain_text_calls_out_unclassifiable_groups_and_signals(tmp_path):
    path = _write_jsonl(tmp_path, [{
        "episode_id": "ep-flat",
        "context": "ATTACH_TO",
        "maxCount": 1,
        "chosen": [0],
        "scores": [0.0, 0.0],
        "features": [{"tempo": 0.0}, {"tempo": 0.0}],
    }])

    text = render_plain_text(analyze_jsonl([path]))

    assert "all_zero_score_vector: 1" in text
    assert "all_zero_feature_vector: 1" in text
    assert "no terminal metadata linked by explicit ID: 1 group(s)" in text


def test_visible_last_prize_base_damage_lethal_miss_is_a_signal_only(tmp_path):
    path = _write_jsonl(tmp_path, [
        {
            "kind": "decision",
            "game_id": "g-lethal",
            "role": "agent",
            "action": [0],
            "observation": {
                "select": {
                    "context": 0,
                    "maxCount": 1,
                    "option": [
                        {"type": 13, "attackId": 982},
                        {"type": 13, "attackId": 983},
                    ],
                },
                "current": {
                    "yourIndex": 0,
                    "players": [
                        {"prize": [None], "active": [{"hp": 340}]},
                        {"prize": [None, None], "active": [{"hp": 200}]},
                    ],
                },
            },
        },
        {
            "kind": "game_end",
            "game_id": "g-lethal",
            "outcome": "loss",
            "agent_status": "DONE",
            "opponent_status": "DONE",
        },
    ])

    report = analyze_jsonl([path])
    signals = report["decisions"]["signals_not_causal_labels"]
    assert signals["visible_base_damage_game_lethal_opportunity"] == 1
    assert signals["visible_base_damage_game_lethal_missed"] == 1
    assert report["terminal"]["failure_buckets"] == {
        "gameplay loss; decision cause unclassifiable": 1
    }
