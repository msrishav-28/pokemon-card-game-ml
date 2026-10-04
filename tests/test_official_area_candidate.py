"""Schema regressions for the opt-in official-area policy candidate."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ptcg_agent.env.adapter import to_canonical
from ptcg_agent.env.types import CanonicalState, PlayerView, PokemonView
from ptcg_agent.policies.official_area_candidate import get_action


def _pokemon(card_id: int, energies: int = 0) -> PokemonView:
    return PokemonView(
        card_id=card_id,
        name="",
        hp=100,
        max_hp=100,
        energies=[6] * energies,
        tools=[],
        status_conditions=[],
        retreat_cost=0,
        is_ex=False,
        is_mega_ex=False,
        raw={},
    )


def _player(active: PokemonView, bench: list[PokemonView], hand=None) -> PlayerView:
    return PlayerView(
        active=active,
        bench=bench,
        hand=hand,
        hand_count=len(hand or []),
        deck_count=40,
        discard=[],
        prizes=[None] * 6,
        prizes_remaining=6,
        supporter_played=False,
        stadium_played=False,
        energy_attached=False,
        retreated=False,
        poisoned=False,
        burned=False,
        asleep=False,
        paralyzed=False,
        confused=False,
    )


def _attach_choice_state() -> CanonicalState:
    # Official cabt areas: Active=4, Bench=5.  Put the utility Pokemon Active
    # so a reversed/off-by-one mapping makes the policy choose the wrong target.
    me = _player(
        active=_pokemon(675),  # Lunatone
        bench=[_pokemon(677)],  # Riolu
        hand=[{"id": 6}],
    )
    opp = _player(active=_pokemon(722), bench=[])
    options = [
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0},
    ]
    return CanonicalState(
        your_index=0,
        remaining_overage_time=600.0,
        result=None,
        turn=4,
        turn_action_count=0,
        first_player=0,
        select_context="MAIN",
        select_context_id=0,
        select_type=0,
        select_max_count=1,
        select_min_count=1,
        legal_options=options,
        legal_option_indices=[0, 1],
        me=me,
        opp=opp,
        stadium=[],
        looking=None,
        logs_tail=[],
        effect_card=None,
        context_card=None,
        raw={},
    )


def test_live_fixture_active_attach_gets_target_aware_score():
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "obs_sample.json")
    with open(fixture_path, encoding="utf-8") as fixture_file:
        state = to_canonical(json.load(fixture_file))

    assert state.me.active is not None
    assert state.me.bench == []
    attach_indices = [
        index
        for index, option in enumerate(state.legal_options)
        if option.get("type") == 8 and option.get("inPlayArea") == 4
    ]
    assert attach_indices

    chosen, scores, features = get_action(state, return_details=True)

    assert chosen[0] in attach_indices
    assert scores[chosen[0]] > 0
    assert features[chosen[0]]["tempo"] > 0


def test_official_bench_target_is_preferred_for_riolu_over_active_lunatone():
    state = _attach_choice_state()

    assert get_action(state) == [1]


def test_official_bench_area_is_resolved_during_switch_selection():
    state = _attach_choice_state()
    state.select_context = "SWITCH"
    state.select_context_id = 3
    state.me.bench = [_pokemon(675), _pokemon(678, energies=2)]
    state.legal_options = [
        {"type": 3, "area": 5, "index": 0, "playerIndex": 0},
        {"type": 3, "area": 5, "index": 1, "playerIndex": 0},
    ]

    assert get_action(state) == [1]


def test_candidate_does_not_mutate_adapter_options():
    state = _attach_choice_state()
    before = [dict(option) for option in state.legal_options]

    get_action(state)

    assert state.legal_options == before
