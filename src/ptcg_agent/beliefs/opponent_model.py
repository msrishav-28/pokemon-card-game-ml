"""
beliefs/opponent_model.py — S4 lightweight belief layer.

Tracks only the five variables the Bible S4 gate requires:

  1. revealed_cards   — set of card IDs the opponent has shown (played,
                        discarded, or appeared in play). Used to bound
                        remaining copies and infer archetype.
  2. archetype_scores — coarse posterior over known archetypes derived from
                        revealed_cards.  Updated every call to update().
  3. scare_remaining  — estimated remaining copies of the four "scare" card
                        categories: gust (Boss's Orders), recovery
                        (Poké Pad / Poke Pad), extra_attacker (ex bench),
                        and switch_out (Switch).  Starts at the max plausible
                        count and decrements when a copy is revealed.
  4. ko_threat_this_turn — True if the opponent's active Pokémon has enough
                           energy in play to KO our active this turn, given the
                           energy on field and one possible unseen attach.
  5. prize_delta      — (our prizes remaining) − (their prizes remaining).
                        Positive = we are ahead, negative = behind.

Design constraints (Bible S4):
- No full Bayesian hand enumeration.
- Start with one consistent guessed world.
- The belief object is stateful (call update() once per obs before get_action).
- Belief changes are logged so L7 (replays as debugger) can reconstruct them.
- Latency budget: update() must be O(cards_in_play), not O(deck_permutations).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from ptcg_agent.env.types import CanonicalState, PokemonView


# ---------------------------------------------------------------------------
# Archetype catalogue (coarse; tuned for the known Standard pool subset)
# ---------------------------------------------------------------------------
# Each entry: archetype_name -> frozenset of card IDs that are strong signals.
# A reveal of any signal card bumps that archetype's score.

_ARCHETYPE_SIGNALS: dict[str, frozenset[int]] = {
    "lucario_ex":    frozenset({678, 677, 673, 674}),   # Mega Lucario ex / Riolu / Makuhita / Hariyama
    "dragapult_ex":  frozenset({144, 322, 323, 337}),   # common Dragapult family IDs (buddy comment)
    "pikachu_ex":    frozenset({25, 26, 104}),          # placeholder Pikachu family
    "charizard_ex":  frozenset({6, 5, 4, 105}),         # placeholder Charizard family
    "generic_ex":    frozenset(),                        # fallback for revealed ex cards
}

# Scare card IDs and their max deck count (conservative upper bound)
_SCARE_CARD_LIMITS: dict[str, tuple[frozenset[int], int]] = {
    "gust":           (frozenset({1182}),         2),   # Boss's Orders x2
    "recovery":       (frozenset({1152}),         4),   # Poké Pad x4
    "extra_attacker": (frozenset({678, 144}),     4),   # 2 Mega Lucario ex + 2 unknown EX
    "switch_out":     (frozenset({1123, 1124}),   2),   # Switch x2
}


# ---------------------------------------------------------------------------
# BeliefState
# ---------------------------------------------------------------------------

@dataclass
class BeliefState:
    """
    Mutable belief about the opponent's hidden state.

    Create once per game, call update(state) on every obs before scoring.
    """
    # Tracking
    revealed_cards:   set[int]          = field(default_factory=set)
    archetype_scores: dict[str, float]  = field(default_factory=dict)
    scare_remaining:  dict[str, int]    = field(default_factory=dict)

    # Derived booleans (recomputed each update)
    ko_threat_this_turn: bool = False
    prize_delta:          int = 0   # our_prizes - their_prizes; + = we lead

    # Change log — list of (turn, variable, old_value, new_value)
    _change_log: list[tuple[int, str, Any, Any]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        # Initialise archetype scores to 0
        for name in _ARCHETYPE_SIGNALS:
            self.archetype_scores[name] = 0.0
        # Initialise scare remaining to upper bounds
        for name, (_, limit) in _SCARE_CARD_LIMITS.items():
            self.scare_remaining[name] = limit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, state: CanonicalState) -> None:
        """
        Ingest the current CanonicalState and update all belief variables.

        Call once per turn, before get_action().
        """
        turn = state.turn

        # 1. Collect ALL currently visible opponent card IDs (with counts)
        #    so we can track multiple copies of the same card.
        current_visible = self._collect_revealed_with_counts(state)

        # Add newly-seen card IDs to the revealed set (for archetype inference)
        for cid in current_visible:
            if cid not in self.revealed_cards:
                self._log(turn, "revealed_cards", None, cid)
                self.revealed_cards.add(cid)
                self._update_archetypes(cid)

        # Update scare remaining based on maximum observed count per card ID.
        # We store the running maximum of how many copies have been visible
        # simultaneously, and decrement the limit by that max.
        self._update_scare_from_counts(turn, current_visible)

        # 2. Recompute KO threat
        old_ko = self.ko_threat_this_turn
        new_ko = self._compute_ko_threat(state)
        if new_ko != old_ko:
            self._log(turn, "ko_threat_this_turn", old_ko, new_ko)
        self.ko_threat_this_turn = new_ko

        # 3. Recompute prize delta
        old_pd = self.prize_delta
        new_pd = state.me.prizes_remaining - state.opp.prizes_remaining
        if new_pd != old_pd:
            self._log(turn, "prize_delta", old_pd, new_pd)
        self.prize_delta = new_pd

    def dominant_archetype(self) -> str:
        """Return the archetype with the highest score, or 'unknown'."""
        if not self.archetype_scores:
            return "unknown"
        best = max(self.archetype_scores, key=lambda k: self.archetype_scores[k])
        return best if self.archetype_scores[best] > 0 else "unknown"

    def scare_threat(self, category: str) -> bool:
        """True if at least one copy of this scare category may remain."""
        return self.scare_remaining.get(category, 0) > 0

    def change_log(self) -> list[tuple[int, str, Any, Any]]:
        """Return the full change log for replay inspection."""
        return list(self._change_log)

    def _update_archetypes(self, card_id: int) -> None:
        """Bump archetype scores when a signal card is revealed."""
        for name, signals in _ARCHETYPE_SIGNALS.items():
            if card_id in signals:
                self.archetype_scores[name] += 1.0
        # Generic EX bump for any ex Pokémon we can't classify
        if card_id not in {c for s in _ARCHETYPE_SIGNALS.values() for c in s}:
            self.archetype_scores["generic_ex"] += 0.5

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_revealed_with_counts(self, state: CanonicalState) -> dict[int, int]:
        """
        Return {card_id: count} of all opponent cards currently visible:
        active, bench (+ tools on each), discard.
        """
        counts: dict[int, int] = {}

        def add(cid: int) -> None:
            if cid:
                counts[cid] = counts.get(cid, 0) + 1

        opp = state.opp
        if opp.active:
            add(opp.active.card_id)
            for tool in (opp.active.tools or []):
                if isinstance(tool, dict):
                    add(tool.get("id", 0))

        for p in opp.bench:
            add(p.card_id)
            for tool in (p.tools or []):
                if isinstance(tool, dict):
                    add(tool.get("id", 0))

        for card in (opp.discard or []):
            if isinstance(card, dict):
                add(card.get("id", 0))

        return counts

    # Keep the old name as an alias for tests that call it directly
    def _collect_revealed(self, state: CanonicalState) -> set[int]:
        return set(self._collect_revealed_with_counts(state).keys())

    def _update_scare_from_counts(self, turn: int,
                                  current_counts: dict[int, int]) -> None:
        """
        Update scare_remaining by counting the total number of distinct
        confirmed copies of each scare card we have ever seen.

        A new "confirmed copy" is counted when:
          - current_counts[cid] > _peak_simultaneous[cid]  (new simultaneous copy), OR
          - the card was absent last turn and appears again  (reappear = another copy)

        This covers all cases: two in discard at once, one seen then recovered
        and seen again, one in discard + one on the field in different turns.
        """
        if not hasattr(self, "_peak_simultaneous"):
            self._peak_simultaneous: dict[int, int] = {}
        if not hasattr(self, "_was_visible"):
            self._was_visible: dict[int, int] = {}   # cid -> count last turn
        if not hasattr(self, "_confirmed_seen"):
            self._confirmed_seen: dict[int, int] = {}  # cid -> total confirmed copies

        for name, (card_ids, limit) in _SCARE_CARD_LIMITS.items():
            for cid in card_ids:
                now  = current_counts.get(cid, 0)
                prev = self._was_visible.get(cid, 0)
                peak = self._peak_simultaneous.get(cid, 0)
                conf = self._confirmed_seen.get(cid, 0)

                if now > peak:
                    # More copies simultaneously than we've ever seen — all new
                    delta = now - peak
                    self._peak_simultaneous[cid] = now
                    self._confirmed_seen[cid] = conf + delta
                elif now > 0 and prev == 0:
                    # Card reappeared after being absent — at least 1 more copy
                    self._confirmed_seen[cid] = max(conf + 1,
                                                    self._confirmed_seen.get(cid, 0))

                self._was_visible[cid] = now

            total_confirmed = sum(self._confirmed_seen.get(cid, 0) for cid in card_ids)
            new_val = max(0, limit - total_confirmed)
            old_val = self.scare_remaining[name]
            if new_val != old_val:
                self._log(turn, f"scare_remaining[{name}]", old_val, new_val)
            self.scare_remaining[name] = new_val

    def _update_scare(self, turn: int, card_id: int) -> None:
        """Legacy single-card decrement (kept for tests that call directly)."""
        for name, (card_ids, _) in _SCARE_CARD_LIMITS.items():
            if card_id in card_ids:
                old = self.scare_remaining[name]
                new = max(0, old - 1)
                if new != old:
                    self._log(turn, f"scare_remaining[{name}]", old, new)
                self.scare_remaining[name] = new

    def _compute_ko_threat(self, state: CanonicalState) -> bool:
        """
        Estimate whether the opponent can KO our active this turn.

        Conservative heuristic (no full lookahead):
        - Count energy on the opponent's active Pokémon.
        - Assume they may attach one more unseen energy this turn.
        - If energy_on_attacker + 1 >= 2 (enough to use any 2-cost attack)
          AND our active HP is low (< 150), flag as threat.
        - This is intentionally conservative to avoid false negatives.
        """
        our_active = state.me.active
        if our_active is None:
            return False

        opp_active = state.opp.active
        if opp_active is None:
            return False

        opp_energy = len(opp_active.energies)
        # Assume opponent can attach one unseen energy
        effective_energy = opp_energy + 1

        # Rough damage tiers by energy count (conservative Fighting damage)
        # 1 energy: ~70-130 damage (Lucario first attack or basic)
        # 2 energy: ~130-270 damage (Mega Brave range)
        # 3 energy: ~210 damage (Hariyama)
        our_hp = our_active.hp
        our_max_hp = our_active.max_hp

        if effective_energy >= 3 and our_hp <= 210:
            return True
        if effective_energy >= 2 and our_hp <= 130:
            return True
        if effective_energy >= 1 and our_hp <= 70:
            return True

        # Bonus: if opponent has a revealed Boss's Orders and we have
        # a low-HP benched Pokémon, flag threat even if active is safe
        if not self.scare_threat("gust"):
            return False  # no gust remaining, ignore bench threat

        for p in state.me.bench:
            if p.hp <= 70 and effective_energy >= 1:
                return True

        return False

    def _log(self, turn: int, variable: str, old: Any, new: Any) -> None:
        self._change_log.append((turn, variable, old, new))
