"""Opt-in tactical policy ported from the frozen buddy Lucario agent.

The important part of the buddy policy is not its raw-observation wrapper; it
is the small ``AttackPlan`` it builds before choosing attachments, switches,
gust targets, and finally an attack.  This module ports that plan to the
project's one :class:`~ptcg_agent.env.types.CanonicalState` representation.

Only cabt-provided option indexes are returned.  Card metadata is read with
the standard library from the unchanged official CSV when it is available;
the locked deck has a small built-in fallback so a packaged agent still plays
legally when the CSV is absent.  No rules engine or native library is loaded.

Three deliberate differences from ``refs/buddy-lucario/main.py`` are backed
by the official CSV/live observation contract:

* A winning knockout is compared with *our* remaining prizes, not the
  opponent's remaining prizes.
* Solrock's Cosmic Beam requires Lunatone on the Bench (not merely in play).
* Hariyama's Heave-Ho Catcher says "may"; evolving is therefore not rejected
  just because the current Active is already the desired target.
"""
from __future__ import annotations

import csv
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ptcg_agent.env.types import CanonicalState, PlayerView, PokemonView


# Locked deck card IDs.
MAKUHITA = 673
HARIYAMA = 674
LUNATONE = 675
SOLROCK = 676
RIOLU = 677
MEGA_LUCARIO_EX = 678
DUSK_BALL = 1102
SWITCH_CARD = 1123
PREMIUM_POWER = 1141
FIGHTING_GONG = 1142
POKE_PAD = 1152
HERO_CAPE = 1159
BOSS_ORDERS = 1182
CARMINE = 1192
LILLIE_DETERMINATION = 1227
GRAVITY_MOUNTAIN = 1252
FIGHTING_ENERGY = 6

# Relevant official enums.  In particular, Active/Bench are 4/5 in live cabt.
AREA_DECK = 1
AREA_HAND = 2
AREA_DISCARD = 3
AREA_ACTIVE = 4
AREA_BENCH = 5
AREA_PRIZE = 6
AREA_STADIUM = 7
AREA_LOOKING = 12

OPT_NUMBER = 0
OPT_YES = 1
OPT_NO = 2
OPT_CARD = 3
OPT_PLAY = 7
OPT_ATTACH = 8
OPT_EVOLVE = 9
OPT_ABILITY = 10
OPT_RETREAT = 12
OPT_ATTACK = 13
OPT_END = 14

CTX_MAIN = 0
CTX_SETUP_ACTIVE = 1
CTX_SETUP_BENCH = 2
CTX_SWITCH = 3
CTX_TO_ACTIVE = 4
CTX_TO_HAND = 7
CTX_ATTACH_FROM = 21
CTX_ACTIVATE = 43

ENERGY_FIGHTING = 6
LEGACY_ENERGY = 12
LILLIES_PEARL = 1172


def _plain(value: object) -> str:
    """Case-fold a CSV value while making Pokémon/Pokemon equivalent."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


_ENERGY_TOKEN = {
    "{g}": 1,
    "{r}": 2,
    "{w}": 3,
    "{l}": 4,
    "{p}": 5,
    "{f}": 6,
    "{d}": 7,
    "{m}": 8,
    "{n}": 9,
}


@dataclass(frozen=True)
class CardMeta:
    card_id: int
    name: str = ""
    card_type: str = "unknown"
    is_pokemon: bool = False
    basic: bool = False
    stage1: bool = False
    stage2: bool = False
    ex: bool = False
    mega_ex: bool = False
    weakness: int | None = None
    resistance: int | None = None


def _locked_fallback() -> dict[int, CardMeta]:
    """Metadata copied from the official CSV rows for the locked list."""
    pokemon = {
        MAKUHITA: ("Makuhita", True, False, False),
        HARIYAMA: ("Hariyama", False, True, False),
        LUNATONE: ("Lunatone", True, False, False),
        SOLROCK: ("Solrock", True, False, False),
        RIOLU: ("Riolu", True, False, False),
        MEGA_LUCARIO_EX: ("Mega Lucario ex", False, True, True),
    }
    result: dict[int, CardMeta] = {}
    for card_id, (name, basic, stage1, mega) in pokemon.items():
        result[card_id] = CardMeta(
            card_id=card_id,
            name=name,
            card_type="pokemon",
            is_pokemon=True,
            basic=basic,
            stage1=stage1,
            ex=mega,
            mega_ex=mega,
            weakness=5 if card_id not in {LUNATONE, SOLROCK} else 1,
        )
    for card_id, name, kind in (
        (DUSK_BALL, "Dusk Ball", "item"),
        (SWITCH_CARD, "Switch", "item"),
        (PREMIUM_POWER, "Premium Power Pro", "item"),
        (FIGHTING_GONG, "Fighting Gong", "item"),
        (POKE_PAD, "Poke Pad", "item"),
        (HERO_CAPE, "Hero's Cape", "tool"),
        (BOSS_ORDERS, "Boss's Orders", "supporter"),
        (CARMINE, "Carmine", "supporter"),
        (LILLIE_DETERMINATION, "Lillie's Determination", "supporter"),
        (GRAVITY_MOUNTAIN, "Gravity Mountain", "stadium"),
        (FIGHTING_ENERGY, "Basic Fighting Energy", "basic_energy"),
    ):
        result[card_id] = CardMeta(card_id, name=name, card_type=kind)
    return result


class CardCatalog:
    """Small immutable metadata lookup with a failure-safe locked-list core."""

    def __init__(self, cards: dict[int, CardMeta], source: str = "fallback") -> None:
        merged = _locked_fallback()
        merged.update(cards)
        self._cards = merged
        self.source = source

    @classmethod
    def load(cls, path: str | Path | None = None) -> "CardCatalog":
        if path is None:
            path = (
                Path(__file__).resolve().parents[3]
                / "data"
                / "official"
                / "EN Card Data.csv"
            )
        csv_path = Path(path)
        cards: dict[int, CardMeta] = {}
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    try:
                        card_id = int(row.get("Card ID", ""))
                    except (TypeError, ValueError):
                        continue
                    if card_id in cards:
                        continue  # attack rows repeat the same card metadata
                    stage_type = _plain(
                        row.get("Stage (Pokemon)/Type (Energy and Trainer)")
                        or row.get("Stage (Pokémon)/Type (Energy and Trainer)")
                    )
                    rule = _plain(row.get("Rule"))
                    is_pokemon = "pokemon" in stage_type
                    weakness = _ENERGY_TOKEN.get(_plain(row.get("Weakness")))
                    resistance = _ENERGY_TOKEN.get(
                        _plain(row.get("Resistance (Type)"))
                    )
                    kind = "pokemon" if is_pokemon else stage_type.replace(" ", "_")
                    cards[card_id] = CardMeta(
                        card_id=card_id,
                        name=str(row.get("Card Name") or ""),
                        card_type=kind,
                        is_pokemon=is_pokemon,
                        basic=stage_type.startswith("basic pokemon"),
                        stage1=stage_type.startswith("stage 1 pokemon"),
                        stage2=stage_type.startswith("stage 2 pokemon"),
                        ex="pokemon ex" in rule,
                        mega_ex="mega pokemon ex" in rule,
                        weakness=weakness,
                        resistance=resistance,
                    )
        except (OSError, csv.Error, UnicodeError):
            return cls({}, source="fallback")
        return cls(cards, source=str(csv_path.resolve()))

    def get(self, card_id: int) -> CardMeta | None:
        return self._cards.get(card_id)


@dataclass(frozen=True)
class AttackSpec:
    attack_id: int
    energy_required: int
    damage: int
    ignores_weakness_resistance: bool = False


# Attack IDs/damage/costs are the official CSV/AllAttack facts for this list.
_ATTACKS: dict[int, tuple[AttackSpec, ...]] = {
    HARIYAMA: (AttackSpec(978, 3, 210),),
    SOLROCK: (AttackSpec(980, 1, 70, True),),
    MEGA_LUCARIO_EX: (
        AttackSpec(982, 1, 130),
        AttackSpec(983, 2, 270),
    ),
}


@dataclass
class AttackPlan:
    attacker_slot: int | None = None  # 0=Active, 1+=Bench index + 1
    target_slot: int | None = None
    attack_id: int | None = None
    remaining_hp: int | None = None
    expected_damage: int = 0
    needs_energy: bool = False
    needs_evolution: bool = False
    terminal: bool = False
    score: float = float("-inf")

    @property
    def exists(self) -> bool:
        return self.attacker_slot is not None and self.attack_id is not None


@dataclass
class _GameMemory:
    player_index: int | None = None
    turn: int | None = None
    plan: AttackPlan = field(default_factory=AttackPlan)
    ability_used: bool = False
    premium_power_used: bool = False


def _field(player: PlayerView) -> list[PokemonView]:
    result: list[PokemonView] = []
    if player.active is not None:
        result.append(player.active)
    result.extend(player.bench)
    return result


def _slot(area: object, index: object) -> int | None:
    if area == AREA_ACTIVE:
        return 0
    if area == AREA_BENCH and type(index) is int and index >= 0:
        return index + 1
    return None


def _sequence_item(values: object, index: object) -> Any | None:
    if not isinstance(values, list) or type(index) is not int:
        return None
    if 0 <= index < len(values):
        return values[index]
    return None


def _entity_at(
    state: CanonicalState,
    area: object,
    index: object,
    player_index: object | None = None,
) -> PokemonView | dict | None:
    """Resolve a CARD option from its official area, never from option order."""
    owner = state.your_index if player_index is None else player_index
    mine = owner == state.your_index
    player = state.me if mine else state.opp

    if area == AREA_DECK:
        select = state.raw.get("select") if isinstance(state.raw, dict) else None
        return _sequence_item(select.get("deck") if isinstance(select, dict) else None, index)
    if area == AREA_HAND:
        return _sequence_item(player.hand, index)
    if area == AREA_DISCARD:
        return _sequence_item(player.discard, index)
    if area == AREA_ACTIVE:
        return player.active if index in (0, None) else None
    if area == AREA_BENCH:
        return _sequence_item(player.bench, index)
    if area == AREA_PRIZE:
        return _sequence_item(player.prizes, index)
    if area == AREA_STADIUM:
        return _sequence_item(state.stadium, index)
    if area == AREA_LOOKING:
        return _sequence_item(state.looking, index)
    return None


def _card_id(entity: PokemonView | dict | None) -> int:
    if isinstance(entity, PokemonView):
        return entity.card_id
    if isinstance(entity, dict):
        value = entity.get("id", 0)
        return value if type(value) is int else 0
    return 0


def _energy_count(entity: PokemonView | dict | None) -> int:
    if isinstance(entity, PokemonView):
        return len(entity.energies)
    if isinstance(entity, dict):
        energies = entity.get("energies") or []
        return len(energies) if isinstance(energies, list) else 0
    return 0


def _attached_ids(pokemon: PokemonView, field_name: str) -> list[int]:
    values = pokemon.raw.get(field_name, []) if isinstance(pokemon.raw, dict) else []
    if not isinstance(values, list):
        return []
    return [_card_id(value) for value in values]


class PlannedPolicy:
    """One policy instance, with tactical memory scoped to one game."""

    def __init__(self, catalog: CardCatalog | None = None) -> None:
        self.catalog = catalog or CardCatalog.load()
        self._memory = _GameMemory()

    @property
    def plan(self) -> AttackPlan:
        """Expose a read-only-by-convention snapshot for tests/telemetry."""
        return self._memory.plan

    def reset(self) -> None:
        self._memory = _GameMemory()

    def _start_selection(self, state: CanonicalState) -> None:
        memory = self._memory
        new_game = (
            memory.player_index is not None
            and (
                memory.player_index != state.your_index
                or (memory.turn is not None and state.turn < memory.turn)
            )
        )
        if new_game:
            self.reset()
            memory = self._memory
        if memory.player_index is None:
            memory.player_index = state.your_index
        if memory.turn != state.turn:
            memory.turn = state.turn
            memory.plan = AttackPlan()
            memory.ability_used = False
            memory.premium_power_used = False

    def _hand_counts(self, state: CanonicalState) -> Counter[int]:
        return Counter(_card_id(card) for card in (state.me.hand or []))

    def _field_counts(self, state: CanonicalState) -> Counter[int]:
        return Counter(pokemon.card_id for pokemon in _field(state.me))

    def _discard_counts(self, state: CanonicalState) -> Counter[int]:
        return Counter(_card_id(card) for card in state.me.discard)

    def _prize_count(self, pokemon: PokemonView) -> int:
        metadata = self.catalog.get(pokemon.card_id)
        count = 3 if metadata and metadata.mega_ex else 2 if metadata and metadata.ex else 1
        # Both reductions are in the official CSV.  Treating Legacy Energy as
        # live is conservative for a claimed game-winning knockout because its
        # once-per-game usage is hidden from the current observation.
        if LEGACY_ENERGY in _attached_ids(pokemon, "energyCards"):
            count -= 1
        if LILLIES_PEARL in _attached_ids(pokemon, "tools"):
            if metadata and "lillie" in _plain(metadata.name):
                count -= 1
        return max(0, count)

    def _pokemon_score(self, pokemon: PokemonView) -> float:
        metadata = self.catalog.get(pokemon.card_id)
        score = self._prize_count(pokemon) * 1000.0
        score += len(pokemon.energies) * 150.0
        score += len(pokemon.tools) * 100.0
        if metadata and metadata.stage2:
            score += 250.0
        elif metadata and metadata.stage1:
            score += 130.0
        if pokemon.card_id in {144, 322, 323, 337}:
            score -= 200.0
        if pokemon.card_id == 112 and pokemon.energies:
            score += 300.0
        return score + pokemon.hp

    def _evolution_slots(self, state: CanonicalState) -> set[int]:
        slots: set[int] = set()
        for option in state.legal_options:
            if option.get("type") != OPT_EVOLVE:
                continue
            card = _entity_at(
                state,
                option.get("area", AREA_HAND),
                option.get("index"),
                state.your_index,
            )
            if _card_id(card) != HARIYAMA:
                continue
            target = _slot(option.get("inPlayArea"), option.get("inPlayIndex"))
            if target is not None:
                slots.add(target)
        return slots

    def _build_plan(self, state: CanonicalState) -> AttackPlan:
        options = state.legal_options
        can_switch = any(option.get("type") == OPT_RETREAT for option in options)
        can_gust = False
        for option in options:
            if option.get("type") == OPT_PLAY:
                card = _entity_at(state, AREA_HAND, option.get("index"))
                card_id = _card_id(card)
                can_switch = can_switch or card_id == SWITCH_CARD
                can_gust = can_gust or card_id == BOSS_ORDERS
            elif option.get("type") == OPT_EVOLVE:
                card = _entity_at(
                    state,
                    option.get("area", AREA_HAND),
                    option.get("index"),
                )
                can_gust = can_gust or _card_id(card) == HARIYAMA

        active_attack_ids = {
            option.get("attackId")
            for option in options
            if option.get("type") == OPT_ATTACK
        }
        evolution_slots = self._evolution_slots(state)
        my_cards = _field(state.me)
        opponent_cards = _field(state.opp)
        hand_counts = self._hand_counts(state)
        discard_counts = self._discard_counts(state)
        lunatone_on_bench = any(
            pokemon.card_id == LUNATONE for pokemon in state.me.bench
        )
        best = AttackPlan()

        if state.turn < 2:
            return best

        for attacker_slot, pokemon in enumerate(my_cards):
            if attacker_slot > 0 and not can_switch:
                break

            planned_card_id = pokemon.card_id
            needs_evolution = False
            if planned_card_id == MAKUHITA and attacker_slot in evolution_slots:
                planned_card_id = HARIYAMA
                needs_evolution = True
            if planned_card_id == SOLROCK and not lunatone_on_bench:
                continue
            attacks = _ATTACKS.get(planned_card_id, ())

            for attack in attacks:
                energy_count = len(pokemon.energies)
                needs_energy = False
                if energy_count < attack.energy_required:
                    if (
                        hand_counts[FIGHTING_ENERGY] > 0
                        and not state.me.energy_attached
                        and energy_count + 1 >= attack.energy_required
                    ):
                        energy_count += 1
                        needs_energy = True
                    else:
                        continue

                # Live cabt is authoritative about disabled attacks that are
                # already paid for.  An attack absent only because this turn's
                # planned manual attachment has not happened yet is allowed;
                # cabt will expose (or withhold) it after the attachment.
                if (
                    attacker_slot == 0
                    and not needs_evolution
                    and attack.attack_id not in active_attack_ids
                    and not needs_energy
                ):
                    continue

                aura_acceleration = 0.0
                if attack.attack_id == 982:
                    aura_acceleration = 60.0 * min(
                        3, discard_counts[FIGHTING_ENERGY]
                    )
                if planned_card_id == MEGA_LUCARIO_EX and state.me.prizes_remaining in {2, 3}:
                    aura_acceleration -= 500.0

                for target_slot, target in enumerate(opponent_cards):
                    if target_slot > 0 and not can_gust:
                        break
                    damage = attack.damage
                    if self._memory.premium_power_used:
                        damage += 30
                    target_meta = self.catalog.get(target.card_id)
                    if not attack.ignores_weakness_resistance and target_meta:
                        if target_meta.weakness == ENERGY_FIGHTING:
                            damage *= 2
                        elif target_meta.resistance == ENERGY_FIGHTING:
                            damage = max(0, damage - 30)

                    prize = self._prize_count(target) if target.hp <= damage else 0
                    target_score = self._pokemon_score(target)
                    if target.hp > damage and target.hp > 0:
                        target_score *= damage / target.hp
                    score = target_score + aura_acceleration

                    # Buddy checked opponent prizes here.  cabt PlayerState
                    # prize arrays belong to that player, so our count is the
                    # one reduced when we take a knockout.
                    terminal = prize > 0 and state.me.prizes_remaining <= prize
                    if terminal:
                        score = 50_000.0
                    if attacker_slot == 0:
                        score += 220.0
                    if target_slot == 0:
                        score += 300.0
                    score += energy_count

                    if score > best.score:
                        best = AttackPlan(
                            attacker_slot=attacker_slot,
                            target_slot=target_slot,
                            attack_id=attack.attack_id,
                            remaining_hp=target.hp - damage,
                            expected_damage=damage,
                            needs_energy=needs_energy,
                            needs_evolution=needs_evolution,
                            terminal=terminal,
                            score=score,
                        )
        return best

    def _energy_score(self, pokemon: PokemonView | dict | None, active: bool) -> float:
        card_id = _card_id(pokemon)
        energy_count = _energy_count(pokemon)
        field = _field(self._last_state.me)
        attacker1_ready = any(
            p.card_id in {RIOLU, MEGA_LUCARIO_EX} and len(p.energies) >= 2
            for p in field
        )
        attacker2_ready = any(
            p.card_id in {MAKUHITA, HARIYAMA} and len(p.energies) >= 3
            for p in field
        )
        score = 8000.0 + (10.0 if active else 0.0)
        if card_id in {MAKUHITA, HARIYAMA}:
            if card_id == HARIYAMA:
                score += 1.0
            if energy_count < 3:
                score += 100.0
            if attacker2_ready:
                score -= 50.0
        elif card_id == LUNATONE:
            score -= 100.0
        elif card_id == SOLROCK:
            score += 20.0 if energy_count < 1 else -100.0
        elif card_id in {RIOLU, MEGA_LUCARIO_EX}:
            if card_id == MEGA_LUCARIO_EX:
                score += 1.0
            if energy_count < 2:
                score += 100.0
            if attacker1_ready:
                score -= 50.0
        return score

    def _score_card(self, option: dict, state: CanonicalState) -> tuple[float, dict[str, float]]:
        entity = _entity_at(
            state,
            option.get("area"),
            option.get("index"),
            option.get("playerIndex", state.your_index),
        )
        card_id = _card_id(entity)
        energy_count = _energy_count(entity)
        mine = option.get("playerIndex", state.your_index) == state.your_index
        option_slot = _slot(option.get("area"), option.get("index"))
        plan = self._memory.plan
        score = 0.0
        plan_match = 0.0

        if state.select_context_id in {CTX_SWITCH, CTX_TO_ACTIVE}:
            if mine:
                score += energy_count * 2.0
                if option_slot == plan.attacker_slot:
                    score += 100.0
                    plan_match = 1.0
                if card_id == MEGA_LUCARIO_EX:
                    score += 8.0 if state.me.prizes_remaining in {2, 3} else 20.0
                elif card_id == HARIYAMA and energy_count >= 2:
                    score += 15.0
                elif card_id == MAKUHITA and energy_count >= 2:
                    score += 10.0
                elif card_id == SOLROCK:
                    score += 5.0
                elif card_id == RIOLU:
                    score += 4.0
            elif option_slot == plan.target_slot:
                score += 100.0
                plan_match = 1.0
        elif state.select_context_id == CTX_SETUP_ACTIVE:
            if card_id == SOLROCK:
                score = 2.0 if state.first_player == state.your_index else 4.0
            elif card_id == RIOLU:
                score = 3.0
            elif card_id == MAKUHITA:
                score = 1.0
        elif state.select_context_id == CTX_SETUP_BENCH:
            # Preserve buddy's neutral ordering during optional setup benching.
            score = 0.0
        elif state.select_context_id == CTX_TO_HAND:
            hand_counts = self._hand_counts(state)
            field_counts = self._field_counts(state)
            score = 200.0 - hand_counts[card_id] * 100.0
            if card_id == MAKUHITA:
                score += 10.0 if field_counts[MAKUHITA] == 0 else -10.0
            elif card_id == HARIYAMA:
                score += 20.0 if field_counts[MAKUHITA] >= 1 else -20.0
            elif card_id == LUNATONE:
                score += 60.0 if field_counts[LUNATONE] == 0 else -250.0
            elif card_id == SOLROCK:
                score += 50.0 if field_counts[SOLROCK] == 0 else -250.0
            elif card_id == RIOLU:
                count = field_counts[RIOLU] + field_counts[MEGA_LUCARIO_EX]
                score += -150.0 if count >= 2 else -3.0 if count >= 1 else 40.0
            elif card_id == MEGA_LUCARIO_EX:
                score += 40.0 if field_counts[RIOLU] >= 1 else -15.0
            elif card_id == FIGHTING_ENERGY:
                score += 30.0 if (
                    not self._memory.ability_used or not state.me.energy_attached
                ) else -1.0
        elif state.select_context_id == CTX_ATTACH_FROM:
            score = self._energy_score(entity, option.get("area") == AREA_ACTIVE)

        return score, {"card_id": float(card_id), "plan_match": plan_match}

    def _score_main(self, option: dict, state: CanonicalState) -> tuple[float, dict[str, float]]:
        option_type = option.get("type")
        plan = self._memory.plan
        score = 0.0
        card_id = 0
        plan_match = 0.0

        if option_type == OPT_PLAY:
            card = _entity_at(state, AREA_HAND, option.get("index"))
            card_id = _card_id(card)
            metadata = self.catalog.get(card_id)
            if metadata and metadata.is_pokemon:
                score = 20_000.0
                field_counts = self._field_counts(state)
                if card_id in {LUNATONE, SOLROCK} and field_counts[card_id] >= 1:
                    score = -1.0
                elif card_id == RIOLU and (
                    field_counts[RIOLU] + field_counts[MEGA_LUCARIO_EX] >= 2
                ):
                    score = -1.0
            else:
                score = 10_000.0
                if card_id == SWITCH_CARD:
                    if plan.attacker_slot is not None and plan.attacker_slot > 0:
                        score = 6000.0
                        plan_match = 1.0
                    else:
                        score = -1.0
                elif card_id == PREMIUM_POWER:
                    # Official text is +30 attack damage, not draw.  Prefer it
                    # when a planned attack exists and especially when +30 can
                    # convert the planned target to a knockout.
                    if not plan.exists:
                        score = -1.0
                    elif plan.remaining_hp is not None and 0 < plan.remaining_hp <= 30:
                        score = 7500.0
                        plan_match = 1.0
                    elif plan.terminal:
                        score = -1.0
                    else:
                        score = 5000.0
                elif card_id == BOSS_ORDERS:
                    if plan.target_slot is not None and plan.target_slot > 0:
                        score = 3200.0
                        plan_match = 1.0
                    else:
                        score = -1.0
                elif card_id == CARMINE:
                    score = 3000.0
                elif card_id == LILLIE_DETERMINATION:
                    score = 3100.0
                elif card_id == GRAVITY_MOUNTAIN:
                    # The official text affects Stage 2 Pokémon.  This locked
                    # deck has none; only play it into a visible opposing Stage
                    # 2, instead of treating it as a Lucario buff.
                    opponent_has_stage2 = any(
                        bool(self.catalog.get(p.card_id) and self.catalog.get(p.card_id).stage2)
                        for p in _field(state.opp)
                    )
                    score = 2000.0 if opponent_has_stage2 else -1.0
        elif option_type == OPT_ATTACH:
            card = _entity_at(
                state,
                option.get("area", AREA_HAND),
                option.get("index"),
            )
            card_id = _card_id(card)
            target = _entity_at(
                state,
                option.get("inPlayArea"),
                option.get("inPlayIndex"),
            )
            target_slot = _slot(option.get("inPlayArea"), option.get("inPlayIndex"))
            if card_id == HERO_CAPE:
                score = 7000.0
                if _card_id(target) == RIOLU:
                    score += 100.0
                elif _card_id(target) == MEGA_LUCARIO_EX:
                    score += 200.0
            else:
                score = self._energy_score(
                    target, option.get("inPlayArea") == AREA_ACTIVE
                )
                if target_slot == plan.attacker_slot and plan.needs_energy:
                    score += 200.0
                    plan_match = 1.0
        elif option_type == OPT_EVOLVE:
            target = _entity_at(
                state,
                option.get("inPlayArea"),
                option.get("inPlayIndex"),
            )
            card = _entity_at(
                state,
                option.get("area", AREA_HAND),
                option.get("index"),
            )
            card_id = _card_id(card)
            score = 9000.0 + _energy_count(target)
            target_slot = _slot(option.get("inPlayArea"), option.get("inPlayIndex"))
            if (
                card_id == HARIYAMA
                and plan.needs_evolution
                and target_slot == plan.attacker_slot
            ):
                score += 300.0
                plan_match = 1.0
        elif option_type == OPT_ABILITY:
            card = _entity_at(
                state,
                option.get("area"),
                option.get("index"),
            )
            card_id = _card_id(card)
            score = 1.0 if card_id == 1267 else 30_000.0
        elif option_type == OPT_RETREAT:
            if plan.attacker_slot is not None and plan.attacker_slot > 0:
                score = 2000.0
                plan_match = 1.0
            else:
                score = -1.0
        elif option_type == OPT_ATTACK:
            score = 1000.0
            if option.get("attackId") == plan.attack_id:
                score += 100.0
                plan_match = 1.0
                if plan.terminal:
                    score += 100_000.0
        elif option_type == OPT_END:
            score = 0.0

        return score, {
            "card_id": float(card_id),
            "plan_match": plan_match,
            "planned_attack_id": float(plan.attack_id or -1),
            "planned_attacker_slot": float(
                plan.attacker_slot if plan.attacker_slot is not None else -1
            ),
            "planned_target_slot": float(
                plan.target_slot if plan.target_slot is not None else -1
            ),
            "visible_game_lethal": float(plan.terminal and plan_match > 0),
        }

    def get_action(
        self,
        state: CanonicalState,
        *,
        return_details: bool = False,
    ) -> list[int] | tuple[list[int], list[float], list[dict[str, float]]]:
        self._start_selection(state)
        options = state.legal_options
        max_count = state.select_max_count
        if type(max_count) is not int or not 0 <= max_count <= len(options):
            raise ValueError("select.maxCount must be within the option list")
        if max_count == 0:
            return ([], [], []) if return_details else []

        # Used only for energy readiness within this synchronous scoring call.
        self._last_state = state
        if state.select_context_id == CTX_MAIN:
            self._memory.plan = self._build_plan(state)

        scores: list[float] = []
        features: list[dict[str, float]] = []
        for option in options:
            option_type = option.get("type")
            if option_type == OPT_NUMBER:
                score = float(option.get("number", 0))
                detail = {"number": score, "plan_match": 0.0}
            elif option_type == OPT_YES:
                score = 1.0
                detail = {"yes": 1.0, "plan_match": 0.0}
            elif option_type == OPT_NO:
                score = 0.0
                detail = {"no": 1.0, "plan_match": 0.0}
            elif option_type == OPT_CARD:
                score, detail = self._score_card(option, state)
            elif state.select_context_id == CTX_MAIN:
                score, detail = self._score_main(option, state)
            else:
                score, detail = 0.0, {"plan_match": 0.0}
            detail = dict(detail)
            detail["tactical_score"] = float(score)
            scores.append(float(score))
            features.append(detail)

        ranked = sorted(range(len(options)), key=lambda index: (-scores[index], index))
        chosen = ranked[:max_count]

        # Track only effects caused by our actual top choice.  Both flags reset
        # on the next turn and wrapper.reset() resets them between games.
        if state.select_context_id == CTX_MAIN and chosen:
            selected = options[chosen[0]]
            if selected.get("type") == OPT_ABILITY:
                entity = _entity_at(
                    state, selected.get("area"), selected.get("index")
                )
                if _card_id(entity) == LUNATONE:
                    self._memory.ability_used = True
            elif selected.get("type") == OPT_PLAY:
                card = _entity_at(state, AREA_HAND, selected.get("index"))
                if _card_id(card) == PREMIUM_POWER:
                    self._memory.premium_power_used = True

        if return_details:
            return chosen, scores, features
        return chosen


_DEFAULT_POLICY = PlannedPolicy()


def reset_policy() -> None:
    """Reset module-level game memory (called by the deck-phase wrapper)."""
    _DEFAULT_POLICY.reset()


def get_action(
    state: CanonicalState,
    belief: object | None = None,
    return_details: bool = False,
) -> list[int] | tuple[list[int], list[float], list[dict[str, float]]]:
    """Compatibility entry point used by the evaluator/submission wrapper."""
    del belief
    return _DEFAULT_POLICY.get_action(state, return_details=return_details)
