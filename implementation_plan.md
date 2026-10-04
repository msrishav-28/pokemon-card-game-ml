# S3 Implementation Plan

## Goal Description
Implement **Stage 3 (Heuristic Tactical Agent)**, the first real player policy for the locked Mega Lucario ex deck. This involves replacing the S1 baseline with a feature-driven scorer.

## User Review Required
No major architectural blockers, but please review the approach to the six feature families and phase detection below.

## Proposed Changes

### 1. `src/ptcg_agent/schema/action.py` [NEW]
Define typed action wrappers so we aren't just passing raw `option` dicts around:
- `ActionType` enum (Attack, PlayTrainer, AttachEnergy, Retreat, Evolve, etc.)
- `ActionFeatureVector` dataclass (stores the 6 feature families)

### 2. `src/ptcg_agent/features/phase.py` [NEW]
Phase detector to identify the current game phase:
- `detect_phase(state: CanonicalState) -> str`
- Rules based on: turn number, prizes remaining, EX Pokemon in play.
- Will include a robust suite of unit tests.

### 3. `src/ptcg_agent/features/action_features.py` [NEW]
Implementation of the 6 feature families (specifically tuned for the Fighting/Lucario deck without full lookahead):
1. **Prize race:** Calculate potential KO on opponent active.
2. **Tempo:** Score energy attachments (prioritize Makuhita/Riolu/Lucario).
3. **Board:** Score playing basics to bench, evolving (Makuhita -> Hariyama, Riolu -> Lucario).
4. **Resources:** Score playing supporters (Carmine, Lillie's Determination).
5. **Risk:** Penalize retreating into fragile basics without energy.
6. **Endgame:** Score playing Boss's Orders if it secures a lethal blow on a bench EX.

### 4. `src/ptcg_agent/policies/heuristic.py` [NEW]
The main heuristic policy.
- Scores every legal action using `action_features.py`.
- Selects the action with the highest scalar score.

### 5. `submission/main.py` [MODIFY]
Update the agent entry point to load `heuristic.py` for its decisions.
- Will still fall back to `baseline.py` logic if the engine asks for multiple generic target selections that the heuristic doesn't perfectly rank yet.

## Verification Plan

### Automated Tests
- Unit tests for `detect_phase` on synthetic `CanonicalState` fixtures.

### Local Simulation
- **500 paired games** vs S1 baseline (using the same Lucario deck).
- Record the Wilson 95% Confidence Interval.
- Validate **0 invalid actions** and **0 timeouts**.
- Dump 20 replays for manual inspection of agent mistakes.
