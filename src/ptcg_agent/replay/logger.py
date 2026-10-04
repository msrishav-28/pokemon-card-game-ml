"""
replay/logger.py — JSONL replay logger (S1+).

Writes one line per decision in JSONL format for later inspection.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from ptcg_agent.env.types import CanonicalState

_REPLAY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "output", "replays")
_CURRENT_EPISODE_ID: str | None = None

def new_episode_id() -> str:
    global _CURRENT_EPISODE_ID
    _CURRENT_EPISODE_ID = f"ep_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    return _CURRENT_EPISODE_ID

def get_current_episode_id() -> str:
    global _CURRENT_EPISODE_ID
    if _CURRENT_EPISODE_ID is None:
        _CURRENT_EPISODE_ID = f"ep_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    return _CURRENT_EPISODE_ID

def get_replay_path() -> str:
    os.makedirs(_REPLAY_DIR, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    return os.path.join(_REPLAY_DIR, f"replay_{date_str}.jsonl")

def log_turn(state: CanonicalState,
             action_indices: list[int],
             episode_id: str | None = None,
             scores: list[float] | None = None,
             features: list[dict] | None = None):
    """
    Log the current state and chosen actions to a JSONL file.

    Fields:
      ts, episode_id, turn, player, context, maxCount, chosen, remaining_overage_time, brief_state
      (plus optional scores and features)
    """
    try:
        path = get_replay_path()
        ep_id = episode_id or get_current_episode_id()
        brief_state = {
            "my_active_id": state.me.active.card_id if state.me.active else None,
            "my_active_hp": state.me.active.hp if state.me.active else 0,
            "my_bench_count": len(state.me.bench),
            "my_hand_count": state.me.hand_count,
            "my_prizes_remaining": state.me.prizes_remaining,
            "opp_active_id": state.opp.active.card_id if state.opp.active else None,
            "opp_active_hp": state.opp.active.hp if state.opp.active else 0,
            "opp_prizes_remaining": state.opp.prizes_remaining,
        }
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "episode_id": ep_id,
            "turn": state.turn,
            "player": state.your_index,
            "context": state.select_context,
            "maxCount": state.select_max_count,
            "chosen": action_indices,
            "remaining_overage_time": state.remaining_overage_time,
            "brief_state": brief_state,
        }
        if scores is not None:
            record["scores"] = [round(s, 2) for s in scores]
        if features is not None:
            record["features"] = features

        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        # Never crash the agent because logging failed
        pass
