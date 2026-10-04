"""
tests/test_baseline_legal.py — Unit tests for the S3 heuristic policy.

Tests verify:
  1. Output contract: always returns a list[int] of correct length with
     indices in-range — regardless of board state.
  2. Priority ordering: attack > evolve > bench basic > end_turn
     in closure/mid-game phases.
  3. Veto logic: switch to naked bench is penalised; over-energising
     Lunatone is penalised.
  4. Non-MAIN contexts: TO_HAND prefers cards not yet on field;
     SETUP_ACTIVE prefers Riolu/Solrock over random basics.
  5. Phase sensitivity: closure weights make attacking score higher than
     in opening.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ptcg_agent.policies.heuristic import get_action
from ptcg_agent.env.types import CanonicalState, PlayerView, PokemonView

# ---------------------------------------------------------------------------
# Shared fixture helpers  (mirrors test_phase.py helpers)
# ---------------------------------------------------------------------------

def _poke(card_id: int, hp: int = 100, max_hp: int = 100,
          energies: int = 0, is_ex: bool = False,
          is_mega_ex: bool = False) -> PokemonView:
    return PokemonView(
        card_id=card_id, name="", hp=hp, max_hp=max_hp,
        energies=[6] * energies, tools=[],
        status_conditions=[], retreat_cost=1,
        is_ex=is_ex, is_mega_ex=is_mega_ex, raw={},
    )


def _player(prizes: int = 6, active_id: int = 677,
            active_energy: int = 0, bench: list | None = None,
            hand: list | None = None, hand_count: int = 5,
            energy_attached: bool = False,
            supporter_played: bool = False) -> PlayerView:
    return PlayerView(
        active=_poke(active_id, energies=active_energy),
        bench=bench or [],
        hand=hand,
        hand_count=hand_count,
        deck_count=40,
        discard=[],
        prizes=[None] * prizes,
        prizes_remaining=prizes,
        supporter_played=supporter_played,
        stadium_played=False,
        energy_attached=energy_attached,
        retreated=False,
        poisoned=False, burned=False, asleep=False,
        paralyzed=False, confused=False,
    )


def _state(turn: int = 4,
           my_prizes: int = 6, op_prizes: int = 6,
           active_id: int = 677, active_energy: int = 0,
           options: list | None = None,
           context_id: int = 0,           # 0 = MAIN
           max_count: int = 1,
           hand: list | None = None,
           hand_count: int = 5,
           bench: list | None = None,
           op_active_id: int = 722,
           energy_attached: bool = False,
           supporter_played: bool = False,
           first_player: int = 0) -> CanonicalState:
    opts = options or []
    return CanonicalState(
        your_index=0,
        remaining_overage_time=600.0,
        result=None,
        turn=turn,
        turn_action_count=0,
        first_player=first_player,
        select_context="MAIN" if context_id == 0 else f"CTX_{context_id}",
        select_context_id=context_id,
        select_type=0,
        select_max_count=max_count,
        select_min_count=1,
        legal_options=opts,
        legal_option_indices=list(range(len(opts))),
        me=_player(my_prizes, active_id, active_energy,
                   bench=bench, hand=hand,
                   hand_count=hand_count,
                   energy_attached=energy_attached,
                   supporter_played=supporter_played),
        opp=_player(op_prizes, op_active_id),
        stadium=[],
        looking=None,
        logs_tail=[],
        effect_card=None,
        context_card=None,
        raw={},
    )


# ---------------------------------------------------------------------------
# 1. Contract: output shape
# ---------------------------------------------------------------------------

class TestOutputContract:

    def test_empty_options_returns_empty(self):
        # Live cabt never pairs maxCount > 0 with an empty option list.
        s = _state(options=[], max_count=0)
        assert get_action(s) == []

    def test_max_count_zero_returns_empty(self):
        s = _state(options=[{"type": 14}], max_count=0)
        assert get_action(s) == []

    def test_single_option_returns_one_index(self):
        s = _state(options=[{"type": 14}], max_count=1)
        result = get_action(s)
        assert result == [0]

    def test_result_length_equals_max_count(self):
        opts = [{"type": 3, "area": 4, "index": i, "playerIndex": 0}
                for i in range(5)]
        s = _state(options=opts, max_count=3, context_id=7)  # TO_HAND
        result = get_action(s)
        assert len(result) == 3

    def test_all_indices_in_range(self):
        opts = [{"type": 14}, {"type": 13, "attackId": 42},
                {"type": 12}, {"type": 9, "inPlayArea": 4, "inPlayIndex": 0}]
        s = _state(options=opts, max_count=1)
        result = get_action(s)
        assert len(result) == 1
        assert 0 <= result[0] < len(opts)

    def test_no_duplicates_in_result(self):
        opts = [{"type": 3, "area": 4, "index": i, "playerIndex": 0}
                for i in range(4)]
        s = _state(options=opts, max_count=3, context_id=7)
        result = get_action(s)
        assert len(result) == len(set(result))


# ---------------------------------------------------------------------------
# 2. Priority: MAIN context ordering
# ---------------------------------------------------------------------------

class TestMainContextPriority:

    def test_attack_preferred_over_end(self):
        # Mid-game with energy on active: attack beats end_turn
        opts = [
            {"type": 14},                        # idx 0: END
            {"type": 13, "attackId": 100},       # idx 1: ATTACK
        ]
        s = _state(options=opts, active_energy=2)
        result = get_action(s)
        assert result[0] == 1   # ATTACK ranked first

    def test_evolve_preferred_over_end(self):
        opts = [
            {"type": 14},                                           # END
            {"type": 9, "inPlayArea": 4, "inPlayIndex": 0,         # EVOLVE
             "area": 2, "index": 0},
        ]
        s = _state(options=opts, bench=[_poke(673, energies=2)])   # Makuhita bench
        result = get_action(s)
        assert result[0] == 1   # EVOLVE ranked first

    def test_end_is_last_when_attack_available(self):
        opts = [
            {"type": 14},                        # END
            {"type": 13, "attackId": 100},       # ATTACK
            {"type": 12},                        # RETREAT
        ]
        s = _state(options=opts, max_count=1, active_energy=2)
        result = get_action(s)
        assert result[0] != 0   # END is not chosen first

    def test_play_basic_preferred_over_end_in_opening(self):
        # Turn 1, bench empty — benching a Riolu should beat end_turn
        hand = [{"id": 677}]  # Riolu in hand
        opts = [
            {"type": 14},                          # END
            {"type": 7, "index": 0},               # PLAY Riolu
        ]
        s = _state(turn=1, options=opts, hand=hand, bench=[])
        result = get_action(s)
        assert result[0] == 1   # PLAY ranked first

    def test_closure_attack_scores_higher_than_opening(self):
        """Closure phase attack score > opening phase attack score."""
        attack_opt = {"type": 13, "attackId": 100}

        s_open    = _state(turn=1, my_prizes=6, op_prizes=6,
                           options=[attack_opt], active_energy=2)
        s_closure = _state(turn=10, my_prizes=2, op_prizes=4,
                           options=[attack_opt], active_energy=2)

        from ptcg_agent.features.phase import detect_phase, GamePhase
        from ptcg_agent.policies.heuristic import _PHASE_WEIGHTS, _score_main, _resolve_card_ids
        from ptcg_agent.features import action_features as af

        open_phase    = detect_phase(s_open)
        closure_phase = detect_phase(s_closure)

        resolved_open    = _resolve_card_ids([attack_opt], s_open)[0]
        resolved_closure = _resolve_card_ids([attack_opt], s_closure)[0]

        score_open    = _score_main(resolved_open,    s_open,    open_phase)
        score_closure = _score_main(resolved_closure, s_closure, closure_phase)

        assert score_closure > score_open


# ---------------------------------------------------------------------------
# 3. Veto logic
# ---------------------------------------------------------------------------

class TestVetoLogic:

    def test_switch_to_naked_bench_is_penalised(self):
        """Switch card when bench has no energy should score below end_turn."""
        hand = [{"id": 1123}]  # Switch card in hand
        opts = [
            {"type": 14},               # END
            {"type": 7, "index": 0},    # PLAY Switch
        ]
        naked_bench = [_poke(677, energies=0)]   # Riolu with no energy
        s = _state(options=opts, hand=hand, bench=naked_bench)
        result = get_action(s)
        assert result[0] == 0   # END preferred over Switch to naked bench

    def test_switch_to_energised_bench_is_preferred(self):
        """Switch card when bench has energy should score above end_turn."""
        hand = [{"id": 1123}]  # Switch card in hand
        opts = [
            {"type": 14},               # END
            {"type": 7, "index": 0},    # PLAY Switch
        ]
        energised_bench = [_poke(678, energies=2)]   # Mega Lucario ex with energy
        s = _state(options=opts, hand=hand, bench=energised_bench)
        result = get_action(s)
        assert result[0] == 1   # PLAY Switch preferred

    def test_duplicate_lunatone_penalised(self):
        """Playing a second Lunatone onto field should score below end_turn."""
        hand = [{"id": 675}]  # Lunatone in hand
        opts = [
            {"type": 14},               # END
            {"type": 7, "index": 0},    # PLAY Lunatone
        ]
        # Already have a Lunatone on bench
        existing_bench = [_poke(675)]
        s = _state(options=opts, hand=hand, bench=existing_bench)
        result = get_action(s)
        assert result[0] == 0   # END preferred — don't bench a 2nd Lunatone

    def test_energy_attach_on_riolu_preferred_over_lunatone(self):
        """Attaching energy to Riolu should score higher than to Lunatone."""
        riolu   = _poke(677, energies=0)
        lunatone = _poke(675, energies=0)
        opts = [
            {"type": 8, "index": 0, "inPlayArea": 4, "inPlayIndex": 0,  # Riolu on bench[0]
             "_card_id": 6},
            {"type": 8, "index": 0, "inPlayArea": 4, "inPlayIndex": 1,  # Lunatone on bench[1]
             "_card_id": 6},
        ]
        s = _state(options=opts, bench=[riolu, lunatone], max_count=1)
        result = get_action(s)
        assert result[0] == 0   # Attach to Riolu preferred


# ---------------------------------------------------------------------------
# 4. Non-MAIN contexts
# ---------------------------------------------------------------------------

class TestNonMainContexts:

    def test_setup_active_prefers_riolu_over_makuhita(self):
        """In SETUP_ACTIVE context, Riolu scores above Makuhita."""
        # Options are CARD type pointing to hand
        hand = [{"id": 673}, {"id": 677}]   # Makuhita(0), Riolu(1)
        opts = [
            {"type": 3, "area": 2, "index": 0, "playerIndex": 0},  # Makuhita
            {"type": 3, "area": 2, "index": 1, "playerIndex": 0},  # Riolu
        ]
        s = _state(options=opts, context_id=1, max_count=1, hand=hand)
        result = get_action(s)
        assert result[0] == 1   # Riolu preferred as Active

    def test_to_hand_avoids_duplicate_lunatone(self):
        """TO_HAND context should not pick Lunatone if one already on field."""
        # bench already has Lunatone
        bench = [_poke(675)]
        hand = [{"id": 675}, {"id": 677}]
        opts = [
            {"type": 3, "area": 1, "index": 0, "playerIndex": 0},  # Lunatone
            {"type": 3, "area": 1, "index": 1, "playerIndex": 0},  # Riolu
        ]
        s = _state(options=opts, context_id=7, max_count=1,
                   hand=hand, bench=bench)
        result = get_action(s)
        assert result[0] == 1   # Riolu preferred; Lunatone already on field

    def test_to_hand_picks_energy_when_not_attached(self):
        """TO_HAND should prefer Fighting Energy when none attached yet."""
        bench = []
        hand  = [{"id": 6}, {"id": 1102}]   # Energy, Dusk Ball
        opts = [
            {"type": 3, "area": 1, "index": 0, "playerIndex": 0},  # Energy
            {"type": 3, "area": 1, "index": 1, "playerIndex": 0},  # Dusk Ball
        ]
        s = _state(options=opts, context_id=7, max_count=1,
                   hand=hand, energy_attached=False)
        result = get_action(s)
        assert result[0] == 0   # Energy preferred when not yet attached


# ---------------------------------------------------------------------------
# 5. Endgame behaviour
# ---------------------------------------------------------------------------

class TestEndgameBehaviour:

    def test_boss_orders_valued_highly_in_closure_with_ex_on_bench(self):
        """Boss's Orders should outscore end_turn in closure when op has an EX benched."""
        hand = [{"id": 1182}]  # Boss's Orders
        # Opponent has Mega Lucario ex on bench (is_mega_ex=True)
        op_bench_ex = _poke(678, is_mega_ex=True)

        opts = [
            {"type": 14},               # END
            {"type": 7, "index": 0},    # PLAY Boss's Orders
        ]
        s = _state(
            turn=10, my_prizes=2, op_prizes=4,
            options=opts, hand=hand,
        )
        # Manually attach opponent bench EX
        s.opp.bench = [op_bench_ex]
        result = get_action(s)
        assert result[0] == 1   # Boss's Orders chosen

    def test_attack_chosen_over_end_in_closure(self):
        opts = [
            {"type": 14},                         # END
            {"type": 13, "attackId": 100},        # ATTACK
        ]
        s = _state(turn=10, my_prizes=1, op_prizes=3,
                   options=opts, active_energy=2)
        result = get_action(s)
        assert result[0] == 1   # ATTACK

    def test_lillie_preferred_over_end_with_small_hand(self):
        """Lillie's Determination should beat end_turn when hand is small."""
        hand = [{"id": 1227}]  # Lillie's Determination
        opts = [
            {"type": 14},               # END
            {"type": 7, "index": 0},    # PLAY Lillie
        ]
        s = _state(options=opts, hand=hand, hand_count=2)   # small hand
        result = get_action(s)
        assert result[0] == 1   # Lillie preferred


# ---------------------------------------------------------------------------
# 6. Direct tests for policies/baseline.py
# ---------------------------------------------------------------------------

class TestBaselinePolicy:
    """Direct verification of S1 policies/baseline.py."""

    def test_baseline_empty_options(self):
        from ptcg_agent.policies.baseline import get_action as baseline_act
        s = _state(options=[], max_count=0)
        assert baseline_act(s) == []

    def test_baseline_prefers_attack(self):
        from ptcg_agent.policies.baseline import get_action as baseline_act
        opts = [
            {"type": 14},                    # END
            {"type": 13, "attackId": 42},   # ATTACK
        ]
        s = _state(options=opts, max_count=1)
        assert baseline_act(s) == [1]

    def test_baseline_first_legal_when_no_attack(self):
        from ptcg_agent.policies.baseline import get_action as baseline_act
        opts = [
            {"type": 7, "index": 0},
            {"type": 14},
        ]
        s = _state(options=opts, max_count=1)
        assert baseline_act(s) == [0]

    def test_baseline_multiple_count(self):
        from ptcg_agent.policies.baseline import get_action as baseline_act
        opts = [
            {"type": 3, "index": 0},
            {"type": 3, "index": 1},
            {"type": 3, "index": 2},
            {"type": 3, "index": 3},
        ]
        s = _state(options=opts, max_count=3)
        assert baseline_act(s) == [0, 1, 2]
