"""
submission/main.py — Thin entry point for the cabt engine.

Contract:
  if obs["select"] is None:
      return DECK_IDS          # exactly 60 card IDs
  else:
      return list[int]         # length == obs["select"]["maxCount"]
                               # each value indexes into obs["select"]["option"]
"""
import os
import sys
import json

# ---------------------------------------------------------------------------
# sys.path: add src/ so ptcg_agent is importable locally and on Kaggle
# ---------------------------------------------------------------------------
try:
    _THIS_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _THIS_DIR = "/kaggle_simulations/agent"

# When running from the repo, _THIS_DIR == .../submission → src is one level up.
# When bundled on Kaggle, everything is flat under /kaggle_simulations/agent.
_SRC_DIR = (
    os.path.join(os.path.dirname(_THIS_DIR), "src")
    if os.path.basename(_THIS_DIR) == "submission"
    else os.path.join(_THIS_DIR, "src")
)
if os.path.exists(_SRC_DIR) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# ---------------------------------------------------------------------------
# Load deck (hardcoded fallback first, then override from file if present)
# ---------------------------------------------------------------------------
DECK_IDS = [
    673, 673, 674, 674, 675, 675, 676, 676, 676,
    677, 677, 677, 678, 678, 678, 678,
    1102, 1102, 1102, 1102, 1123, 1123,
    1141, 1141, 1141, 1141, 1142, 1142, 1142, 1142,
    1152, 1152, 1152, 1152, 1159,
    1182, 1182, 1192, 1192, 1192, 1192,
    1227, 1227, 1227, 1227, 1252, 1252,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
]

_search_dirs = [_THIS_DIR, "/kaggle_simulations/agent"]
for _d in _search_dirs:
    for _fname in ["deck.json", "deck.csv"]:
        _p = os.path.join(_d, _fname)
        if os.path.exists(_p):
            try:
                if _p.endswith(".json"):
                    with open(_p) as _f:
                        DECK_IDS = json.load(_f)
                else:
                    with open(_p) as _f:
                        DECK_IDS = [int(line.strip()) for line in _f if line.strip()]
                break
            except Exception:
                pass
    else:
        continue
    break  # stop after first directory that yielded a file

assert len(DECK_IDS) == 60, f"Deck has {len(DECK_IDS)} cards, need 60"

# ---------------------------------------------------------------------------
# Import agent modules (fail gracefully if missing — see fallback below)
# ---------------------------------------------------------------------------
try:
    from ptcg_agent.env.adapter import to_canonical
    from ptcg_agent.policies.planned_candidate import get_action, reset_policy
    _MODULES_LOADED = True
except ImportError:
    _MODULES_LOADED = False

_policy_fallback_count = 0
_last_policy_error: str | None = None
_last_decision_telemetry: dict | None = None


def _first_legal_selection(obs) -> list[int]:
    """Return the engine-oracle fallback for a battle selection."""
    select = obs["select"]
    max_count = int(select["maxCount"])
    option_count = len(select["option"])
    if not 0 <= max_count <= option_count:
        # Live cabt guarantees this invariant. Raising is safer than emitting a
        # knowingly malformed action if a non-cabt caller violates it.
        raise ValueError("cabt invariant violated: maxCount exceeds options")
    return list(range(max_count))


def _is_legal_selection(action, obs) -> bool:
    """Validate only the index contract; cabt already validates game rules."""
    if not isinstance(action, list):
        return False
    select = obs["select"]
    option_count = len(select["option"])
    if len(action) != int(select["maxCount"]):
        return False
    if any(type(index) is not int for index in action):
        return False
    return len(set(action)) == len(action) and all(
        0 <= index < option_count for index in action
    )


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------
def agent(obs, config=None):
    """
    Main agent entry point for cabt.

    Phase A (select is None): return 60 card IDs.
    Phase B (select is not None): return list[int] of length maxCount,
        each value an index into obs["select"]["option"].
    """
    global _policy_fallback_count, _last_policy_error, _last_decision_telemetry

    if obs.get("select") is None:
        # The tactical planner is stateful within a game. The engine's deck
        # request is the authoritative new-game boundary.
        _policy_fallback_count = 0
        _last_policy_error = None
        _last_decision_telemetry = {"phase": "deck", "policy_fallback": False}
        if _MODULES_LOADED:
            reset_policy()
        return list(DECK_IDS)

    if not _MODULES_LOADED:
        _last_decision_telemetry = {
            "phase": "selection",
            "policy_fallback": True,
            "policy_error": "agent modules unavailable",
        }
        return _first_legal_selection(obs)

    try:
        # B3 policy: canonical observation -> deck-specific tactical plan.
        state = to_canonical(obs)
        action_indices, scores, features = get_action(state, return_details=True)
        if not _is_legal_selection(action_indices, obs):
            raise ValueError("policy returned an invalid index selection")
        _last_decision_telemetry = {
            "phase": "selection",
            "policy_fallback": False,
            "scores": scores,
            "features": features,
        }
        return action_indices
    except Exception as exc:
        # Strategy failures must degrade to the engine's first-index oracle,
        # never to an INVALID action. Counters remain inspectable by local eval.
        _policy_fallback_count += 1
        _last_policy_error = f"{type(exc).__name__}: {exc}"
        _last_decision_telemetry = {
            "phase": "selection",
            "policy_fallback": True,
            "policy_error": _last_policy_error,
        }
        return _first_legal_selection(obs)
