"""Focused contract and plan-follow-through tests for the B3 candidate."""
from __future__ import annotations

from pathlib import Path

import pytest

from ptcg_agent.env.adapter import selection_indices_are_valid
from ptcg_agent.env.types import CanonicalState, PlayerView, PokemonView
from ptcg_agent.policies.planned_candidate import (
    CardCatalog,
    PlannedPolicy,
)


ROOT = Path(__file__).resolve().parents[1]


def _pokemon(card_id: int, *, hp: int = 100, energies: int = 0) -> PokemonView:
    return PokemonView(
        card_id=card_id,
        name="",
        hp=hp,
        max_hp=hp,
        energies=[6] * energies,
        tools=[],
        status_conditions=[],
        retreat_cost=0,
        is_ex=False,
        is_mega_ex=False,
        raw={"id": card_id, "energyCards": [], "tools": []},
    )


def _player(
    active: PokemonView,
    *,
    bench: list[PokemonView] | None = None,
    hand: list[dict] | None = None,
    prizes: int = 6,
) -> PlayerView:
    return PlayerView(
        active=active,
        bench=list(bench or []),
        hand=list(hand or []),
        hand_count=len(hand or []),
        deck_count=40,
        discard=[],
        prizes=[None] * prizes,
        prizes_remaining=prizes,
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


def _state(
    options: list[dict],
    *,
    me: PlayerView | None = None,
    opp: PlayerView | None = None,
    context: int = 0,
    max_count: int = 1,
    raw: dict | None = None,
) -> CanonicalState:
    me = me or _player(_pokemon(678, energies=2))
    opp = opp or _player(_pokemon(673))
    raw = raw or {"select": {"option": options, "maxCount": max_count}}
    return CanonicalState(
        your_index=0,
        remaining_overage_time=600.0,
        result=None,
        turn=4,
        turn_action_count=0,
        first_player=0,
        select_context={0: "MAIN", 3: "SWITCH", 7: "TO_HAND"}.get(context, "TEST"),
        select_context_id=context,
        select_type=0,
        select_max_count=max_count,
        select_min_count=max_count,
        legal_options=options,
        legal_option_indices=list(range(len(options))),
        me=me,
        opp=opp,
        stadium=[],
        looking=None,
        logs_tail=[],
        effect_card=None,
        context_card=None,
        raw=raw,
    )


def _catalog() -> CardCatalog:
    return CardCatalog.load(ROOT / "data" / "official" / "EN Card Data.csv")


def test_attack_plan_takes_visible_last_prize_lethal() -> None:
    me = _player(_pokemon(678, hp=340, energies=2), prizes=1)
    # Opponent still has six prizes: this specifically guards the buddy bug
    # that checked the opponent's array instead of ours.
    opp = _player(_pokemon(673, hp=200), prizes=6)
    state = _state(
        [
            {"type": 13, "attackId": 982},  # Aura Jab: 130, not a KO
            {"type": 13, "attackId": 983},  # Mega Brave: 270, wins
            {"type": 14},
        ],
        me=me,
        opp=opp,
    )
    policy = PlannedPolicy(_catalog())

    chosen, scores, features = policy.get_action(state, return_details=True)

    assert chosen == [1]
    assert policy.plan.terminal
    assert policy.plan.attack_id == 983
    assert scores[1] > scores[0]
    assert features[1]["visible_game_lethal"] == 1.0


def test_attack_plan_directs_the_manual_attach() -> None:
    me = _player(
        _pokemon(678, hp=340, energies=0),
        bench=[_pokemon(677)],
        hand=[{"id": 6}],
    )
    options = [
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 4, "inPlayIndex": 0},
        {"type": 8, "area": 2, "index": 0, "inPlayArea": 5, "inPlayIndex": 0},
        {"type": 14},
    ]
    policy = PlannedPolicy(_catalog())
    state = _state(options, me=me)

    chosen, _, features = policy.get_action(state, return_details=True)

    assert policy.plan.attacker_slot == 0
    assert policy.plan.needs_energy
    assert chosen == [0]
    assert features[0]["plan_match"] == 1.0


def test_switch_selection_follows_the_plan_across_contexts() -> None:
    me = _player(
        _pokemon(675),
        bench=[_pokemon(677), _pokemon(678, hp=340, energies=2)],
        hand=[{"id": 1123}],
    )
    policy = PlannedPolicy(_catalog())
    main = _state(
        [{"type": 7, "index": 0}, {"type": 14}],
        me=me,
        opp=_player(_pokemon(673, hp=200)),
    )

    assert policy.get_action(main) == [0]
    assert policy.plan.attacker_slot == 2

    switch_options = [
        {"type": 3, "area": 5, "index": 0, "playerIndex": 0},
        {"type": 3, "area": 5, "index": 1, "playerIndex": 0},
    ]
    switch = _state(
        switch_options,
        me=me,
        opp=main.opp,
        context=3,
    )
    chosen, scores, features = policy.get_action(switch, return_details=True)

    assert chosen == [1]
    assert scores[1] > scores[0]
    assert features[1]["plan_match"] == 1.0


def test_card_choice_resolves_official_deck_area_not_hand_position() -> None:
    me = _player(
        _pokemon(673),
        hand=[{"id": 675}, {"id": 6}],  # deliberately unrelated indexes
    )
    deck_view = [{"id": 1102}, {"id": 674}]
    options = [
        {"type": 3, "area": 1, "index": 0, "playerIndex": 0},
        {"type": 3, "area": 1, "index": 1, "playerIndex": 0},
    ]
    raw = {"select": {"deck": deck_view, "option": options, "maxCount": 1}}
    state = _state(options, me=me, context=7, raw=raw)

    chosen, _, features = PlannedPolicy(_catalog()).get_action(
        state, return_details=True
    )

    assert chosen == [1]  # Hariyama completes the visible Makuhita line.
    assert features[0]["card_id"] == 1102.0
    assert features[1]["card_id"] == 674.0


def test_exact_distinct_index_contract_and_aligned_telemetry() -> None:
    options = [
        {"type": 0, "number": 1},
        {"type": 0, "number": 4},
        {"type": 1},
        {"type": 2},
    ]
    state = _state(options, context=38, max_count=3)

    chosen, scores, features = PlannedPolicy(_catalog()).get_action(
        state, return_details=True
    )

    assert chosen == [1, 0, 2]
    assert len(chosen) == len(set(chosen)) == state.select_max_count
    assert len(scores) == len(features) == len(options)
    assert selection_indices_are_valid(state, chosen)


def test_impossible_cardinality_fails_before_returning_an_illegal_action() -> None:
    state = _state([{"type": 1}], max_count=2)

    with pytest.raises(ValueError, match="maxCount"):
        PlannedPolicy(_catalog()).get_action(state)


def test_missing_csv_keeps_locked_deck_metadata_fallback(tmp_path: Path) -> None:
    catalog = CardCatalog.load(tmp_path / "missing.csv")

    assert catalog.source == "fallback"
    lucario = catalog.get(678)
    assert lucario is not None and lucario.mega_ex and lucario.stage1
