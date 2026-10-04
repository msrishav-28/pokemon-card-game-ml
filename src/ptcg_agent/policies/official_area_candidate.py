"""Opt-in heuristic candidate using cabt's official Active/Bench area IDs.

The incumbent heuristic was built with legacy area constants 3/4, while cabt
uses 4/5 for Active/Bench.  This module is deliberately a compatibility shim:
it translates only option area fields on a copied ``CanonicalState`` and then
delegates to the incumbent scorer.  It neither mutates the shared adapter
output nor changes the submission entry point.

Once the incumbent feature module uses the official constants directly, this
shim automatically becomes a no-op.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from ptcg_agent.env.types import CanonicalState
from ptcg_agent.features import action_features as af
from ptcg_agent.policies.heuristic import get_action as _incumbent_get_action

if TYPE_CHECKING:
    from ptcg_agent.beliefs.opponent_model import BeliefState


OFFICIAL_AREA_ACTIVE = 4
OFFICIAL_AREA_BENCH = 5


def _translate_area(area: object) -> object:
    """Map an official in-play area to the incumbent scorer's area codes."""
    if (af.AREA_ACTIVE, af.AREA_BENCH) == (
        OFFICIAL_AREA_ACTIVE,
        OFFICIAL_AREA_BENCH,
    ):
        return area
    if area == OFFICIAL_AREA_ACTIVE:
        return af.AREA_ACTIVE
    if area == OFFICIAL_AREA_BENCH:
        return af.AREA_BENCH
    return area


def _translate_option(option: dict) -> dict:
    translated = dict(option)
    if "area" in translated:
        translated["area"] = _translate_area(translated["area"])
    if "inPlayArea" in translated:
        translated["inPlayArea"] = _translate_area(translated["inPlayArea"])
    return translated


def _scoring_view(state: CanonicalState) -> CanonicalState:
    """Return a shallow state copy whose legal options match legacy scoring."""
    translated = [_translate_option(option) for option in state.legal_options]
    return replace(state, legal_options=translated)


def get_action(
    state: CanonicalState,
    belief: "BeliefState | None" = None,
    return_details: bool = False,
) -> list[int] | tuple[list[int], list[float], list[dict]]:
    """Score official cabt options without changing their indices or the state."""
    return _incumbent_get_action(
        _scoring_view(state),
        belief=belief,
        return_details=return_details,
    )
