"""
features/action_features.py — Six heuristic feature families (S3).

Each family returns a float score for one option dict given the current
CanonicalState.  The scorer in policies/heuristic.py linearly combines
them (with phase-sensitive weights) into a scalar.

Feature families
----------------
1. prize_race   — Does this action threaten a KO?  Which target is most
                  valuable?  Does it win the game outright?
2. tempo        — Does this move an energy onto the right attacker faster?
3. board        — Does this develop our board (bench basics, evolve)?
4. resources    — Does this play a supporter/item that fills hand/board?
5. risk         — Does this expose us to a bad trade (retreat into naked basic)?
6. endgame      — Does this clinch the last prize(s)?

Design principles
-----------------
- No lookahead; pure single-step feature extraction.
- All scores are real-valued.  Negative = bad, 0 = neutral, positive = good.
- Calibrated so that a strong attack scores ~300–500 and a harmless END
  scores 0 so the final sum is dominated by the best action.
- References the locked deck IDs directly (verified against configs/decks/primary.yaml).
"""
from __future__ import annotations
from typing import Any

from ptcg_agent.env.types import CanonicalState, PokemonView

# ---------------------------------------------------------------------------
# Deck constants (IDs from configs/decks/primary.yaml)
# ---------------------------------------------------------------------------
MAKUHITA        = 673
HARIYAMA        = 674
LUNATONE        = 675
SOLROCK         = 676
RIOLU           = 677
MEGA_LUCARIO_EX = 678
DUSK_BALL       = 1102
SWITCH_CARD     = 1123
PREMIUM_POWER   = 1141
FIGHTING_GONG   = 1142
POKE_PAD        = 1152
HERO_CAPE       = 1159
BOSS_ORDERS     = 1182
CARMINE         = 1192
LILLIE_DET      = 1227
GRAVITY_MTN     = 1252
FIGHTING_ENERGY = 6

# Pokémon sets for quick membership testing
BASICS     = {MAKUHITA, LUNATONE, SOLROCK, RIOLU}
STAGE1S    = {HARIYAMA, MEGA_LUCARIO_EX}
ATTACKERS  = {MAKUHITA, HARIYAMA, RIOLU, MEGA_LUCARIO_EX}
SUPPORTERS = {CARMINE, LILLIE_DET, BOSS_ORDERS, PREMIUM_POWER}
ITEMS      = {DUSK_BALL, SWITCH_CARD, FIGHTING_GONG, POKE_PAD, HERO_CAPE,
              GRAVITY_MTN}

# OptionType ints (from adapter.OPTION_TYPE_NAMES)
OPT_NUMBER   = 0
OPT_YES      = 1
OPT_NO       = 2
OPT_CARD     = 3
OPT_PLAY     = 7
OPT_ATTACH   = 8
OPT_EVOLVE   = 9
OPT_ABILITY  = 10
OPT_RETREAT  = 12
OPT_ATTACK   = 13
OPT_END      = 14

# AreaType ints from the live cabt contract (locked by fixture tests).
AREA_ACTIVE = 4
AREA_BENCH  = 5

# Lucario attack IDs (verified from buddy main.py comment: 983 = Mega Brave)
ATTACK_MEGA_BRAVE = 983   # Mega Lucario ex second attack (270 dmg, 2 energy)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hand_ids(state: CanonicalState) -> list[int]:
    """Return list of card IDs in our hand (empty if unknown)."""
    hand = state.me.hand
    if not hand:
        return []
    return [c.get("id", 0) for c in hand]


def _field_pokemon(state: CanonicalState) -> list[PokemonView]:
    """Return all of our Pokémon in play (active + bench, non-None)."""
    result: list[PokemonView] = []
    if state.me.active:
        result.append(state.me.active)
    result.extend(state.me.bench)
    return result


def _field_ids(state: CanonicalState) -> dict[int, int]:
    """Count of each card_id on our field."""
    counts: dict[int, int] = {}
    for p in _field_pokemon(state):
        counts[p.card_id] = counts.get(p.card_id, 0) + 1
    return counts


def _hand_counts(state: CanonicalState) -> dict[int, int]:
    counts: dict[int, int] = {}
    for cid in _hand_ids(state):
        counts[cid] = counts.get(cid, 0) + 1
    return counts


def _discard_counts(state: CanonicalState) -> dict[int, int]:
    counts: dict[int, int] = {}
    for c in (state.me.discard or []):
        cid = c.get("id", 0) if isinstance(c, dict) else 0
        counts[cid] = counts.get(cid, 0) + 1
    return counts


def _op_field_pokemon(state: CanonicalState) -> list[PokemonView]:
    result: list[PokemonView] = []
    if state.opp.active:
        result.append(state.opp.active)
    result.extend(state.opp.bench)
    return result


def _prize_value(card_id: int) -> int:
    """How many prizes does KO-ing this Pokémon give us?"""
    if card_id == MEGA_LUCARIO_EX:
        return 3
    if card_id in {HARIYAMA}:
        return 1  # stage1, non-ex
    if card_id in BASICS:
        return 1
    # Unknown: assume 1
    return 1


def _pokemon_by_area_idx(state: CanonicalState, area: int, idx: int,
                          player_mine: bool) -> PokemonView | None:
    """Retrieve a PokemonView by area/index for the given player."""
    pv = state.me if player_mine else state.opp
    if area == AREA_ACTIVE:
        return pv.active
    if area == AREA_BENCH:
        bench = pv.bench
        if 0 <= idx < len(bench):
            return bench[idx]
    return None


def _attacker1_ready(state: CanonicalState) -> bool:
    """True if a Riolu/Mega Lucario ex with >=2 energy is in play."""
    for p in _field_pokemon(state):
        if p.card_id in {RIOLU, MEGA_LUCARIO_EX} and len(p.energies) >= 2:
            return True
    return False


def _attacker2_ready(state: CanonicalState) -> bool:
    """True if a Makuhita/Hariyama with >=3 energy is in play."""
    for p in _field_pokemon(state):
        if p.card_id in {MAKUHITA, HARIYAMA} and len(p.energies) >= 3:
            return True
    return False


def _can_attack(state: CanonicalState) -> bool:
    return any(o.get("type") == OPT_ATTACK for o in state.legal_options)


# ---------------------------------------------------------------------------
# Feature 1: Prize Race
# ---------------------------------------------------------------------------
# Scores an option based on whether it threatens or achieves a KO on the
# most valuable opponent target.

def prize_race(option: dict, state: CanonicalState) -> float:
    """Score how well this action advances the prize race."""
    opt_type = option.get("type")

    if opt_type == OPT_ATTACK:
        # Attacking is inherently advancing the prize race.
        # We give base credit; the endgame feature handles lethal.
        active = state.me.active
        if active is None:
            return 50.0

        n_energy = len(active.energies)
        score = 50.0 + n_energy * 10.0

        # Prefer the non-Mega-Brave attack when we have 2 prizes left
        # (save the big attack for when we can one-shot something valuable)
        my_prizes = state.me.prizes_remaining
        attack_id = option.get("attackId", -1)
        if attack_id == ATTACK_MEGA_BRAVE and my_prizes > 3:
            score -= 20.0   # don't blow 2-energy attack when not needed
        elif attack_id != ATTACK_MEGA_BRAVE:
            score += 10.0   # prefer the safer/cheaper attack in mid-game

        return score

    if opt_type == OPT_RETREAT:
        # Retreating to a stronger attacker can be a prize-race move,
        # but generally doesn't advance prize race directly.
        return 0.0

    if opt_type == OPT_END:
        return 0.0

    return 0.0


# ---------------------------------------------------------------------------
# Feature 2: Tempo
# ---------------------------------------------------------------------------
# Scores whether this action gets energy onto the right attacker quickly.

def tempo(option: dict, state: CanonicalState) -> float:
    """Score how well this action builds energy tempo."""
    opt_type = option.get("type")
    a1_ready = _attacker1_ready(state)
    a2_ready = _attacker2_ready(state)

    if opt_type == OPT_ATTACH:
        # Attaching an energy
        target_area = option.get("inPlayArea", -1)
        target_idx  = option.get("inPlayIndex", 0)
        pokemon = _pokemon_by_area_idx(state, target_area, target_idx, player_mine=True)
        if pokemon is None:
            return 0.0

        n_energy = len(pokemon.energies)
        score = 80.0  # base: any attach is good

        if pokemon.card_id in {RIOLU, MEGA_LUCARIO_EX}:
            if pokemon.card_id == MEGA_LUCARIO_EX:
                score += 1.0   # prefer Mega Lucario over Riolu
            if n_energy < 2:
                score += 50.0  # actively needs energy
            if a1_ready:
                score -= 30.0  # attacker already ready; less urgent
        elif pokemon.card_id in {MAKUHITA, HARIYAMA}:
            if pokemon.card_id == HARIYAMA:
                score += 1.0
            if n_energy < 3:
                score += 50.0
            if a2_ready:
                score -= 30.0
        elif pokemon.card_id == SOLROCK:
            if n_energy < 1:
                score += 20.0  # only needs 1
            else:
                score -= 50.0  # over-energising Solrock wastes energy
        elif pokemon.card_id == LUNATONE:
            score -= 50.0  # Lunatone doesn't attack; never attach

        # Prefer active (keeps pressure up)
        if target_area == AREA_ACTIVE:
            score += 5.0

        return score

    if opt_type == OPT_PLAY:
        # Playing Fighting Gong lets us attach an extra energy this turn
        card_id = option.get("_card_id", 0)   # pre-resolved by heuristic
        if card_id == FIGHTING_GONG:
            return 40.0

    return 0.0


# ---------------------------------------------------------------------------
# Feature 3: Board
# ---------------------------------------------------------------------------
# Scores board development: benching basics, evolving, attaching tools.

def board(option: dict, state: CanonicalState) -> float:
    """Score board-development value of this action."""
    opt_type = option.get("type")
    field_counts = _field_ids(state)

    if opt_type == OPT_PLAY:
        card_id = option.get("_card_id", 0)

        # Benching a basic Pokémon
        if card_id in BASICS:
            score = 60.0

            # Avoid over-crowding with utility Pokémon
            if card_id == LUNATONE and field_counts.get(LUNATONE, 0) >= 1:
                return -50.0   # already have one, don't bench another
            if card_id == SOLROCK and field_counts.get(SOLROCK, 0) >= 1:
                return -50.0

            # Cap Riolu copies at 2 (Mega Lucario ex slots)
            riolu_lucario = (field_counts.get(RIOLU, 0)
                             + field_counts.get(MEGA_LUCARIO_EX, 0))
            if card_id == RIOLU and riolu_lucario >= 2:
                return -30.0

            # Prefer attackers
            if card_id in {MAKUHITA, RIOLU}:
                score += 20.0

            return score

        if card_id == DUSK_BALL:
            # Searches for a basic — great for board development
            return 55.0

        if card_id == HERO_CAPE:
            # Attaching Hero Cape is handled under OPT_ATTACH; skip here
            return 0.0

        if card_id == GRAVITY_MTN:
            # Stadium that helps Lucario: good, but don't overvalue
            return 20.0

    if opt_type == OPT_EVOLVE:
        # Evolving is always a board gain
        target_area = option.get("inPlayArea", -1)
        target_idx  = option.get("inPlayIndex", 0)
        pokemon = _pokemon_by_area_idx(state, target_area, target_idx, player_mine=True)
        n_energy = len(pokemon.energies) if pokemon else 0

        score = 90.0 + n_energy  # evolved Pokémon with energy is very good
        return score

    if opt_type == OPT_ATTACH:
        # Hero Cape attach: strong defensive board play
        card_id = option.get("_card_id", 0)
        if card_id == HERO_CAPE:
            target_area = option.get("inPlayArea", -1)
            target_idx  = option.get("inPlayIndex", 0)
            pokemon = _pokemon_by_area_idx(state, target_area, target_idx, player_mine=True)
            score = 70.0
            if pokemon:
                if pokemon.card_id == MEGA_LUCARIO_EX:
                    score += 20.0
                elif pokemon.card_id == RIOLU:
                    score += 10.0
            return score

    return 0.0


# ---------------------------------------------------------------------------
# Feature 4: Resources
# ---------------------------------------------------------------------------
# Scores playing supporter/item cards that refill hand or fetch key pieces.

def resources(option: dict, state: CanonicalState) -> float:
    """Score resource-generation value of this action."""
    opt_type = option.get("type")
    if opt_type != OPT_PLAY:
        return 0.0

    card_id = option.get("_card_id", 0)

    # Supporters — great, but only one per turn (engine enforces this)
    if card_id == LILLIE_DET:
        # Lillie's Determination: massive hand refill
        return 90.0

    if card_id == CARMINE:
        # Carmine: discard 2, draw 6 — strong but burns hand
        # Better early (empty hand) than late (full hand)
        hand_size = state.me.hand_count
        return max(60.0, 90.0 - hand_size * 5.0)

    if card_id == PREMIUM_POWER:
        # Premium Power Pro: draw until 6 cards — decent, context-dependent
        hand_size = state.me.hand_count
        if hand_size >= 5:
            return 10.0   # barely useful
        return 50.0

    if card_id == BOSS_ORDERS:
        # Boss's Orders: switch opponent's active — powerful but tactical
        # Scored mainly in endgame; give small resource credit here
        return 20.0

    # Items
    if card_id == DUSK_BALL:
        return 55.0   # also board, but resource gain too

    if card_id == POKE_PAD:
        # Poke Pad: look at top 3, take a Pokémon — good early
        return 40.0

    if card_id == FIGHTING_GONG:
        # Extra energy attach — strong tempo; small resource credit
        return 20.0

    return 0.0


# ---------------------------------------------------------------------------
# Feature 5: Risk
# ---------------------------------------------------------------------------
# Penalises actions that expose us to bad trades or waste resources.

def risk(option: dict, state: CanonicalState) -> float:
    """Return a penalty (negative) for risky actions."""
    opt_type = option.get("type")

    if opt_type == OPT_RETREAT:
        # Retreating to a benched Pokémon with no energy is risky —
        # we expose a naked basic that the opponent can one-shot for prizes.
        active = state.me.active
        if active is None:
            return 0.0

        # Check retreat cost feasibility (retreat_cost = 0 means unknown; allow)
        retreat_cost = active.retreat_cost
        n_active_energy = len(active.energies)
        if retreat_cost > 0 and n_active_energy < retreat_cost:
            return -80.0   # can't pay retreat cost — shouldn't be legal but penalise

        # Penalise retreating when the benched target has no energy
        # (heuristic uses bench[0] as the likely target for retreat)
        bench = state.me.bench
        if bench:
            target = bench[0]
            if len(target.energies) == 0 and target.card_id not in {SOLROCK}:
                return -40.0  # retreating into a naked basic

        return 0.0

    if opt_type == OPT_PLAY:
        card_id = option.get("_card_id", 0)
        # Playing Switch when we don't have a better target wastes the card
        if card_id == SWITCH_CARD:
            bench = state.me.bench
            if not bench:
                return -60.0   # no bench target — Switch is wasted
            # OK if at least one bench Pokémon has energy
            if any(len(p.energies) > 0 for p in bench):
                return 0.0
            return -30.0   # bench is all naked; modest penalty

    return 0.0


# ---------------------------------------------------------------------------
# Feature 6: Endgame
# ---------------------------------------------------------------------------
# Scores actions that directly win the game or lock in lethal.

def endgame(option: dict, state: CanonicalState) -> float:
    """Score endgame / lethal-clinch value of this action."""
    opt_type = option.get("type")
    my_prizes = state.me.prizes_remaining
    op_prizes = state.opp.prizes_remaining

    if opt_type == OPT_ATTACK:
        # If we're in closure (≤2 prizes left) attacking is everything
        if my_prizes <= 2:
            return 200.0
        if my_prizes <= 3:
            return 100.0
        return 0.0

    if opt_type == OPT_PLAY:
        card_id = option.get("_card_id", 0)
        if card_id == BOSS_ORDERS:
            # Boss's Orders: pull up a benched EX for a lethal hit
            # Very powerful when we're 1-2 prizes away
            op_pokemon = _op_field_pokemon(state)
            has_ex_on_bench = any(
                (p.card_id == MEGA_LUCARIO_EX or p.is_ex or p.is_mega_ex)
                for p in op_pokemon[1:]  # skip active
            )
            if my_prizes <= 2 and has_ex_on_bench:
                return 400.0   # game-winning move
            if my_prizes <= 3 and has_ex_on_bench:
                return 200.0
            if my_prizes <= 2:
                return 150.0
            return 0.0

        if card_id == PREMIUM_POWER:
            # Premium Power Pro can let us attack again after a KO — lethal combo
            if my_prizes <= 2 and _can_attack(state):
                return 250.0
            return 0.0

    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def feature_vector(option: dict, state: CanonicalState) -> dict[str, float]:
    """Return dictionary of scores across the six feature families."""
    return {
        "prize_race": round(prize_race(option, state), 2),
        "tempo": round(tempo(option, state), 2),
        "board": round(board(option, state), 2),
        "resources": round(resources(option, state), 2),
        "risk": round(risk(option, state), 2),
        "endgame": round(endgame(option, state), 2),
    }


def score_option(option: dict, state: CanonicalState) -> float:
    """
    Compute the raw combined score for one option.

    The caller (heuristic.py) applies phase-sensitive weights before
    final ranking.
    """
    return (
        prize_race(option, state)
        + tempo(option, state)
        + board(option, state)
        + resources(option, state)
        + risk(option, state)
        + endgame(option, state)
    )
