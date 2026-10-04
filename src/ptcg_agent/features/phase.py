"""
features/phase.py - Game phase detector (S3+).
"""
from enum import Enum
from ptcg_agent.env.types import CanonicalState

class GamePhase(Enum):
    OPENING = "opening"                 # Turns 1-2, setting up
    DEVELOPMENT = "development"         # Turn 3+, both setting up EXs
    PRESSURE = "pressure"               # Mid-game, attacking but not threatening lethal
    PRIZE_CONVERSION = "prize conversion" # Taking prizes actively
    STABILIZATION = "stabilization"     # Behind on prizes, trying to recover
    CLOSURE = "closure"                 # 1-2 prizes left, looking for lethal

def detect_phase(state: CanonicalState) -> GamePhase:
    """
    Detect the current phase of the game from the CanonicalState.
    """
    my_prizes = state.me.prizes_remaining
    op_prizes = state.opp.prizes_remaining
    
    # Closure: We are 1-2 prizes away from winning
    if my_prizes <= 2:
        return GamePhase.CLOSURE
        
    # Stabilization: Opponent is 1-2 prizes away from winning, we are behind
    if op_prizes <= 2 and my_prizes > op_prizes:
        return GamePhase.STABILIZATION
        
    # Opening: Very early game
    if state.turn <= 2:
        return GamePhase.OPENING
        
    # Prize Conversion: Someone has taken prizes
    if my_prizes < 6 or op_prizes < 6:
        if my_prizes < op_prizes:
            return GamePhase.PRIZE_CONVERSION
        elif op_prizes < my_prizes:
            # If we are slightly behind but they aren't in closure yet
            return GamePhase.STABILIZATION
            
    # Pressure vs Development
    # If we have an active with energy, we can apply pressure
    active_energy = len(state.me.active.energies) if state.me.active else 0
    if active_energy >= 2:
        return GamePhase.PRESSURE
        
    return GamePhase.DEVELOPMENT
