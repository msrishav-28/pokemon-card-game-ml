# Pokémon TCG cabt Agent

A local, reproducible agent for the official Kaggle `cabt` environment. The
frozen player uses one locked 60-card Mega Lucario ex list and a visible-state
tactical AttackPlan. It returns only engine-provided option indexes, validates
the transport contract before every return, and falls back to the first legal
indexes if policy code ever fails.

Frozen player: **B3 AttackPlan**. The promoted `submission/main.py` scored
94.0% versus `random`, 82.5% versus `first`, and 49.0% versus the frozen buddy
agent (N=200 each). Across all 600 result-grade games it had zero invalid
actions, timeouts, errors, contract failures, or policy fallbacks.

| Opponent | N | W-D-L | Win rate | Wilson 95% CI | Invalid | Timeout |
|---|---:|---:|---:|---:|---:|---:|
| `random` | 200 | 188-0-12 | 94.0% | 89.8-96.5% | 0 | 0 |
| `first` | 200 | 165-0-35 | 82.5% | 76.6-87.1% | 0 | 0 |
| buddy-lucario | 200 | 98-0-102 | 49.0% | 42.2-55.9% | 0 | 0 |

See `docs/notes/freeze.md` for provenance, hashes, limitations, and exact
reproduction commands.

## Reproduce locally

Python 3.11+ is required. The verified environment used Python 3.12.14 and
`kaggle-environments==1.32.7`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with
`.venv/bin/python`.

Run the exact host entry point:

```powershell
.\.venv\Scripts\python.exe -c "from kaggle_environments import make; e=make('cabt',debug=True); e.run(['submission/main.py','random']); print(e.toJSON()['statuses'], e.toJSON()['rewards'])"
```

Run one readable local match, including the untouched buddy reference through
the platform-safe loader:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_match.py --opponent buddy
```

## Evaluation

The runner alternates seats, writes every observation/action plus a linked
`game_end` record to JSONL, and records Wilson intervals, action-contract
failures, latency, and remaining overage. Native cabt chance is not exposed as
a controllable seed, so results are labeled **seat-balanced**, not falsely
paired by engine seed.

```powershell
# Smoke only
.\.venv\Scripts\python.exe scripts\run_batch.py --agent submission/main.py --opponent random --n 20 --tag smoke

# Result-grade run
.\.venv\Scripts\python.exe scripts\run_batch.py --agent submission/main.py --opponent buddy --n 200 --tag final-buddy-200

# Audit retained live replay fixtures
.\.venv\Scripts\python.exe scripts\diagnose_replays.py fixtures\replays
```

Runs below 50 games are called smoke tests. Improvement claims in this repo use
N=200 or more against the same frozen opponent. Full local replay streams are
ignored because they are large; compact byte-for-byte live games and hashes
are retained under `fixtures/replays/`.

## Build the portable agent bundle

```powershell
.\.venv\Scripts\python.exe scripts\build_submission.py
```

This creates `dist/cabt-agent/` and `dist/cabt-agent.zip`, including a SHA-256
manifest and unchanged official EN metadata. The runtime allowlist contains
only the entry point, deck, canonical adapter/types, and AttackPlan policy. It
does not contain the buddy implementation, evaluation code, search code, or
any native library; `kaggle-environments` remains the only rules engine.
Verify the emitted entry point with:

```powershell
.\.venv\Scripts\python.exe -c "from kaggle_environments import make; e=make('cabt',debug=True); e.run(['dist/cabt-agent/main.py','random']); print(e.toJSON()['statuses'])"
```

## Repository map

```text
docs/canon/          Bible + field addendum (read-only)
docs/notes/          probe, bets, doctrine difference, eval protocol, freeze
data/official/       unchanged official CSV data; optional PDFs stay local
refs/buddy-lucario/  frozen read-only reference opponent
refs/ladder/         frozen leaderboard table (not card data)
fixtures/            live observation and compact replay fixtures
submission/          host entry point and locked deck
src/ptcg_agent/      adapter, policies, evaluator, diagnostics
scripts/             probes, batch evaluation, replay audit, bundle build
tests/               contract, adapter, policy, evaluator, packaging tests
```

No competition upload command is provided: Simulation submissions are closed,
and the project is evaluated locally.

## Evidence and design notes

- `docs/notes/freeze.md`: release identity, result-grade measurements, hashes,
  verification, and known limits.
- `docs/notes/probe.md`: official engine and buddy import probe.
- `docs/notes/eval_protocol.md`: seats, randomness, outcomes, and replay schema.
- `docs/notes/bets.md`: pre-registered changes and their measured decisions.
- `docs/notes/doctrine_diff.md`: evidence for replacing the linear scorer.
- `docs/notes/failure_taxonomy.md`: replay-derived signals and evidence limits.
- `fixtures/replays/README.md`: retained byte-for-byte live game fixtures.
