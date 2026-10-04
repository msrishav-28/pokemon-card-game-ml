"""
policies/baseline.py — Legal baseline policy (S1+).

Rules for baseline:
  always legal; prefer a cheap default (attack if legal else first legal).
"""
import random
from typing import List
from ptcg_agent.env.types import CanonicalState
from ptcg_agent.env.adapter import OPTION_TYPE_NAMES

def get_action(state: CanonicalState) -> List[int]:
    """
    Select an action index from the legal options.
    Returns a list of indices (cabt expects a list).
    """
    options = state.legal_options
    max_count = state.select_max_count
    
    if not 0 <= max_count <= len(options):
        raise ValueError("cabt invariant violated: maxCount exceeds options")
    if max_count == 0:
        return []

    # The project contract always returns exactly maxCount distinct indices.
    count_to_pick = state.select_max_count
    
    if count_to_pick == 1:
        # If we only need 1 choice, and attack is available, pick attack.
        attack_indices = [i for i, opt in enumerate(options) if opt.get("type") == 13]
        if attack_indices:
            return [attack_indices[0]]
            
    # If we need multiple choices, or no attack is available, pick the first N.
    return list(range(count_to_pick))
