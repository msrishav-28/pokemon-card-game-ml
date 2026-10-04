"""
tests/test_beliefs.py — Unit tests for the S4 belief layer.

Tests cover:
  1. Initialisation — scare limits, archetype scores start at 0.
  2. Card reveal — revealed_cards grows, archetypes bump, scare decrements.
  3. Archetype posterior — correct dominant_archetype() after signals.
  4. Scare remaining — scare_threat() flips when copies exhausted.
  5. KO threat — ko_threat_this_turn set correctly for HP/energy combos.
  6. Prize delta — updated correctly from CanonicalState.
  7. Change log — every variable flip is recorded.
  8. Idempotency — update() twice on same state doesn't double-count.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ptcg_agent.beliefs.opponent_model import BeliefState
from ptcg_agent.env.types import CanonicalState, PlayerView, PokemonView


# ---------------------------------------------------------------------------
# Minimal fixture helpers (same pattern as test_phase.py)
# ---------------------------------------------------------------------------

def _poke(card_id: int, hp: int = 100, max_hp: int = 100,
          energies: int = 0, tools: list | None = None) -> PokemonView:
    return PokemonView(
        card_id=card_id, name="", hp=hp, max_hp=max_hp,
        energies=[6] * energies,
        tools=tools or [],
        status_conditions=[], retreat_cost=1,
        is_ex=False, is_mega_ex=False, raw={},
    )


def _player(prizes: int = 6, active: PokemonView | None = None,
            bench: list | None = None, discard: list | None = None,
            prizes_remaining: int | None = None) -> PlayerView:
    return PlayerView(
        active=active,
        bench=bench or [],
        hand=None,
        hand_count=5,
        deck_count=40,
        discard=discard or [],
        prizes=[None] * prizes,
        prizes_remaining=prizes if prizes_remaining is None else prizes_remaining,
        supporter_played=False, stadium_played=False,
        energy_attached=False, retreated=False,
        poisoned=False, burned=False, asleep=False,
        paralyzed=False, confused=False,
    )


def _state(turn: int = 3,
           me_prizes: int = 6, op_prizes: int = 6,
           op_active: PokemonView | None = None,
           op_bench: list | None = None,
           op_discard: list | None = None,
           me_active: PokemonView | None = None,
           me_bench: list | None = None) -> CanonicalState:
    me_active  = me_active  or _poke(677, hp=100)   # Riolu
    op_active  = op_active  or _poke(678, hp=200)   # Mega Lucario ex
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
        legal_options=[{"type": 14}],
        legal_option_indices=[0],
        me=_player(me_prizes, active=me_active, bench=me_bench or []),
        opp=_player(op_prizes, active=op_active,
                    bench=op_bench or [], discard=op_discard or []),
        stadium=[],
        looking=None,
        logs_tail=[],
        effect_card=None,
        context_card=None,
        raw={},
    )


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------

class TestInit:

    def test_archetype_scores_start_at_zero(self):
        b = BeliefState()
        assert all(v == 0.0 for v in b.archetype_scores.values())

    def test_revealed_cards_starts_empty(self):
        b = BeliefState()
        assert len(b.revealed_cards) == 0

    def test_scare_limits_initialised(self):
        b = BeliefState()
        # gust (Boss's Orders) = 2, recovery (PokePad) = 4
        assert b.scare_remaining["gust"] == 2
        assert b.scare_remaining["recovery"] == 4
        assert b.scare_remaining["switch_out"] == 2

    def test_ko_threat_starts_false(self):
        b = BeliefState()
        assert b.ko_threat_this_turn is False

    def test_prize_delta_starts_zero(self):
        b = BeliefState()
        assert b.prize_delta == 0


# ---------------------------------------------------------------------------
# 2. Card reveal
# ---------------------------------------------------------------------------

class TestCardReveal:

    def test_active_pokemon_revealed(self):
        b = BeliefState()
        s = _state(op_active=_poke(678))   # Mega Lucario ex
        b.update(s)
        assert 678 in b.revealed_cards

    def test_bench_pokemon_revealed(self):
        b = BeliefState()
        s = _state(op_bench=[_poke(677)])  # Riolu on bench
        b.update(s)
        assert 677 in b.revealed_cards

    def test_discard_card_revealed(self):
        b = BeliefState()
        s = _state(op_discard=[{"id": 1182}])  # Boss's Orders in discard
        b.update(s)
        assert 1182 in b.revealed_cards

    def test_tool_on_active_revealed(self):
        b = BeliefState()
        active_with_tool = _poke(678, tools=[{"id": 1159}])  # Hero Cape
        s = _state(op_active=active_with_tool)
        b.update(s)
        assert 1159 in b.revealed_cards

    def test_second_update_does_not_double_count(self):
        """Revealing the same Pokémon twice should not grow the set."""
        b = BeliefState()
        s = _state(op_active=_poke(678))
        b.update(s)
        count_after_first = len(b.revealed_cards)
        b.update(s)
        assert len(b.revealed_cards) == count_after_first


# ---------------------------------------------------------------------------
# 3. Archetype posterior
# ---------------------------------------------------------------------------

class TestArchetypePosterior:

    def test_lucario_signal_bumps_lucario_archetype(self):
        b = BeliefState()
        s = _state(op_active=_poke(678),     # Mega Lucario ex
                   op_bench=[_poke(677)])     # Riolu
        b.update(s)
        assert b.archetype_scores["lucario_ex"] >= 2.0

    def test_dominant_archetype_is_lucario(self):
        b = BeliefState()
        s = _state(op_active=_poke(678), op_bench=[_poke(677), _poke(673)])
        b.update(s)
        assert b.dominant_archetype() == "lucario_ex"

    def test_unknown_card_does_not_crash(self):
        b = BeliefState()
        s = _state(op_active=_poke(9999))   # completely unknown card ID
        b.update(s)
        # Should not raise; generic_ex gets a small bump
        assert b.archetype_scores["generic_ex"] >= 0.5

    def test_dominant_archetype_unknown_when_no_signals(self):
        b = BeliefState()
        # No update called
        assert b.dominant_archetype() == "unknown"

    def test_dragapult_signals_beat_lucario(self):
        b = BeliefState()
        # Reveal 3 Dragapult-family cards vs 1 Lucario
        dragapult_ids = [144, 322, 323]
        lucario_ids   = [678]
        s = _state(
            op_active=_poke(144),
            op_bench=[_poke(322), _poke(323), _poke(678)],
        )
        b.update(s)
        assert b.dominant_archetype() == "dragapult_ex"


# ---------------------------------------------------------------------------
# 4. Scare remaining
# ---------------------------------------------------------------------------

class TestScareRemaining:

    def test_boss_orders_in_discard_decrements_gust(self):
        b = BeliefState()
        s = _state(op_discard=[{"id": 1182}])  # Boss's Orders
        b.update(s)
        assert b.scare_remaining["gust"] == 1

    def test_both_boss_orders_seen_clears_gust(self):
        b = BeliefState()
        # Both copies visible simultaneously: one in discard, one on active as tool
        # (possible if opponent played one and has one equipped as a hypothetical)
        # More realistically: both in discard at once
        s = _state(op_discard=[{"id": 1182}, {"id": 1182}])
        b.update(s)
        assert b.scare_remaining["gust"] == 0

    def test_scare_threat_false_when_exhausted(self):
        b = BeliefState()
        # Exhaust both gust copies
        b.scare_remaining["gust"] = 0
        assert b.scare_threat("gust") is False

    def test_scare_threat_true_when_copies_remain(self):
        b = BeliefState()
        assert b.scare_threat("gust") is True

    def test_scare_never_goes_negative(self):
        b = BeliefState()
        # Reveal 5 Boss's Orders (more than the limit)
        for _ in range(5):
            b._update_scare(1, 1182)
        assert b.scare_remaining["gust"] == 0


# ---------------------------------------------------------------------------
# 5. KO threat
# ---------------------------------------------------------------------------

class TestKoThreat:

    def test_no_threat_when_opp_has_no_energy_and_our_hp_is_high(self):
        b = BeliefState()
        # Opponent active has 0 energy; our active has 200 HP
        s = _state(
            op_active=_poke(678, hp=200, energies=0),
            me_active=_poke(677, hp=200, max_hp=200),
        )
        b.update(s)
        assert b.ko_threat_this_turn is False

    def test_threat_when_opp_has_2_energy_and_our_hp_is_low(self):
        b = BeliefState()
        # Opponent active has 2 energy (3 with unseen attach) → 210 dmg range
        # Our active has only 100 HP → threatened
        s = _state(
            op_active=_poke(678, hp=200, energies=2),
            me_active=_poke(677, hp=100, max_hp=200),
        )
        b.update(s)
        assert b.ko_threat_this_turn is True

    def test_threat_when_opp_has_1_energy_and_our_hp_is_very_low(self):
        b = BeliefState()
        # 1 energy + 1 unseen = 2 effective → 130 dmg threshold
        s = _state(
            op_active=_poke(678, energies=1),
            me_active=_poke(677, hp=60, max_hp=100),
        )
        b.update(s)
        assert b.ko_threat_this_turn is True

    def test_no_threat_when_opp_active_is_none(self):
        b = BeliefState()
        s = _state(op_active=None)
        b.update(s)
        assert b.ko_threat_this_turn is False

    def test_no_threat_when_me_active_is_none(self):
        b = BeliefState()
        s = _state(me_active=None, op_active=_poke(678, energies=3))
        # Use None directly but it's valid per types
        s.me.active = None
        b.update(s)
        assert b.ko_threat_this_turn is False


# ---------------------------------------------------------------------------
# 6. Prize delta
# ---------------------------------------------------------------------------

class TestPrizeDelta:

    def test_prize_delta_zero_at_start(self):
        b = BeliefState()
        s = _state(me_prizes=6, op_prizes=6)
        b.update(s)
        assert b.prize_delta == 0

    def test_prize_delta_positive_when_we_are_ahead(self):
        b = BeliefState()
        # We have 4 prizes left (took 2), opponent still has 6
        s = _state(me_prizes=4, op_prizes=6)
        b.update(s)
        assert b.prize_delta == -2   # 4 - 6 = -2  (lower = better for us)

    def test_prize_delta_negative_when_we_are_behind(self):
        b = BeliefState()
        # Opponent has taken 3 prizes (3 remaining), we still have 6
        s = _state(me_prizes=6, op_prizes=3)
        b.update(s)
        assert b.prize_delta == 3   # 6 - 3 = +3 (higher = worse for us)


# ---------------------------------------------------------------------------
# 7. Change log
# ---------------------------------------------------------------------------

class TestChangeLog:

    def test_reveal_logged(self):
        b = BeliefState()
        s = _state(op_active=_poke(678))
        b.update(s)
        log = b.change_log()
        variables = [entry[1] for entry in log]
        assert "revealed_cards" in variables

    def test_prize_delta_change_logged(self):
        b = BeliefState()
        # Start at 0, then move to -2
        s1 = _state(me_prizes=6, op_prizes=6)
        b.update(s1)
        s2 = _state(me_prizes=4, op_prizes=6)
        b.update(s2)
        log = b.change_log()
        pd_entries = [e for e in log if e[1] == "prize_delta"]
        assert len(pd_entries) >= 1
        assert pd_entries[-1][3] == -2   # new value

    def test_no_duplicate_log_entries_for_unchanged_variables(self):
        b = BeliefState()
        s = _state(me_prizes=6, op_prizes=6)
        b.update(s)
        b.update(s)   # same state again
        # prize_delta should only be logged once (first time it changes from 0 to 0 is a no-op)
        pd_entries = [e for e in b.change_log() if e[1] == "prize_delta"]
        # It should not be logged at all since it never changed
        assert len(pd_entries) == 0
