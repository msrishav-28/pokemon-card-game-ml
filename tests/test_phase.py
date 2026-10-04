"""
tests/test_phase.py

Unit tests for the GamePhase detector.
Constructs minimal CanonicalState fixtures using the actual field names
from ptcg_agent.env.types — no guessing.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ptcg_agent.features.phase import detect_phase, GamePhase
from ptcg_agent.env.types import CanonicalState, PlayerView, PokemonView


def _make_pokemon(energy_count: int = 0) -> PokemonView:
    """Return a minimal PokemonView with the given number of attached energies."""
    return PokemonView(
        card_id=1,
        name="Mock",
        hp=100,
        max_hp=100,
        energies=[6] * energy_count,
        tools=[],
        status_conditions=[],
        retreat_cost=1,
        is_ex=False,
        is_mega_ex=False,
        raw={},
    )


def _make_player(prizes_remaining: int, active_energy: int = 0) -> PlayerView:
    """Return a minimal PlayerView with the given prize count."""
    return PlayerView(
        active=_make_pokemon(active_energy),
        bench=[],
        hand=[],
        hand_count=5,
        deck_count=40,
        discard=[],
        prizes=[None] * prizes_remaining,   # face-down prize slots
        prizes_remaining=prizes_remaining,
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


def _make_state(
    turn: int,
    my_prizes: int,
    op_prizes: int,
    my_active_energy: int = 0,
) -> CanonicalState:
    """Return a minimal CanonicalState for phase-detection tests."""
    return CanonicalState(
        your_index=0,
        remaining_overage_time=600.0,
        result=None,
        turn=turn,
        turn_action_count=0,
        first_player=0,
        select_context="MAIN",
        select_context_id=0,
        select_type=0,
        select_max_count=1,
        select_min_count=1,
        legal_options=[],
        legal_option_indices=[],
        me=_make_player(my_prizes, my_active_energy),
        opp=_make_player(op_prizes),
        stadium=[],
        looking=None,
        logs_tail=[],
        effect_card=None,
        context_card=None,
        raw={},
    )


# ---------------------------------------------------------------------------
# Phase detection tests
# ---------------------------------------------------------------------------

def test_phase_opening_turn1():
    s = _make_state(turn=1, my_prizes=6, op_prizes=6)
    assert detect_phase(s) == GamePhase.OPENING


def test_phase_opening_turn2():
    s = _make_state(turn=2, my_prizes=6, op_prizes=6)
    assert detect_phase(s) == GamePhase.OPENING


def test_phase_closure_2_prizes_left():
    s = _make_state(turn=10, my_prizes=2, op_prizes=6)
    assert detect_phase(s) == GamePhase.CLOSURE


def test_phase_closure_1_prize_left():
    s = _make_state(turn=8, my_prizes=1, op_prizes=4)
    assert detect_phase(s) == GamePhase.CLOSURE


def test_phase_stabilization_opponent_near_win():
    # Opponent has 2 prizes left, we have 5 — we're behind
    s = _make_state(turn=10, my_prizes=5, op_prizes=2)
    assert detect_phase(s) == GamePhase.STABILIZATION


def test_phase_prize_conversion_we_are_ahead():
    # We have taken prizes (4 left), opponent still at 6
    s = _make_state(turn=5, my_prizes=4, op_prizes=6)
    assert detect_phase(s) == GamePhase.PRIZE_CONVERSION


def test_phase_pressure_active_has_2_energy():
    # Mid-game, no prizes taken yet, active Pokémon has 2 energy attached
    s = _make_state(turn=5, my_prizes=6, op_prizes=6, my_active_energy=2)
    assert detect_phase(s) == GamePhase.PRESSURE


def test_phase_pressure_active_has_3_energy():
    s = _make_state(turn=6, my_prizes=6, op_prizes=6, my_active_energy=3)
    assert detect_phase(s) == GamePhase.PRESSURE


def test_phase_development_active_has_1_energy():
    # Active only has 1 energy — not enough to be "pressure"
    s = _make_state(turn=5, my_prizes=6, op_prizes=6, my_active_energy=1)
    assert detect_phase(s) == GamePhase.DEVELOPMENT


def test_phase_development_no_energy():
    # Active has no energy at all
    s = _make_state(turn=4, my_prizes=6, op_prizes=6, my_active_energy=0)
    assert detect_phase(s) == GamePhase.DEVELOPMENT


def test_closure_takes_priority_over_stabilization():
    # We have 2 prizes left and opponent has 2 — closure wins (we act first)
    s = _make_state(turn=9, my_prizes=2, op_prizes=2)
    assert detect_phase(s) == GamePhase.CLOSURE


def test_stabilization_takes_priority_over_pressure():
    # Opponent near win (2 prizes) but we have energy — stabilization wins
    s = _make_state(turn=8, my_prizes=5, op_prizes=2, my_active_energy=3)
    assert detect_phase(s) == GamePhase.STABILIZATION
