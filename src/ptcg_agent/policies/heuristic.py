"""
policies/heuristic.py — Heuristic tactical policy (S3/S4).

Design
------
1. Resolve hand card IDs onto each option dict once (key: "_card_id").
2. Apply phase-sensitive feature weights to the 6 families from
   action_features.py.
3. For non-MAIN contexts (TO_HAND, SWITCH, SETUP, ATTACH_FROM, …) use
   targeted sub-scorers that mirror the buddy reference agent.
4. Accept an optional BeliefState (S4); when present, two belief variables
   can flip action order:
     - ko_threat_this_turn: raises risk penalty on RETREAT (stabilize first).
     - scare_threat("gust"): raises Boss's Orders endgame bonus when gusts
       may still be live in the opponent's hand.
5. Return the top-N option indices (N == state.select_max_count).

All option scoring is pure; no global mutable state is needed here
because CanonicalState already captures energyAttached / supporterPlayed.
"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ptcg_agent.beliefs.opponent_model import BeliefState

from ptcg_agent.env.types import CanonicalState, PokemonView
from ptcg_agent.features.phase import detect_phase, GamePhase
from ptcg_agent.features import action_features as af

# Re-export deck constants for tests
from ptcg_agent.features.action_features import (
    MAKUHITA, HARIYAMA, LUNATONE, SOLROCK, RIOLU, MEGA_LUCARIO_EX,
    DUSK_BALL, SWITCH_CARD, PREMIUM_POWER, FIGHTING_GONG, POKE_PAD,
    HERO_CAPE, BOSS_ORDERS, CARMINE, LILLIE_DET, GRAVITY_MTN,
    FIGHTING_ENERGY,
    BASICS, STAGE1S, ATTACKERS, SUPPORTERS,
    OPT_NUMBER, OPT_YES, OPT_NO, OPT_CARD, OPT_PLAY, OPT_ATTACH,
    OPT_EVOLVE, OPT_ABILITY, OPT_RETREAT, OPT_ATTACK, OPT_END,
    AREA_ACTIVE, AREA_BENCH,
    ATTACK_MEGA_BRAVE,
    _field_pokemon, _field_ids, _hand_counts, _discard_counts,
    _op_field_pokemon, _prize_value, _pokemon_by_area_idx,
    _attacker1_ready, _attacker2_ready, _can_attack,
)

# SelectContext IDs (from adapter.SELECT_CONTEXT_NAMES)
CTX_MAIN              = 0
CTX_SETUP_ACTIVE      = 1
CTX_SETUP_BENCH       = 2
CTX_SWITCH            = 3
CTX_TO_ACTIVE         = 4
CTX_TO_HAND           = 7
CTX_ATTACH_FROM       = 21


import os
import yaml

# ---------------------------------------------------------------------------
# Phase weights
# ---------------------------------------------------------------------------
# Each entry maps (feature_name -> multiplier) for a given phase.
# Loaded from configs/weights/heuristic_v1.yaml, with hardcoded defaults as fallback.

_DEFAULT_PHASE_WEIGHTS: dict[GamePhase, dict[str, float]] = {
    GamePhase.OPENING: {
        "prize_race": 0.3,
        "tempo":      1.5,
        "board":      2.0,
        "resources":  1.5,
        "risk":       1.2,
        "endgame":    0.1,
    },
    GamePhase.DEVELOPMENT: {
        "prize_race": 0.6,
        "tempo":      1.4,
        "board":      1.6,
        "resources":  1.2,
        "risk":       1.0,
        "endgame":    0.2,
    },
    GamePhase.PRESSURE: {
        "prize_race": 1.4,
        "tempo":      1.2,
        "board":      0.8,
        "resources":  0.9,
        "risk":       1.0,
        "endgame":    0.5,
    },
    GamePhase.PRIZE_CONVERSION: {
        "prize_race": 1.6,
        "tempo":      1.0,
        "board":      0.7,
        "resources":  0.8,
        "risk":       1.1,
        "endgame":    1.2,
    },
    GamePhase.STABILIZATION: {
        "prize_race": 0.8,
        "tempo":      1.3,
        "board":      1.4,
        "resources":  1.4,
        "risk":       1.5,
        "endgame":    0.3,
    },
    GamePhase.CLOSURE: {
        "prize_race": 1.8,
        "tempo":      0.7,
        "board":      0.4,
        "resources":  0.6,
        "risk":       0.8,
        "endgame":    2.5,
    },
}

def _load_phase_weights() -> dict[GamePhase, dict[str, float]]:
    weights = {k: dict(v) for k, v in _DEFAULT_PHASE_WEIGHTS.items()}
    yaml_candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "configs", "weights", "heuristic_v1.yaml"),
        "configs/weights/heuristic_v1.yaml",
        "/kaggle_simulations/agent/configs/weights/heuristic_v1.yaml",
    ]
    for path in yaml_candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    name_map = {
                        "opening": GamePhase.OPENING,
                        "development": GamePhase.DEVELOPMENT,
                        "pressure": GamePhase.PRESSURE,
                        "prize_conversion": GamePhase.PRIZE_CONVERSION,
                        "stabilization": GamePhase.STABILIZATION,
                        "closure": GamePhase.CLOSURE,
                    }
                    for name, w_dict in data.items():
                        gp = name_map.get(name.lower())
                        if gp and isinstance(w_dict, dict):
                            weights[gp].update(w_dict)
                break
            except Exception:
                pass
    return weights

_PHASE_WEIGHTS: dict[GamePhase, dict[str, float]] = _load_phase_weights()



# ---------------------------------------------------------------------------
# Card ID resolution
# ---------------------------------------------------------------------------

def _resolve_card_ids(options: list[dict], state: CanonicalState) -> list[dict]:
    """
    Return a shallow copy of each option dict with "_card_id" injected.

    For PLAY options the card comes from our hand (by index).
    For ATTACH options the card comes from our hand (by index) too.
    Other options get _card_id=0.
    """
    hand = state.me.hand or []
    resolved = []
    for opt in options:
        o = dict(opt)  # shallow copy — don't mutate the original
        opt_type = o.get("type")
        card_id = 0

        if opt_type in (OPT_PLAY, OPT_ATTACH):
            idx = o.get("index", -1)
            if 0 <= idx < len(hand):
                card = hand[idx]
                card_id = card.get("id", 0) if isinstance(card, dict) else 0

        o["_card_id"] = card_id
        resolved.append(o)
    return resolved


# ---------------------------------------------------------------------------
# Context-specific scorers (non-MAIN)
# ---------------------------------------------------------------------------

def _score_card_option(opt: dict, state: CanonicalState, context_id: int | None) -> float:
    """Score a CARD option (selecting a specific card from an area)."""
    area       = opt.get("area", -1)
    idx        = opt.get("index", 0)
    player_idx = opt.get("playerIndex", state.your_index)
    is_mine    = (player_idx == state.your_index)

    pokemon = _pokemon_by_area_idx(state, area, idx, player_mine=is_mine)
    n_energy = len(pokemon.energies) if pokemon else 0
    card_id  = pokemon.card_id if pokemon else 0

    # For hand/deck/discard areas (not ACTIVE=3, BENCH=4), resolve card_id
    # from the hand list directly — pokemon lookup only works for in-play areas.
    if card_id == 0 and is_mine and area not in (AREA_ACTIVE, AREA_BENCH):
        hand = state.me.hand or []
        if 0 <= idx < len(hand):
            c = hand[idx]
            card_id = c.get("id", 0) if isinstance(c, dict) else 0

    field_counts = _field_ids(state)
    hand_counts  = _hand_counts(state)
    my_prizes    = state.me.prizes_remaining

    # --- SWITCH / TO_ACTIVE: selecting who comes to Active ---
    if context_id in (CTX_SWITCH, CTX_TO_ACTIVE):
        if is_mine:
            score = n_energy * 20.0
            if card_id == MEGA_LUCARIO_EX:
                score += 200.0 if my_prizes <= 3 else 80.0
            elif card_id == HARIYAMA and n_energy >= 2:
                score += 60.0
            elif card_id == MAKUHITA and n_energy >= 2:
                score += 40.0
            elif card_id == SOLROCK:
                score += 20.0
            elif card_id == RIOLU:
                score += 16.0
        else:
            # Selecting opponent target (Boss's Orders, etc.)
            # Prefer high-prize benched EX targets
            score = _prize_value(card_id) * 80.0
        return score

    # --- SETUP_ACTIVE_POKEMON: first Pokémon placed as Active ---
    if context_id == CTX_SETUP_ACTIVE:
        # Solrock first if we go first (can use Ability); else Riolu
        if card_id == SOLROCK:
            return 40.0 if state.first_player == state.your_index else 80.0
        if card_id == RIOLU:
            return 70.0
        if card_id == MAKUHITA:
            return 50.0
        return 20.0

    # --- TO_HAND: selecting cards to take into hand (e.g. Lillie's Det) ---
    if context_id == CTX_TO_HAND:
        score = 200.0 - hand_counts.get(card_id, 0) * 100.0
        # Prioritise cards we need but don't have on field
        if card_id == MAKUHITA:
            score += 10.0 if field_counts.get(MAKUHITA, 0) == 0 else -10.0
        elif card_id == HARIYAMA:
            score += 20.0 if field_counts.get(MAKUHITA, 0) >= 1 else -20.0
        elif card_id == LUNATONE:
            score += 60.0 if field_counts.get(LUNATONE, 0) == 0 else -250.0
        elif card_id == SOLROCK:
            score += 50.0 if field_counts.get(SOLROCK, 0) == 0 else -250.0
        elif card_id == RIOLU:
            riolu_lucario = (field_counts.get(RIOLU, 0)
                             + field_counts.get(MEGA_LUCARIO_EX, 0))
            if riolu_lucario >= 2:
                score -= 150.0
            elif riolu_lucario >= 1:
                score -= 3.0
            else:
                score += 40.0
        elif card_id == MEGA_LUCARIO_EX:
            score += 40.0 if field_counts.get(RIOLU, 0) >= 1 else -15.0
        elif card_id == FIGHTING_ENERGY:
            score += 30.0 if not state.me.energy_attached else -1.0
        return score

    # --- ATTACH_FROM: selecting which Pokémon to attach energy TO ---
    if context_id == CTX_ATTACH_FROM:
        is_active = (area == AREA_ACTIVE)
        return af.tempo({"type": OPT_ATTACH, "inPlayArea": area,
                         "inPlayIndex": idx, "_card_id": FIGHTING_ENERGY},
                        state)

    return float(n_energy)   # generic fallback: prefer more energy


# ---------------------------------------------------------------------------
# MAIN context scorer
# ---------------------------------------------------------------------------

def _score_main(opt: dict, state: CanonicalState, phase: GamePhase,
                belief: "BeliefState | None" = None) -> float:
    """Score one option in the MAIN context using weighted feature families."""
    weights = _PHASE_WEIGHTS.get(phase, {})

    def w(name: str) -> float:
        return weights.get(name, 1.0)

    pr  = af.prize_race(opt, state) * w("prize_race")
    te  = af.tempo(opt, state)      * w("tempo")
    bo  = af.board(opt, state)      * w("board")
    re  = af.resources(opt, state)  * w("resources")
    ri  = af.risk(opt, state)       * w("risk")
    eg  = af.endgame(opt, state)    * w("endgame")

    base = pr + te + bo + re + ri + eg

    opt_type = opt.get("type")

    # ---- Belief-aware adjustments (S4) ----
    if belief is not None:
        if opt_type == OPT_RETREAT:
            # If opponent has a live KO threat, retreating may be necessary
            # even into a naked bench — reduce the risk penalty.
            if belief.ko_threat_this_turn:
                base += 60.0   # override risk penalty; we NEED to get out

        if opt_type == OPT_PLAY:
            card_id = opt.get("_card_id", 0)
            if card_id == BOSS_ORDERS:
                # If opponent still has gust cards live, using ours first
                # for a lethal pull is even more valuable (tempo mirror).
                if belief.scare_threat("gust") and state.me.prizes_remaining <= 3:
                    base += 80.0   # belief-driven endgame bonus

    # ---- Special flat bonuses / overrides in MAIN context ----

    if opt_type == OPT_PLAY:
        card_id = opt.get("_card_id", 0)

        # Pokémon play: always consider unless flagged negative by board()
        if card_id in BASICS:
            # board() already scored it; just pass through
            pass

        # Switch: only if we have a meaningful bench target
        elif card_id == SWITCH_CARD:
            bench = state.me.bench
            has_energised_bench = any(len(p.energies) > 0 for p in bench)
            if not has_energised_bench:
                base = -100.0   # hard veto: switching to naked bench is waste
            else:
                # Positive score: switching to a charged attacker is a tempo play
                best_bench_energy = max((len(p.energies) for p in bench), default=0)
                base = 30.0 + best_bench_energy * 15.0

        # Gravity Mountain: only if no stadium up already
        elif card_id == GRAVITY_MTN:
            if not state.stadium:
                base += 20.0
            else:
                base = -50.0   # don't replace existing stadium

    elif opt_type == OPT_EVOLVE:
        # Evolving is almost always correct in MAIN; give it a strong floor
        base = max(base, 90.0)

    elif opt_type == OPT_ATTACK:
        # Attacking is the primary win condition — give it a strong floor
        base = max(base, 100.0)

    elif opt_type == OPT_END:
        # Ending turn when we could attack or evolve is bad — but valid
        base = 0.0

    elif opt_type == OPT_ABILITY:
        # Abilities are almost always worth using (Solrock/Lunatone)
        base = max(base, 300.0)

    return base


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_action(state: CanonicalState,
               belief: "BeliefState | None" = None,
               return_details: bool = False) -> list[int] | tuple[list[int], list[float], list[dict]]:
    """
    Return a list of option indices for the current selection.

    Length == state.select_max_count.
    All returned indices are valid (within range of state.legal_options).

    Args:
        state:          current CanonicalState (required).
        belief:         optional S4 BeliefState; caller must have called
                        belief.update(state) before passing it here.
        return_details: if True, returns (action_indices, scores, features).
    """
    options = state.legal_options
    max_count = state.select_max_count
    n_options = len(options)

    if not 0 <= max_count <= n_options:
        raise ValueError("cabt invariant violated: maxCount exceeds options")

    if max_count == 0:
        if return_details:
            return [], [], []
        return []

    pick = max_count

    # Resolve hand card IDs onto option copies
    resolved = _resolve_card_ids(options, state)

    # Detect phase (only used for MAIN context weighting)
    phase = detect_phase(state)
    ctx   = state.select_context_id

    # Score every option and extract feature vector
    scores: list[float] = []
    features: list[dict] = []
    for opt in resolved:
        opt_type = opt.get("type")

        if ctx == CTX_MAIN:
            score = _score_main(opt, state, phase, belief)
        elif opt_type == OPT_CARD:
            score = _score_card_option(opt, state, ctx)
        elif opt_type == OPT_NUMBER:
            score = float(opt.get("number", 0))
        elif opt_type == OPT_YES:
            score = 1.0
        elif opt_type == OPT_NO:
            score = 0.0
        elif opt_type == OPT_END:
            score = 0.0
        else:
            # For any other option in a non-MAIN context, use the full scorer
            score = af.score_option(opt, state)

        scores.append(score)
        features.append(af.feature_vector(opt, state))

    # Sort by descending score, return top-`pick` indices
    ranked = sorted(range(n_options), key=lambda i: scores[i], reverse=True)
    chosen = ranked[:pick]

    if return_details:
        return chosen, scores, features
    return chosen
