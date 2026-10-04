"""Opt-in B2 policy: never decline a base-damage game-winning knockout.

This is deliberately narrow. It layers on the official-area candidate and
uses only two attack facts verified from cabt ``AllAttack`` data. It does not
infer Weakness, Resistance, damage modifiers, prize value, or hidden state.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ptcg_agent.env.types import CanonicalState
from ptcg_agent.policies.official_area_candidate import get_action as _base_action

if TYPE_CHECKING:
    from ptcg_agent.beliefs.opponent_model import BeliefState


OPT_ATTACK = 13
ATTACK_BASE_DAMAGE = {
    982: 130,  # Aura Jab, verified with cabt AllAttack
    983: 270,  # Mega Brave, verified with cabt AllAttack
}
LETHAL_SCORE_BONUS = 100_000.0


def get_action(
    state: CanonicalState,
    belief: "BeliefState | None" = None,
    return_details: bool = False,
) -> list[int] | tuple[list[int], list[float], list[dict]]:
    """Apply a last-prize, visible-Active lethal override to the base policy."""
    chosen, scores, features = _base_action(
        state, belief=belief, return_details=True
    )

    if (
        state.select_context_id == 0
        and state.select_max_count == 1
        and state.me.prizes_remaining == 1
        and state.opp.active is not None
    ):
        target_hp = state.opp.active.hp
        lethal_indices = [
            index
            for index, option in enumerate(state.legal_options)
            if option.get("type") == OPT_ATTACK
            and ATTACK_BASE_DAMAGE.get(option.get("attackId"), 0) >= target_hp
        ]
        if lethal_indices:
            # If more than one base-damage attack KOs, retain the incumbent's
            # preference (normally Aura Jab's lower cost/use restriction).
            lethal_index = max(lethal_indices, key=lambda index: scores[index])
            for index in lethal_indices:
                scores[index] += LETHAL_SCORE_BONUS
                features[index] = dict(features[index])
                features[index]["visible_game_lethal"] = 1.0
            chosen = [lethal_index]

    if return_details:
        return chosen, scores, features
    return chosen
