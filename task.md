# S3 Execution Task List

- [x] Create `src/ptcg_agent/schema/action.py` (ActionType enum, ActionFeatureVector)
- [x] Create `src/ptcg_agent/features/phase.py` (Phase detection logic)
- [x] Create unit tests for phase detector in `tests/test_phase.py`
- [x] Create `src/ptcg_agent/features/action_features.py` (6 heuristic families)
- [x] Create `src/ptcg_agent/policies/heuristic.py` (Main scorer and selector)
- [x] Update `submission/main.py` to use heuristic policy
- [ ] Run 500 paired games against `random`/`baseline` to verify win rate CI
- [ ] Ensure 0 invalid actions and 0 timeouts over the run
- [ ] Generate 20 replays and inspect for mistakes (label in failure_taxonomy.md)
