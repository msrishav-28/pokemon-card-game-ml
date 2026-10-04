from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptcg_agent.eval.harness import action_contract, run_batch, wilson_ci
from ptcg_agent.eval.opponents import load_agent, load_opponent


ROOT = Path(__file__).resolve().parents[1]


def test_wilson_known_interval() -> None:
    low, high = wilson_ci(11, 20)
    assert low == pytest.approx(0.342085, abs=1e-6)
    assert high == pytest.approx(0.741802, abs=1e-6)


def test_action_contract_uses_live_fixture() -> None:
    observation = json.loads((ROOT / "fixtures" / "obs_sample.json").read_text())
    select = observation["select"]
    assert select is not None
    legal_action = list(range(select["maxCount"]))
    result = action_contract(observation, legal_action)
    assert result["ok"]
    assert result["expected_count"] == len(legal_action)
    assert result["option_count"] == len(select["option"])


def test_action_contract_rejects_duplicate_indices_on_live_multiselect_fixture() -> None:
    observation = json.loads(
        (ROOT / "fixtures" / "multi_select_obs_sample.json").read_text()
    )
    select = observation["select"]
    assert select is not None and select["maxCount"] == 3
    assert action_contract(observation, [0, 1, 2])["ok"]
    duplicate = action_contract(observation, [0, 0, 1])
    assert not duplicate["ok"]
    assert not duplicate["indices_unique"]


@pytest.mark.parametrize("name", ["random", "first"])
def test_builtin_opponent_loader(name: str) -> None:
    opponent = load_opponent(name, ROOT)
    assert opponent.name == name
    assert callable(opponent.agent)
    assert opponent.deck_ids is not None
    assert len(opponent.deck_ids) == 60


def test_live_one_game_writes_every_observed_decision(tmp_path: Path) -> None:
    summary = run_batch(
        n_games=1,
        agent_path=ROOT / "submission" / "main.py",
        opponent="first",
        tag="pytest-live",
        output_dir=tmp_path / "experiments",
        replay_dir=tmp_path / "replays",
        repo_root=ROOT,
        base_seed=17,
    )
    lines = [
        json.loads(line)
        for line in Path(summary["replay_jsonl"]).read_text(encoding="utf-8").splitlines()
    ]
    decisions = [line for line in lines if line["kind"] == "decision"]
    game = summary["game_records"][0]
    assert summary["results"]["completed"] == 1
    assert summary["results"]["invalid"] == 0
    assert len(decisions) == game["agent_decisions"] + game["opponent_decisions"]
    assert all("observation" in decision and "action" in decision for decision in decisions)
    assert all(decision["engine_seed"] is None for decision in decisions)
    agent_selections = [
        decision
        for decision in decisions
        if decision["role"] == "agent"
        and decision["contract"]["phase"] == "selection"
    ]
    assert agent_selections
    assert all(decision.get("policy_fallback") is False for decision in agent_selections)
    assert all(
        len(decision["scores"])
        == len(decision["observation"]["select"]["option"])
        for decision in agent_selections
    )
    assert summary["seed_policy"] == "seat-paired"


def test_live_buddy_loader_reuses_official_engine() -> None:
    from kaggle_environments import make

    buddy = load_opponent("buddy", ROOT)
    env = make("cabt", debug=False)
    env.run(["random", buddy.agent])
    assert [state.status for state in env.state] == ["DONE", "DONE"]


def test_live_buddy_agent_loader_reuses_official_engine() -> None:
    from kaggle_environments import make

    buddy_main = ROOT / "refs" / "buddy-lucario" / "main.py"
    buddy = load_agent(buddy_main, ROOT)
    assert buddy.source == str(buddy_main.resolve())
    assert buddy.name == "buddy-lucario"
    env = make("cabt", debug=False)
    env.run([buddy.agent, "first"])
    assert [state.status for state in env.state] == ["DONE", "DONE"]
