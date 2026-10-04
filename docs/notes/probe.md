# Live `cabt` probe

Date: 2026-09-04

Host: Windows x64

Engine: `kaggle-environments==1.32.7`
Python used after repair: workspace-local `.venv`, CPython 3.12.14

## Canon read before probing

- `docs/canon/PTCG_AI_FIELD_ADDENDUM.md` section 6: deck-or-index action contract, reward enum, and 600-second overage bank.
- `docs/canon/PTCG_AI_BUILD_BIBLE.md` section 2: standing laws, especially environment first and zero invalid/timeout.

## Runtime repair evidence

The pre-existing `python` command was a stale virtual-environment shim. Its raw failure was:

```text
Unable to create process using '"C:\Users\Vignesh\AppData\Local\Programs\Python\Python311\python.exe" ...'
```

The Codex bundled CPython 3.12.14 worked but initially had no engine package:

```text
ModuleNotFoundError: No module named 'kaggle_environments'
```

A workspace-local `.venv` was created from that interpreter and the official `kaggle-environments` package was installed. The repository's editable install also exposed an invalid build backend (`setuptools.backends._legacy:_Backend`); `pyproject.toml` now uses `setuptools.build_meta`.

## Official engine probe

Command-equivalent probe:

```python
from kaggle_environments import make
env = make("cabt", debug=True)
env.run(["random", "first"])
```

Raw result:

```text
make_s 0.013
run_s 0.132
name cabt
statuses ["DONE", "DONE"]
rewards [-1, 1]
steps 38
errors null
```

The OpenSpiel game-list warnings printed during `kaggle_environments` import are unrelated package import noise; they did not affect `cabt` construction or execution.

## Frozen buddy probe

The archive contents and unpacked `refs/buddy-lucario/` files were SHA-256 compared. Every source file, `deck.pkl`, and supplied `libcg.so` matched the archive byte-for-byte. The locked deck contains 60 IDs and begins `[673, 673, 674, 674, 675, 675, 676, 676]`.

On Windows, importing the buddy package naively attempts to load a sibling `cg.dll`; initializing the official DLL a second time produced:

```text
buffer full. capacity:7
OSError: [WinError -529697949] Windows Error 0xe06d7363
```

The passing path does not vendor or initialize a second engine. It aliases the official package's already-initialized `kaggle_environments.envs.cabt.cg.sim` as the buddy module's `cg.sim`, then imports the untouched buddy `main.py` and supplies `buddy.agent` to `env.run`.

Raw live result:

```text
buddy_import True
deck_len 60
statuses ["DONE", "DONE"]
rewards [-1, 1]
steps 32
errors null
run_s 0.101
```

## Submission legal-floor probe

The required path form completed directly:

```python
env.run(["submission/main.py", "random"])
```

Raw result: `DONE/DONE`, rewards `[-1, 1]`, 109 steps, no engine error, 0.415 seconds.

The 20-game seat-balanced smoke test against `random` then produced:

```text
games 20
wins 11
losses 9
draws 0
win_rate 0.55
Wilson 95% CI [0.342, 0.742]
invalid 0
timeout 0
errors 0
mean decision latency 0.5 ms
```

This is a smoke test, not an improvement claim.
