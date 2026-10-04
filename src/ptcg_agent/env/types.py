"""
CanonicalState and supporting types for the PTCG agent.

All fields are populated only from real obs keys verified in fixtures
or live cabt dumps. Guessed fields go in docs/notes/unknowns.md.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PokemonView:
    """One Pokémon in play (Active or Bench)."""
    card_id: int
    name: str
    hp: int
    max_hp: int
    energies: list[int]         # EnergyType integer IDs from live cabt JSON
    tools: list[dict]           # raw tool objects
    status_conditions: list[str]  # e.g. ["POISON", "BURN"]
    retreat_cost: int
    is_ex: bool
    is_mega_ex: bool
    raw: dict                    # original dict, always kept


@dataclass
class PlayerView:
    """View of one player's board."""
    active: PokemonView | None
    bench: list[PokemonView]
    hand: list[dict] | None      # list of card dicts for us, None for opponent
    hand_count: int
    deck_count: int
    discard: list[dict]
    prizes: list[dict | None]    # None entries are face-down
    prizes_remaining: int
    supporter_played: bool
    stadium_played: bool
    energy_attached: bool
    retreated: bool
    # Status conditions on Active (duplicated from PokemonView for convenience)
    poisoned: bool
    burned: bool
    asleep: bool
    paralyzed: bool
    confused: bool


@dataclass
class CanonicalState:
    """
    Canonical representation of a cabt observation.

    Built by adapter.to_canonical(obs_dict). Adapter never calls the C engine.
    """
    # Identity
    your_index: int
    remaining_overage_time: float | None

    # Game result (-1 = not finished, 0 = player0 wins, 1 = player1 wins)
    result: int | None

    # Turn info
    turn: int
    turn_action_count: int
    first_player: int

    # Selection context
    select_context: str | None    # human-readable context name if available
    select_context_id: int | None # raw SelectContext int
    select_type: int | None       # raw SelectType int
    select_max_count: int
    select_min_count: int

    # Legal actions
    legal_options: list[dict]     # raw option dicts from obs["select"]["option"]
    legal_option_indices: list[int]  # [0, 1, ..., len(options)-1]

    # Board state
    me: PlayerView
    opp: PlayerView

    # Stadium
    stadium: list[dict]

    # Looking cards (e.g. when viewing top of deck)
    looking: list[dict | None] | None

    # Recent game log entries
    logs_tail: list[dict]

    # Effect / context card info from select
    effect_card: dict | None
    context_card: dict | None

    # Always keep the raw observation for debugging
    raw: dict = field(repr=False)
