"""Contract tests for the raw cabt observation adapter.

All base observations come from ``make("cabt")`` captures. Tests mutate deep
copies only to exercise forward-compatible or optional-field handling; no
hand-authored observation is checked in as a fixture.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ptcg_agent.env.adapter import (
    describe_option,
    legal_indices,
    selection_indices_are_valid,
    to_canonical,
)
from ptcg_agent.env.types import CanonicalState


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    assert path.is_file(), f"missing required live fixture: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json_digest(value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class TestLiveFixtureProvenance:
    def test_manifest_hashes_every_captured_fixture(self):
        manifest = _load_fixture("live_capture_manifest.json")

        assert manifest["generatedBy"] == "scripts/inspect_obs.py"
        assert manifest["source"] == "make('cabt').run(['random', 'first'])"
        assert manifest["kaggleEnvironmentsVersion"] == "1.32.7"
        assert manifest["cabtSpecificationVersion"] == "1.0.0"

        for filename, record in manifest["fixtures"].items():
            fixture = _load_fixture(filename)
            assert record["status"] == "ACTIVE"
            assert (
                _canonical_json_digest(fixture)
                == record["sha256CanonicalJson"]
            )

    def test_manifest_records_a_successful_official_episode(self):
        manifest = _load_fixture("live_capture_manifest.json")
        for result in manifest["episodeResults"]:
            assert result["statuses"] == ["DONE", "DONE"]
            assert all(reward in (-1, 0, 1) for reward in result["rewards"])
            assert sorted(result["rewards"]) in ([-1, 1], [0, 0])

    def test_legal_actions_fixture_is_exact_select_payload(self):
        observation = _load_fixture("obs_sample.json")
        legal_actions = _load_fixture("legal_actions_sample.json")
        assert observation["select"] == legal_actions


class TestDeckPhase:
    def test_live_deck_observation(self):
        obs = _load_fixture("deck_obs_sample.json")
        assert obs["select"] is None
        assert obs["current"] is None

        state = to_canonical(obs)

        assert isinstance(state, CanonicalState)
        assert state.select_context is None
        assert state.select_max_count == 0
        assert state.select_min_count == 0
        assert state.legal_options == []
        assert state.legal_option_indices == []
        assert state.remaining_overage_time == 600
        assert state.raw is obs

    def test_deck_action_is_not_a_selection_action(self):
        state = to_canonical(_load_fixture("deck_obs_sample.json"))
        assert not selection_indices_are_valid(state, [0] * 60)


class TestBattlePhase:
    def test_live_main_observation_maps_player_perspective(self):
        obs = _load_fixture("obs_sample.json")
        state = to_canonical(obs)
        current = obs["current"]
        your_index = current["yourIndex"]
        opponent_index = 1 - your_index

        assert isinstance(state, CanonicalState)
        assert state.raw is obs
        assert state.your_index == your_index
        assert state.turn == current["turn"]
        assert state.turn_action_count == current["turnActionCount"]
        assert state.first_player == current["firstPlayer"]
        assert state.select_context == "MAIN"
        assert state.select_context_id == obs["select"]["context"]
        assert state.select_type == obs["select"]["type"]
        assert state.select_max_count == obs["select"]["maxCount"]
        assert state.select_min_count == obs["select"]["minCount"]
        assert state.result is None  # live -1 means the battle is unfinished
        assert state.me.active.card_id == current["players"][your_index]["active"][0]["id"]
        assert state.opp.active.card_id == current["players"][opponent_index]["active"][0]["id"]
        assert state.me.hand == current["players"][your_index]["hand"]
        assert state.opp.hand is None
        assert state.logs_tail == obs["logs"][-20:]

    def test_live_energized_pokemon_uses_integer_energy_type_ids(self):
        state = to_canonical(_load_fixture("energized_obs_sample.json"))
        pokemon = [state.me.active, *state.me.bench, state.opp.active, *state.opp.bench]
        energized = [card for card in pokemon if card and card.energies]

        assert energized, "capture tool promised at least one energized Pokemon"
        assert all(type(energy) is int for card in energized for energy in card.energies)

    def test_optional_none_containers_do_not_crash(self):
        obs = copy.deepcopy(_load_fixture("obs_sample.json"))
        obs["logs"] = None
        obs["current"]["stadium"] = None
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        me["bench"] = None
        me["discard"] = None
        me["prize"] = None
        me.pop("handCount")

        state = to_canonical(obs)

        assert state.logs_tail == []
        assert state.stadium == []
        assert state.me.bench == []
        assert state.me.discard == []
        assert state.me.prizes_remaining == 0
        assert state.me.hand_count == len(me["hand"])

    def test_unknown_appended_fields_are_preserved_only_in_raw(self):
        obs = copy.deepcopy(_load_fixture("obs_sample.json"))
        obs["futureObservationField"] = {"opaque": True}
        obs["select"]["futureSelectionField"] = 123
        obs["current"]["futureStateField"] = "new"
        active = obs["current"]["players"][obs["current"]["yourIndex"]]["active"][0]
        active["futurePokemonField"] = [1, 2, 3]

        state = to_canonical(obs)

        assert state.raw is obs
        assert state.raw["futureObservationField"] == {"opaque": True}
        assert state.me.active.raw["futurePokemonField"] == [1, 2, 3]

    def test_unknown_future_context_gets_stable_name(self):
        obs = copy.deepcopy(_load_fixture("obs_sample.json"))
        obs["select"]["context"] = 999
        state = to_canonical(obs)
        assert state.select_context == "UNKNOWN_999"
        assert state.select_context_id == 999

    def test_active_status_conditions_are_copied_from_player_state(self):
        obs = copy.deepcopy(_load_fixture("obs_sample.json"))
        me = obs["current"]["players"][obs["current"]["yourIndex"]]
        me["poisoned"] = True
        me["confused"] = True

        state = to_canonical(obs)

        assert state.me.poisoned is True
        assert state.me.confused is True
        assert state.me.active.status_conditions == ["POISON", "CONFUSE"]

    def test_engine_result_values_are_not_confused_with_rewards(self):
        obs = copy.deepcopy(_load_fixture("obs_sample.json"))
        for engine_result in (0, 1, 2):
            obs["current"]["result"] = engine_result
            assert to_canonical(obs).result == engine_result


class TestSelectionIndexContract:
    def test_live_multi_select_has_enough_unique_options(self):
        obs = _load_fixture("multi_select_obs_sample.json")
        state = to_canonical(obs)
        expected = list(range(state.select_max_count))

        assert state.select_max_count > 1
        assert state.select_min_count <= state.select_max_count
        assert state.select_max_count <= len(state.legal_options)
        assert legal_indices(state) == list(range(len(state.legal_options)))
        assert selection_indices_are_valid(state, expected)

    def test_wrong_count_is_rejected(self):
        state = to_canonical(_load_fixture("multi_select_obs_sample.json"))
        assert not selection_indices_are_valid(
            state, list(range(state.select_max_count - 1))
        )

    def test_duplicate_indices_are_rejected(self):
        state = to_canonical(_load_fixture("multi_select_obs_sample.json"))
        assert not selection_indices_are_valid(state, [0] * state.select_max_count)

    def test_out_of_range_index_is_rejected(self):
        state = to_canonical(_load_fixture("multi_select_obs_sample.json"))
        indices = list(range(state.select_max_count))
        indices[-1] = len(state.legal_options)
        assert not selection_indices_are_valid(state, indices)

    def test_negative_non_integer_bool_and_tuple_are_rejected(self):
        state = to_canonical(_load_fixture("obs_sample.json"))
        assert not selection_indices_are_valid(state, [-1])
        assert not selection_indices_are_valid(state, [0.0])
        assert not selection_indices_are_valid(state, [True])
        assert not selection_indices_are_valid(state, (0,))


class TestDescribeOption:
    def test_known_options(self):
        assert "ATTACK" in describe_option({"type": 13, "attackId": 42})
        assert "END" in describe_option({"type": 14})
        assert "PLAY" in describe_option({"type": 7, "index": 3})
        assert "RETREAT" in describe_option({"type": 12})

    def test_unknown_option_type_is_forward_compatible(self):
        assert describe_option({"type": 999}) == "UNKNOWN_999"
