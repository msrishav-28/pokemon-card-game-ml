"""Evaluation-only entry point for the opt-in official-area candidate."""
from __future__ import annotations

from pathlib import Path

from ptcg_agent.beliefs.opponent_model import BeliefState
from ptcg_agent.env.adapter import to_canonical
from ptcg_agent.policies.official_area_candidate import get_action


_ROOT = Path(__file__).resolve().parents[2]
DECK_IDS = [
    int(line)
    for line in (_ROOT / "submission" / "deck.csv").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
if len(DECK_IDS) != 60:
    raise ValueError("locked deck must contain exactly 60 card IDs")

_belief: BeliefState | None = None
_last_decision_telemetry: dict | None = None


def _fallback(obs: dict) -> list[int]:
    select = obs["select"]
    count = int(select["maxCount"])
    options = select["option"]
    if not 0 <= count <= len(options):
        raise ValueError("cabt invariant violated: maxCount exceeds options")
    return list(range(count))


def _valid(action: object, obs: dict) -> bool:
    select = obs["select"]
    return (
        isinstance(action, list)
        and len(action) == int(select["maxCount"])
        and all(type(index) is int for index in action)
        and len(action) == len(set(action))
        and all(0 <= index < len(select["option"]) for index in action)
    )


def agent(obs: dict, config: dict | None = None) -> list[int]:
    del config
    global _belief, _last_decision_telemetry
    if obs.get("select") is None:
        _belief = None
        _last_decision_telemetry = {"phase": "deck", "policy_fallback": False}
        return list(DECK_IDS)

    try:
        state = to_canonical(obs)
        if _belief is None:
            _belief = BeliefState()
        _belief.update(state)
        action, scores, features = get_action(
            state, belief=_belief, return_details=True
        )
        if not _valid(action, obs):
            raise ValueError("candidate returned invalid selection")
        _last_decision_telemetry = {
            "phase": "selection",
            "policy_fallback": False,
            "scores": scores,
            "features": features,
        }
        return action
    except Exception as exc:
        _last_decision_telemetry = {
            "phase": "selection",
            "policy_fallback": True,
            "policy_error": f"{type(exc).__name__}: {exc}",
        }
        return _fallback(obs)
