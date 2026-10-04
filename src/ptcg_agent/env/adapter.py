"""
Adapter: raw cabt observation dict -> CanonicalState.

Rules:
  - Never calls the C engine.
  - Only reads keys verified in fixtures or live cabt dumps.
  - Round-trip test: must not crash on fixtures/obs_sample.json.

Live obs key map (verified 2026-09-01):
  Pokemon in play: {id, serial, playerIndex, hp, maxHp, appearThisTurn,
                     energies, energyCards, tools, preEvolution}
  Hand card: {id, serial, playerIndex}
  PlayerState: {active, bench, benchMax, deckCount, discard, hand, handCount,
                prize, poisoned, burned, asleep, paralyzed, confused}
  State: {turn, turnActionCount, yourIndex, firstPlayer, supporterPlayed,
          stadiumPlayed, energyAttached, retreated, result, stadium, looking, players}
  obs top: {current, logs, remainingOverageTime, search_begin_input, select}
"""
from __future__ import annotations
from typing import Any

from .types import CanonicalState, PlayerView, PokemonView


# ---------------------------------------------------------------------------
# Enum name lookups (from buddy cg/api.py, verified against source)
# ---------------------------------------------------------------------------

SELECT_CONTEXT_NAMES = {
    0: "MAIN",
    1: "SETUP_ACTIVE_POKEMON",
    2: "SETUP_BENCH_POKEMON",
    3: "SWITCH",
    4: "TO_ACTIVE",
    5: "TO_BENCH",
    6: "TO_FIELD",
    7: "TO_HAND",
    8: "DISCARD",
    9: "TO_DECK",
    10: "TO_DECK_BOTTOM",
    11: "TO_PRIZE",
    12: "NOT_MOVE",
    13: "DAMAGE_COUNTER",
    14: "DAMAGE_COUNTER_ANY",
    15: "DAMAGE",
    16: "REMOVE_DAMAGE_COUNTER",
    17: "HEAL",
    18: "EVOLVES_FROM",
    19: "EVOLVES_TO",
    20: "DEVOLVE",
    21: "ATTACH_FROM",
    22: "ATTACH_TO",
    23: "DETACH_FROM",
    24: "LOOK",
    25: "EFFECT_TARGET",
    26: "DISCARD_ENERGY_CARD",
    27: "DISCARD_TOOL_CARD",
    28: "SWITCH_ENERGY_CARD",
    29: "DISCARD_CARD_OR_ATTACHED_CARD",
    30: "DISCARD_ENERGY",
    31: "TO_HAND_ENERGY",
    32: "TO_DECK_ENERGY",
    33: "SWITCH_ENERGY",
    34: "SKILL_ORDER",
    35: "ATTACK",
    36: "DISABLE_ATTACK",
    37: "EVOLVE",
    38: "DRAW_COUNT",
    39: "DAMAGE_COUNTER_COUNT",
    40: "REMOVE_DAMAGE_COUNTER_COUNT",
    41: "IS_FIRST",
    42: "MULLIGAN",
    43: "ACTIVATE",
    44: "FIRST_EFFECT",
    45: "MORE_DEVOLVE",
    46: "COIN_HEAD",
    47: "AFFECT_SPECIAL_CONDITION",
    48: "RECOVER_SPECIAL_CONDITION",
}

OPTION_TYPE_NAMES = {
    0: "NUMBER",
    1: "YES",
    2: "NO",
    3: "CARD",
    4: "TOOL_CARD",
    5: "ENERGY_CARD",
    6: "ENERGY",
    7: "PLAY",
    8: "ATTACH",
    9: "EVOLVE",
    10: "ABILITY",
    11: "DISCARD",
    12: "RETREAT",
    13: "ATTACK",
    14: "END",
    15: "SKILL",
    16: "SPECIAL_CONDITION",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_pokemon(poke_dict: dict | None) -> PokemonView | None:
    """Parse a single Pokemon dict from the live observation.

    Live keys (verified): id, serial, playerIndex, hp, maxHp,
    appearThisTurn, energies, energyCards, tools, preEvolution.
    """
    if poke_dict is None:
        return None

    energies = poke_dict.get("energies", []) or []
    energy_cards = poke_dict.get("energyCards", []) or []
    tools = poke_dict.get("tools", []) or []

    return PokemonView(
        card_id=poke_dict.get("id", 0),
        name="",  # not in live obs; look up from all_card_data() if needed
        hp=poke_dict.get("hp", 0),
        max_hp=poke_dict.get("maxHp", 0),
        energies=energies,
        tools=tools,
        status_conditions=[],  # conditions are at PlayerState level
        retreat_cost=0,  # not in live obs; look up from CardData if needed
        is_ex=False,     # not in live obs; look up from CardData if needed
        is_mega_ex=False,  # not in live obs; look up from CardData if needed
        raw=poke_dict,
    )


def _parse_player(player_dict: dict, is_me: bool) -> PlayerView:
    """Parse a PlayerState dict into our PlayerView.

    Live keys (verified): active, bench, benchMax, deckCount, discard,
    hand, handCount, prize, poisoned, burned, asleep, paralyzed, confused.
    """
    # Active: list of 0-1 pokemon (None entries = face-down)
    active_list = player_dict.get("active") or []
    active = None
    if active_list:
        active = _parse_pokemon(active_list[0])

    # cabt stores Special Conditions on PlayerState; they apply to the
    # Active Pokemon. Keep the convenience field in sync with those flags.
    condition_fields = (
        ("poisoned", "POISON"),
        ("burned", "BURN"),
        ("asleep", "SLEEP"),
        ("paralyzed", "PARALYZE"),
        ("confused", "CONFUSE"),
    )
    if active is not None:
        active.status_conditions = [
            name for field, name in condition_fields if player_dict.get(field, False)
        ]

    # Bench
    bench_raw = player_dict.get("bench") or []
    bench = [_parse_pokemon(p) for p in bench_raw if p is not None]
    bench = [b for b in bench if b is not None]

    # Hand: full list for us, None for opponent
    hand = player_dict.get("hand", None)
    hand_count = player_dict.get(
        "handCount", len(hand) if isinstance(hand, list) else 0
    )

    # Discard
    discard = player_dict.get("discard") or []

    # Prizes
    prizes = player_dict.get("prize") or []
    prizes_remaining = len(prizes)

    return PlayerView(
        active=active,
        bench=bench,
        hand=hand if is_me else None,
        hand_count=hand_count,
        deck_count=player_dict.get("deckCount", 0),
        discard=discard,
        prizes=prizes,
        prizes_remaining=prizes_remaining,
        supporter_played=False,   # Set from State, not PlayerState
        stadium_played=False,
        energy_attached=False,
        retreated=False,
        poisoned=player_dict.get("poisoned", False),
        burned=player_dict.get("burned", False),
        asleep=player_dict.get("asleep", False),
        paralyzed=player_dict.get("paralyzed", False),
        confused=player_dict.get("confused", False),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_canonical(obs_dict: dict) -> CanonicalState:
    """
    Convert a raw cabt observation dict into a CanonicalState.

    This is the single entry point for all observation parsing.
    """
    select = obs_dict.get("select")
    current = obs_dict.get("current")
    logs = obs_dict.get("logs") or []

    # --- Deck phase (select is None) ---
    if select is None:
        return CanonicalState(
            your_index=current.get("yourIndex", 0) if current else 0,
            remaining_overage_time=obs_dict.get("remainingOverageTime"),
            result=None,
            turn=0,
            turn_action_count=0,
            first_player=-1,
            select_context=None,
            select_context_id=None,
            select_type=None,
            select_max_count=0,
            select_min_count=0,
            legal_options=[],
            legal_option_indices=[],
            me=PlayerView(
                active=None, bench=[], hand=None, hand_count=0,
                deck_count=0, discard=[], prizes=[], prizes_remaining=0,
                supporter_played=False, stadium_played=False,
                energy_attached=False, retreated=False,
                poisoned=False, burned=False, asleep=False,
                paralyzed=False, confused=False,
            ),
            opp=PlayerView(
                active=None, bench=[], hand=None, hand_count=0,
                deck_count=0, discard=[], prizes=[], prizes_remaining=0,
                supporter_played=False, stadium_played=False,
                energy_attached=False, retreated=False,
                poisoned=False, burned=False, asleep=False,
                paralyzed=False, confused=False,
            ),
            stadium=[],
            looking=None,
            logs_tail=[],
            effect_card=None,
            context_card=None,
            raw=obs_dict,
        )

    # --- Battle phase (select is not None) ---
    options = select.get("option") or []
    max_count = select.get("maxCount", 0)
    min_count = select.get("minCount", 0)
    context_id = select.get("context")
    select_type_id = select.get("type")
    context_name = SELECT_CONTEXT_NAMES.get(context_id, f"UNKNOWN_{context_id}")

    your_index = current.get("yourIndex", 0) if current else 0
    result_val = current.get("result", -1) if current else None
    if result_val == -1:
        result_val = None

    # Parse players
    players = (current.get("players") or []) if current else []
    opp_index = 1 - your_index
    me_dict = players[your_index] if 0 <= your_index < len(players) else {}
    opp_dict = players[opp_index] if 0 <= opp_index < len(players) else {}
    me = _parse_player(me_dict or {}, is_me=True)
    opp = _parse_player(opp_dict or {}, is_me=False)

    # State-level flags go on `me` since they describe the current turn's player
    if current:
        me.supporter_played = current.get("supporterPlayed", False)
        me.stadium_played = current.get("stadiumPlayed", False)
        me.energy_attached = current.get("energyAttached", False)
        me.retreated = current.get("retreated", False)

    # Stadium
    stadium = (current.get("stadium") or []) if current else []

    # Looking
    looking = current.get("looking") if current else None

    return CanonicalState(
        your_index=your_index,
        remaining_overage_time=obs_dict.get("remainingOverageTime"),
        result=result_val,
        turn=current.get("turn", 0) if current else 0,
        turn_action_count=current.get("turnActionCount", 0) if current else 0,
        first_player=current.get("firstPlayer", -1) if current else -1,
        select_context=context_name,
        select_context_id=context_id,
        select_type=select_type_id,
        select_max_count=max_count,
        select_min_count=min_count,
        legal_options=options,
        legal_option_indices=list(range(len(options))),
        me=me,
        opp=opp,
        stadium=stadium,
        looking=looking,
        logs_tail=logs[-20:] if logs else [],
        effect_card=select.get("effect"),
        context_card=select.get("contextCard"),
        raw=obs_dict,
    )


def legal_indices(state: CanonicalState) -> list[int]:
    """Return valid option indices for the current selection."""
    return list(state.legal_option_indices)


def selection_indices_are_valid(state: CanonicalState, indices: Any) -> bool:
    """Check the exact cabt battle-action transport contract.

    This deliberately does not adjudicate card rules: every entry in
    ``legal_options`` already came from cabt. It only verifies that an action
    is a list of exactly ``maxCount`` distinct, in-range integer indexes.
    Deck actions are a separate phase and therefore return ``False`` here.
    """
    if state.raw.get("select") is None or not isinstance(indices, list):
        return False
    if len(indices) != state.select_max_count:
        return False
    if any(type(index) is not int for index in indices):
        return False
    if len(set(indices)) != len(indices):
        return False
    return all(0 <= index < len(state.legal_options) for index in indices)


def describe_option(option: dict) -> str:
    """Return a human-readable description of an option dict."""
    opt_type = option.get("type")
    type_name = OPTION_TYPE_NAMES.get(opt_type, f"UNKNOWN_{opt_type}")

    parts = [type_name]

    if opt_type == 13:  # ATTACK
        aid = option.get("attackId", "?")
        parts.append(f"attackId={aid}")
    elif opt_type == 7:  # PLAY
        idx = option.get("index", "?")
        parts.append(f"hand_index={idx}")
    elif opt_type == 8:  # ATTACH
        parts.append(f"area={option.get('area','?')} idx={option.get('index','?')}")
        parts.append(f"to_area={option.get('inPlayArea','?')} to_idx={option.get('inPlayIndex','?')}")
    elif opt_type == 9:  # EVOLVE
        parts.append(f"area={option.get('area','?')} idx={option.get('index','?')}")
        parts.append(f"to_area={option.get('inPlayArea','?')} to_idx={option.get('inPlayIndex','?')}")
    elif opt_type == 12:  # RETREAT
        parts.append("retreat")
    elif opt_type == 14:  # END
        parts.append("end_turn")
    elif opt_type == 3:  # CARD
        area = option.get("area", "?")
        idx = option.get("index", "?")
        player = option.get("playerIndex", "?")
        parts.append(f"area={area} idx={idx} player={player}")
    elif opt_type in (1, 2):  # YES / NO
        pass
    elif opt_type == 0:  # NUMBER
        parts.append(f"number={option.get('number', '?')}")

    return " | ".join(parts)
