# Local evaluation protocol

The canonical runner is `scripts/run_batch.py`. It accepts `random`, `first`,
and `buddy` (the untouched `refs/buddy-lucario/main.py`) through one opponent
loader. The buddy loader imports its Python policy and card API while reusing
the native library already initialized by the official `kaggle-environments`
package. It does not load or vendor the buddy's Linux `libcg.so`.

Every run writes:

- one experiment JSON with the engine version, deck and opponent names and
  fingerprints, Git commit and dirty flag, W/D/L and Wilson interval, separate
  invalid/timeout/error counters, decision timing, final overage time when the
  engine exposes it, seat splits, and per-game records;
- one JSONL file containing every decision made by both players. A decision
  record includes the exact live observation, returned action, structural
  contract check, duration, and observed `remainingOverageTime`.

For file agents that expose the repository's legacy `log_turn` hook, the
runner disables that separate daily logger for the duration of the loaded
agent module. The experiment JSONL is the single evaluation record, avoiding
duplicate records with no terminal `game_id` and avoiding concurrent append
races.

For W/D/L, an agent `INVALID`, `TIMEOUT`, or `ERROR` status is a loss, and the
same status from the opponent is an agent win. Clean games use cabt's reward.
The structural precheck covers action type, required length, index range, and
unique selection indices; the official engine remains the legality authority.

## Seed finding

`kaggle-environments==1.32.7` accepts an extra `configuration={"seed": ...}`
value for `cabt`, but `envs/cabt/cabt.py` never reads it and the native battle
API exposes no seed argument. `env.info` also remains empty.

An empirical check ran two `first` versus `first` games with requested seed
`12345`. Their first observable seven-card hands were different:

```text
[3, 1092, 722, 3, 3, 3, 1219]
[3, 3, 1227, 3, 721, 3, 3]
```

Therefore the runner does **not** claim paired chance seeds. It alternates the
agent's seat and labels the design `seat-paired`. `--seed` resets Python's RNG
to the same value within each two-seat pair (useful for Python policies such as
the built-in random opponent), while every record truthfully stores
`engine_seed: null` and `engine.seed_control: false`.

Example:

```powershell
.venv/Scripts/python.exe scripts/run_batch.py --n 20 --opponent random --tag random-smoke
```

An odd `--n` is allowed and run exactly; the summary reports the one unpaired
seat game. Runs below 50 games are smoke tests, not improvement evidence.
