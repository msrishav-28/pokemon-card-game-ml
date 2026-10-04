# B3 AttackPlan freeze

**Freeze date:** 2026-10-04

**Status:** accepted local release candidate

**Engine:** official `kaggle-environments==1.32.7` `make("cabt")`

**Deck:** locked 60-card buddy Lucario list

## Decision

Freeze the promoted `submission/main.py` AttackPlan player. It clears the
project's physics gates: official cabt is the only rules engine, every battle
action is selected from the engine's legal option list, the locked deck is
unchanged, all result-grade games finish within the overage bank, and the
player materially beats the frozen linear incumbent.

No search, value model, PPO, second deck, Python rules clone, or vendored
native library is part of this release. No competition submission was made.

## Result-grade promoted-entry evaluation

Every row used N=200, exactly 100 games from each seat, the same locked deck,
and the actual `submission/main.py` host entry. Native engine chance is not
seed-controllable, so these are seat-balanced independent samples rather than
paired-seed claims.

| Opponent | W-D-L | Win rate | Wilson 95% CI | Invalid | Timeout | Error | Fallback | p95 decision | Min overage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `random` | 188-0-12 | 94.0% | 89.8-96.5% | 0 | 0 | 0 | 0 | 0.943 ms | 599.608 s |
| `first` | 165-0-35 | 82.5% | 76.6-87.1% | 0 | 0 | 0 | 0 | 0.920 ms | 599.538 s |
| buddy-lucario | 98-0-102 | 49.0% | 42.2-55.9% | 0 | 0 | 0 | 0 | 0.824 ms | 599.257 s |

Across the trio: 600 completed games, 451 wins, 149 losses, zero draws, and
zero invalid, timeout, engine-error, runner-error, contract-failure,
exception, or policy-fallback events. The player made 33,664 decisions. The
buddy result is near parity but its confidence interval includes 50%; it is
not evidence that this player is stronger than buddy.

The architecture gate is separate and decisive: AttackPlan beat the frozen
incumbent 156-44 over 200 direct games, 78.0% with Wilson 95% CI
[71.8%, 83.2%], while retaining zero safety failures.

## Evaluation artifacts

Full replays remain local under ignored `output/replays/`; compact exact games
and adjacent source hashes are retained in `fixtures/replays/`. Independent
checks reconciled every terminal record to its summary.

| Opponent | Summary SHA-256 | Replay SHA-256 |
|---|---|---|
| `random` | `7db93707bcb2e0b3d1ee3a87e3a9de064a81196120f3e42a85721013a7572e32` | `71c1ed395a0d8b50eca8093d3b6287d34ea593e55bb3bc00bbccd0c8db8b8535` |
| `first` | `923dbbb13898ab6b7cc60272acb30da3192939749e1e908fa0f30456278df64a` | `ce5bbce833905cbabd7aceaf36b89eeb5de490fbe6704a00543c54cea5c4b0fc` |
| buddy-lucario | `387a501a520ded77bd5238ed8446a41d7566b10a9fb6164c6dba8e39bf2b92a1` | `1e656596c4833b11298264e77269ca3f0948733f14804bdc7e1e9ade96387e03` |

Summary files:

- `output/experiments/exp_20261003_162915_039009_final-submission-random-200.json`
- `output/experiments/exp_20261003_162922_701352_final-submission-first-200.json`
- `output/experiments/exp_20261003_162928_450627_final-submission-buddy-200.json`

## Released runtime identity

The final bundle was rebuilt after its exact-path smoke test. It contains no
development/evaluation modules, buddy code, refs, search code, or native
library.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `dist/cabt-agent.zip` | 83,703 | `3d23ac718412a5b5cdbc572376466e7fbcd8a8f4717f91a9b2a98bd6f9197b2f` |
| bundle `manifest.json` | 1,870 | `81a2752cfa03721b3303064a3d29d371c5efff22c927eae9844dc2b8767ed19e` |
| `submission/main.py` | 6,226 | `9b7cc5523ea901b047f62203b2ff9db3fd6335daf1c5bb497df0d521d03266b1` |
| `planned_candidate.py` | 33,908 | `bc33ff1bcc897daeabdf2cab67b1255e782bd866be61b326e546594f789b8e6a` |
| canonical adapter | 12,869 | `eb8168f1306c40147b8ceba94d29fc4a9df0a50927ade1203f2254dc429fa85d` |
| canonical types | 2,691 | `e6263a40c8ab5faefca5d30f398432d73f23a29e28529b81643cb2113131c963` |
| `deck.csv` | 305 | `406e2e9bd6ae82b8008b16ee64ffcbb58e4a50cd6bc36e33ae655456c6b9afee` |
| official EN CSV | 358,345 | `507d8d670c9c3c8d58f400d42eed09270b6b01354332770081bdb455d53b8c84` |

The uncompressed bundle is 416,523 bytes against the 207,303,475-byte worker
limit. `dist/` is intentionally ignored; rebuild it from the pushed source
with `scripts/build_submission.py` and compare the per-file manifest hashes.

## Verification performed

- Python 3.12.14 on Windows 11.
- `136 passed` from the complete pytest suite.
- `python -m compileall -q submission src scripts tests` completed.
- `python -m pip check` reported no broken requirements.
- `git diff --check` reported no content errors.
- Replay audit: 600 terminals, 56,131 decisions, zero malformed records, zero
  ungrouped decisions, and every loss linked to its game's decisions.
- Exact bundle invocation through official cabt finished `DONE/DONE`, reward
  `[1, -1]`, in 92 engine steps.
- Bundle manifest hashes and native-library exclusions passed package tests.

Reproduce the important checks:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\diagnose_replays.py fixtures\replays
.\.venv\Scripts\python.exe scripts\build_submission.py
.\.venv\Scripts\python.exe -c "from kaggle_environments import make; e=make('cabt',debug=True); e.run(['dist/cabt-agent/main.py','random']); print(e.toJSON()['statuses'], e.toJSON()['rewards'])"
```

Run fresh result-grade evaluation with:

```powershell
.\.venv\Scripts\python.exe scripts\run_batch.py --agent submission/main.py --opponent random --n 200 --tag final-random-200
.\.venv\Scripts\python.exe scripts\run_batch.py --agent submission/main.py --opponent first --n 200 --tag final-first-200
.\.venv\Scripts\python.exe scripts\run_batch.py --agent submission/main.py --opponent buddy --n 200 --tag final-buddy-200
```

## Provenance and known limits

- The final summaries record Git commit
  `5f463b8d2f38162d63d46bb97df6bece2348ca47` and `git_dirty=true`.
  They do not embed hashes of imported modules. The orchestrated run did not
  edit runtime source while those evaluations were active, but that fact is
  operational provenance rather than cryptographic proof. The runtime table
  and bundle manifest define the frozen bytes.
- Native cabt chance is unseeded. Seat balance controls position, not draws,
  prizes, or other native randomness.
- All 149 gameplay losses are result-linked, but the replay schema has no
  explicit causal-decision reference. Their causes remain unclassified.
- Six conservative last-prize signals require same-turn sequencing analysis;
  they are not labeled missed lethal. B4 records the diagnostic gate.
- The bundle was exercised on Windows. It relies on the platform-specific
  native library installed by official `kaggle-environments`; no Kaggle Linux
  worker was available for a second platform smoke.

## Unfreeze rule

Do not replace this player because a new architecture looks stronger. A
candidate must first preserve zero invalid, timeout, error, and fallback
events; beat this freeze directly in at least 200 seat-balanced games with a
Wilson lower bound above 50%; and avoid material regression in a fresh N=200
trio against `random`, `first`, and frozen buddy. B4 turn-sequence diagnostics
is the next recorded bet.
