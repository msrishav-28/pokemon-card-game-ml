"""cabt agent I/O and official environment contract tests."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "submission"))

import main as submission_main
from main import DECK_IDS, agent
from ptcg_agent.env.adapter import selection_indices_are_valid, to_canonical


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _assert_selection_contract(observation: dict, action: object) -> None:
    state = to_canonical(observation)
    assert selection_indices_are_valid(state, action)


@pytest.fixture
def live_observation():
    return _load_fixture("obs_sample.json")


@pytest.fixture
def live_multi_observation():
    return _load_fixture("multi_select_obs_sample.json")


class TestDeckContract:
    """The initial action is the locked list of exactly 60 integer IDs."""

    def test_deck_returns_locked_60_ids_from_live_deck_observation(self):
        observation = _load_fixture("deck_obs_sample.json")
        result = agent(observation)

        assert isinstance(result, list)
        assert len(result) == 60
        assert all(type(card_id) is int for card_id in result)
        assert result == DECK_IDS

    def test_deck_action_is_a_copy(self):
        observation = _load_fixture("deck_obs_sample.json")
        assert agent(observation) is not DECK_IDS

    def test_all_submission_deck_encodings_match(self):
        submission_dir = FIXTURES_DIR.parent / "submission"
        csv_ids = [
            int(line)
            for line in (submission_dir / "deck.csv").read_text().splitlines()
            if line.strip()
        ]
        json_ids = json.loads((submission_dir / "deck.json").read_text())
        assert csv_ids == json_ids == DECK_IDS

    def test_deck_phase_resets_stateful_policy_and_fallback_telemetry(
        self, monkeypatch
    ):
        calls = []
        monkeypatch.setattr(submission_main, "reset_policy", lambda: calls.append(True))
        submission_main._policy_fallback_count = 7
        submission_main._last_policy_error = "old"

        result = submission_main.agent(_load_fixture("deck_obs_sample.json"))

        assert result == DECK_IDS
        assert calls == [True]
        assert submission_main._policy_fallback_count == 0
        assert submission_main._last_policy_error is None


class TestSelectContract:
    """Battle actions have exactly maxCount unique in-range integer indexes."""

    def test_live_main_selection(self, live_observation):
        _assert_selection_contract(live_observation, agent(live_observation))

    def test_live_multi_selection(self, live_multi_observation):
        select = live_multi_observation["select"]
        assert select["maxCount"] > 1
        result = agent(live_multi_observation)
        _assert_selection_contract(live_multi_observation, result)

    def test_policy_exception_uses_legal_oracle_fallback(
        self, monkeypatch, live_observation
    ):
        def fail_policy(*args, **kwargs):
            raise RuntimeError("deliberate test failure")

        monkeypatch.setattr(submission_main, "get_action", fail_policy)
        result = submission_main.agent(live_observation)
        select = live_observation["select"]
        assert result == list(range(select["maxCount"]))
        _assert_selection_contract(live_observation, result)

    @pytest.mark.parametrize(
        "invalid_action",
        (
            [-1],       # out of range
            [True],     # bool is an int subclass, but not an engine index here
            [0, 0],     # wrong count and duplicate
            (0,),       # cabt contract requires list[int]
        ),
    )
    def test_invalid_policy_output_uses_legal_oracle_fallback(
        self, monkeypatch, live_observation, invalid_action
    ):
        def invalid_policy(*args, **kwargs):
            return invalid_action, [], []

        monkeypatch.setattr(submission_main, "get_action", invalid_policy)
        result = submission_main.agent(live_observation)
        select = live_observation["select"]
        assert result == list(range(select["maxCount"]))
        _assert_selection_contract(live_observation, result)


class TestOfficialEnvironmentContract:
    """Executable checks against the installed official cabt interpreter."""

    def test_cabt_specification(self):
        from kaggle_environments import make

        specification = make("cabt", debug=True).specification

        assert specification["agents"] == [2]
        assert specification["action"]["type"] == "array"
        assert specification["observation"]["remainingOverageTime"]["default"] == 600
        assert specification["reward"]["enum"] == [-1, 0, 1]
        assert specification["configuration"]["actTimeout"]["default"] == 0
        assert specification["configuration"]["runTimeout"]["default"] == 2000

    def test_successful_live_episode_status_and_reward_contract(self):
        from kaggle_environments import make

        env = make("cabt", debug=True)
        env.run(["random", "first"])
        episode = env.toJSON()

        assert episode["statuses"] == ["DONE", "DONE"]
        assert all(reward in (-1, 0, 1) for reward in episode["rewards"])
        assert sorted(episode["rewards"]) in ([-1, 1], [0, 0])

    def test_invalid_deck_status_contract(self):
        from kaggle_environments import make

        env = make("cabt", debug=True)
        env.run([lambda observation: [], "first"])
        episode = env.toJSON()

        assert episode["statuses"] == ["INVALID", "DONE"]
        # The framework uses null for the disqualified player's terminal
        # reward; the untouched opponent retains the default reward 0.
        assert episode["rewards"] == [None, 0]

    def test_invalid_selection_status_contract(self):
        from kaggle_environments import make
        from kaggle_environments.envs.cabt.cabt import deck

        def invalid_selection(observation):
            return list(deck) if observation["select"] is None else [-1]

        env = make("cabt", debug=True)
        env.run([invalid_selection, "first"])
        episode = env.toJSON()

        assert episode["statuses"] == ["INVALID", "DONE"]
        assert episode["rewards"] == [None, 1]
