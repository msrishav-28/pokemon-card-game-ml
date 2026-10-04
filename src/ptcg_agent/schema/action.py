"""
schema/action.py - Action feature schema for S3 heuristics.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Any

class ActionType(Enum):
    PLAY_BASIC = "PLAY_BASIC"
    PLAY_TRAINER = "PLAY_TRAINER"
    ATTACH_ENERGY = "ATTACH_ENERGY"
    EVOLVE = "EVOLVE"
    RETREAT = "RETREAT"
    ATTACK = "ATTACK"
    USE_ABILITY = "USE_ABILITY"
    END_TURN = "END_TURN"
    OTHER = "OTHER"

@dataclass
class ActionFeatureVector:
    prize_race: float = 0.0
    tempo: float = 0.0
    board: float = 0.0
    resources: float = 0.0
    risk: float = 0.0
    endgame: float = 0.0

@dataclass
class ActionWrapper:
    index: int
    raw_option: dict[str, Any]
    action_type: ActionType
    features: ActionFeatureVector
    total_score: float = 0.0
