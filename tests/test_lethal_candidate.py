"""B2 regressions derived from live state shape and official attack metadata."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ptcg_agent.env.adapter import to_canonical
from ptcg_agent.policies.lethal_candidate import get_action as lethal_action
from ptcg_agent.policies.official_area_candidate import get_action as area_action


ROOT = Path(__file__).resolve().parents[1]


def _attack_state(target_hp: int, prizes: int):
    raw = json.loads((ROOT / "fixtures" / "energized_obs_sample.json").read_text())
    state = to_canonical(raw)
    assert state.me.active is not None
    assert state.opp.active is not None
    state.me.active.card_id = 678
    state.me.active.energies = [6, 6]
    state.me.prizes = [None] * prizes
    state.me.prizes_remaining = prizes
    state.opp.active.hp = target_hp
    state.select_context = "MAIN"
    state.select_context_id = 0
    state.select_min_count = 1
    state.select_max_count = 1
    state.legal_options = [
        {"type": 13, "attackId": 982},
        {"type": 13, "attackId": 983},
    ]
    state.legal_option_indices = [0, 1]
    return state


def test_visible_last_prize_ko_beats_non_ko():
    state = _attack_state(target_hp=200, prizes=1)
    assert area_action(copy.deepcopy(state)) == [0]
    assert lethal_action(state) == [1]


def test_when_both_attacks_ko_incumbent_preference_is_preserved():
    state = _attack_state(target_hp=100, prizes=1)
    assert lethal_action(state) == area_action(copy.deepcopy(state)) == [0]


def test_override_is_narrow_to_last_prize():
    state = _attack_state(target_hp=200, prizes=2)
    assert lethal_action(state) == area_action(copy.deepcopy(state))


def test_details_mark_only_verified_base_damage_lethal():
    state = _attack_state(target_hp=200, prizes=1)
    chosen, scores, features = lethal_action(state, return_details=True)
    assert chosen == [1]
    assert scores[1] > scores[0]
    assert features[1]["visible_game_lethal"] == 1.0
    assert "visible_game_lethal" not in features[0]
