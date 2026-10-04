# PTCG AI Field Addendum

**Status:** companion canon. Read after the Bible. Does not replace it.  
**Date locked:** 2026-09-01  
**Purpose:** freeze everything learned from official Kaggle pages, Kaggle GitHub repos, the attached Lucario agent bundle, the frozen Simulation leaderboard export, and the Strategy data tab — so a later coding agent cannot re-invent the contest interface.

If this file and `PTCG_AI_BUILD_BIBLE.md` disagree on **architecture, stages, or gates**, the Bible wins.  
If this file and the Bible disagree on **contest interface, dates, worker limits, or agent I/O**, this file wins (it was checked against primary sources on 2026-09-01).

Do not paste this file plus the Bible plus the three old briefs into one agent session. Use the Bible for S0–S7. Use this file when the work touches Kaggle, `cabt`, CLI, Docker, decks-as-IDs, or Strategy eligibility.

---

## 0. What this file adds that the Bible did not have

The Bible was written as a *build doctrine*. This file is the *field sheet*.

New, verified facts:

1. `cabt` is a first-class environment inside `Kaggle/kaggle-environments`, not a private side SDK.
2. Exact agent I/O (deck phase vs option-index phase) from `cabt.py` + official tests.
3. Exact `cabt.json` timeouts and reward enum.
4. Native engine binaries shipped in the public repo (Linux / Windows / macOS Intel / ARM64).
5. Official Dockerfile base image.
6. Official kaggle-cli simulation workflow (download, submit shape, episode replay, logs).
7. Frozen Simulation leaderboard snapshot (6,807 teams; #1 μ = 1398.2 on 2026-09-01).
8. Full Strategy rubric weights, writeup rules, prize table, team-identity rule.
9. Contents of `buddy-other-pokemon-v1.tar.gz` (working Lucario rules agent).
10. Strategy Data tab is a usable source of `EN Card Data.csv` when Simulation Data is locked.
11. Worker hardware and path `/kaggle_simulations/agent/`.

---

## 1. Primary sources used

### Official contest pages (user-supplied text, 2026-09-01)

- Simulation Overview / Evaluation / Data / Rules  
  https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/overview
- Strategy Overview / Evaluation / Data / Rules  
  https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy/overview

### Official GitHub (read via GitHub connector, 2026-09-01)

- https://github.com/Kaggle/kaggle-cli
- https://github.com/Kaggle/kaggle-cli/blob/main/docs/simulation_competitions.md  
  commit family `659469c` / file SHA `ae7ec94`
- https://github.com/Kaggle/kaggle-environments  
  tree SHA `28b6d8af3ce73926b3d0fda1410c1ddd8384ab8c` (master at fetch)
- https://github.com/Kaggle/kaggle-environments/blob/master/docker/Dockerfile
- `kaggle_environments/envs/cabt/cabt.py`
- `kaggle_environments/envs/cabt/cabt.json`
- `tests/envs/cabt/test_cabt.py`

### Local artifacts attached in this project

- `/home/workdir/attachments/buddy-other-pokemon-v1.tar.gz`  
  unpacked: `main.py`, `deck.pkl`, `cg/` (dated 2026-06-26)
- `/home/workdir/attachments/pokemon-tcg-ai-battle-privateleaderboard-2026-09-01T15_46_13.zip`  
  inner CSV dated 2026-09-01 15:46

### Engine API (not in the four GitHub links; still required)

- https://matsuoinstitute.github.io/cabt/

### Do not treat as official card IDs

- Random Pokédex CSVs, Pokémon TCG Pocket databases, Showdown dumps, `PokemonTCG/pokemon-tcg-data`.  
  Those IDs are a different numbering system.

---

## 2. Two-track contest, restated with page-level precision

### 2.1 Simulation — `pokemon-tcg-ai-battle`

What you submit: a **running agent**, not a spreadsheet.

| Item | Official value |
|---|---|
| Start | 2026-06-16 11:00 UTC |
| Entry deadline | 2026-08-09 |
| Team merger | 2026-08-10 |
| Final submission deadline | 2026-08-17 |
| Post-deadline games | ~2026-08-17 to ~2026-08-31 (page text; later freeze used 31 Aug in one paragraph and “approx two weeks” in another) |
| Daily uploads | 5 |
| Active agents per team | latest **2** |
| Leaderboard display | best scoring agent only |
| Initial μ after validation | **600** |
| Validation | one self-play episode; failure → status Error + downloadable logs |
| Matchmaking | similar-μ pairing; new agents get extra games |
| Update rule | Gaussian N(μ, σ²); win raises winner μ / lowers loser μ; draw pulls μ together; **score margin does not matter** |
| Private leaderboard | **none** (Simulation page: “There is no Private Leaderboard in Simulation competitions.”) |
| Money on this track | **none** |
| Points / medals | yes (Kaggle ranking track) |

Worker (Simulation FAQ):

| Resource | Limit |
|---|---|
| Submission size | **197.7 MiB** |
| HDD | 11.8 GiB |
| RAM | 12.2 GiB |
| vCPUs | **2** |
| Files on disk at runtime | `/kaggle_simulations/agent/` |
| Network during an episode | **no ingress, no egress** |

How-to-Submit text on the Simulation page:

> bundle `.tar.gz` with `main.py` at the **top level** (not nested) and include a `deck.csv`.  
> `tar -czvf submission.tar.gz *`

The buddy bundle used `deck.pkl` instead of `deck.csv`. Both exist in the wild. Prefer `deck.csv` if writing a new bundle that claims to follow the page. The engine’s first action is still “return 60 integer card IDs,” however they were stored.

Code reference on the page: environment as of `kaggle-environments` **1.14.10**, latest on GitHub.

### 2.2 Strategy — `pokemon-tcg-ai-battle-challenge-strategy`

What you submit: **one Kaggle Writeup**, not a new bot upload.

| Item | Official value |
|---|---|
| Start | 2026-06-16 11:00 UTC |
| Entry + team merger | **2026-09-06** |
| Final writeup deadline | **2026-09-13** |
| Judging | 2026-09-14 → 2026-10-11 (subject to volume) |
| Submissions per team | **one** |
| Word limit | **2000**; over-limit may be penalized |
| Required | title, subtitle, Track selected, detailed analysis |
| Optional | Media Gallery, notebooks, repos, links |
| Prize | **$240,000** = 8 finalists × **$30,000** |
| Extra | possible in-person tournament, Tokyo, date TBD |
| Winner license | MIT (plus Pokémon-element restrictions) |
| Data license | Competition Use Only; delete after the event |

Judging table (official weights):

| Category | Weight | What they say they score |
|---|---|---|
| Model Score | **70%** | clarity of approach; originality + technical soundness; consistency under repeated matches; not overfit to openers / matchups; **Simulation-track performance** |
| Deck Score | **20%** | deck concept articulated; key cards used to support the plan |
| Report Score | **10%** | structure, writing, figures/tables |

Eligibility that people miss:

1. Strategy page: participation in Simulation is **required** for a complete submission.
2. Strategy rules §2.1.c: prize-eligible teams must be the **same team** on both divisions. Membership changes must be mirrored.
3. Pokémon card images in the Media Gallery that violate the Pokémon Elements license → DQ.
4. Attaching a private Kaggle Resource to a public Writeup **makes that resource public after the deadline**.

As of 2026-09-01: Strategy is still open. Simulation bot uploads are not.

### 2.3 What “I have the Strategy dataset” means

Strategy Data tab: **8 files, 641.48 MB**, types `pdf` + `csv`.

Files named on both pages:

- `Card_ID_List_EN.pdf`
- `Card_ID_List_JP.pdf`
- `EN Card Data.csv`
- `JP Card Data.csv`

CSV schema (official):

Card ID, Card Name, Expansion, Collection No., Stage (Pokémon) / Type (Energy and Trainer), Rule, Category, Previous stage, HP, Type, Weakness, Resistance (Type), Retreat, Move Name, Cost, Damage, Effect Explanation.

English and Japanese CSVs are the same rows, different language on names/text.

This catalog maps **simulator integer IDs** to human card text. It is not replay data and not a trained model.

If Simulation Data is 403/locked for an account that never entered before 9 Aug, the Strategy Data tab can still supply the same CSVs **if that account accepted Strategy rules**. That does not by itself create Simulation prize eligibility.

Rules on both tracks: Competition Data is not for republication, not for products that compete with Pokémon, and should be deleted when the competition ends.

---

## 3. Frozen Simulation ladder (attached zip)

File: `pokemon-tcg-ai-battle-privateleaderboard-2026-09-01T15_46_13.zip`  
Inner: `pokemon-tcg-ai-battle-privateleaderboard-2026-09-01T15:46:13.csv`

Columns: `Rank, TeamId, TeamName, LastSubmissionDate, Score, SubmissionCount, TeamMemberUserNames`  
Rows: **6,807** teams (header excluded).

Top 8 as exported:

| Rank | Team | Score (μ) | LastSubmissionDate | Members |
|---|---|---|---|---|
| 1 | Luca | 1398.2 | 2026-08-16 23:38:16 | yijiey |
| 2 | palsystem | 1297.8 | 2026-08-16 23:57:19 | ebinan92, kcotton21 |
| 3 | Unown Gradiant | 1280.5 | 2026-08-16 17:32:13 | dipamc77 |
| 4 | flg | 1266.1 | 2026-08-16 23:56:26 | ferdinandlimburg |
| 5 | Petit Canard | 1257.3 | 2026-08-16 21:17:11 | petitcanard |
| 6 | KawattaTaido | 1229.5 | 2026-08-16 17:29:15 | kawattataido |
| 7 | LumenLiquidity | 1226.6 | 2026-08-16 23:40:56 | giovannibaldon, pasqualemadd4loni |
| 8 | やる気元気ミワハルキ | 1214.2 | 2026-08-16 23:42:16 | cnumber, confirm, harukimiwa, masayoshi64, tomo0608 |

Notes for the Bible’s L9:

- Last uploads cluster on **16 Aug 2026**, consistent with the 17 Aug deadline.
- `SubmissionCount` in this export is **2** for the top rows (the two active agents), not lifetime upload count.
- This file is **not** `EN Card Data.csv`. Do not feed it to an adapter.

Treat #1 μ ≈ 1400 as the empirical ceiling of the closed ladder, not as a local-win-rate target.

---

## 4. kaggle-cli — what the repo is for

Repo: https://github.com/Kaggle/kaggle-cli  
Install: `pip install kaggle` (Python **3.11+**).

Auth options from `docs/README.md`:

1. `kaggle auth login` (OAuth)
2. `export KAGGLE_API_TOKEN=...`
3. `~/.kaggle/access_token`
4. Legacy `~/.kaggle/kaggle.json`

Rules acceptance is **in the browser**. The CLI cannot skip it. Verify with:

```bash
kaggle competitions list --group entered
```

### Simulation-competition tutorial commands

Doc: `docs/simulation_competitions.md`. Examples use `connectx`; replace with `pokemon-tcg-ai-battle`.

```bash
kaggle competitions list -s simulation
kaggle competitions pages pokemon-tcg-ai-battle
kaggle competitions pages pokemon-tcg-ai-battle --content
kaggle competitions topics list pokemon-tcg-ai-battle -s top --page-size 10
kaggle competitions download pokemon-tcg-ai-battle -p data/official

# historical submit shapes (Simulation uploads are closed; keep for format)
kaggle competitions submit pokemon-tcg-ai-battle -f main.py -m "v1"
tar -czf submission.tar.gz main.py helper.py model_weights.pkl
kaggle competitions submit pokemon-tcg-ai-battle -f submission.tar.gz -m "multi"

kaggle competitions submissions pokemon-tcg-ai-battle
kaggle competitions episodes <SUBMISSION_ID>
kaggle competitions replay <EPISODE_ID> -p ./replays
kaggle competitions logs <EPISODE_ID> 0 -p ./logs
kaggle competitions leaderboard pokemon-tcg-ai-battle -s
kaggle competitions team-submissions <TEAM_ID>
```

Use CLI for **files, replays, logs**. Do not use it as a rules engine.

---

## 5. kaggle-environments — local match host

Repo: https://github.com/Kaggle/kaggle-environments  
Install:

```bash
pip install kaggle-environments
# upstream README also shows: uv pip install kaggle-environments
```

Generic loop from README:

```python
from kaggle_environments import make
env = make("cabt", debug=True)
env.run(["random", "random"])
print(env.toJSON()["rewards"], env.toJSON()["statuses"])
```

Agent loading forms the README documents: function, `"random"`, source string, **file path**, constant, HTTP URL.

Error classes the library names:

1. **Timeout** — `agentTimeout` (init) or `actTimeout` (each act)
2. **Error** — exception in the agent
3. **Invalid** — action fails spec or engine rejects it

`debug=True` is mandatory until S1 is green.

`evaluate(environment, agents, configuration, steps, num_episodes)` is the official multi-episode helper. Prefer a project harness that also writes JSONL, but this is the blessed runner.

CLI of the library itself:

```bash
python -m kaggle_environments.main list
python -m kaggle_environments.main run --environment cabt --agents random random --debug True
python -m kaggle_environments.main evaluate --environment cabt --agents random random --episodes 10
```

---

## 6. `cabt` contract (copy this into adapter tests)

### 6.1 Specification (`cabt.json`)

```json
{
  "name": "cabt",
  "title": "Card Battle",
  "agents": [2],
  "configuration": {
    "episodeSteps": 10000000,
    "actTimeout": 0,
    "runTimeout": 2000
  },
  "reward": { "enum": [-1, 0, 1], "default": 0 },
  "observation": { "remainingOverageTime": 600 },
  "action": { "type": "array", "default": [] }
}
```

Read it as:

- Two players only.
- Reward is **only** −1 / 0 / +1. This is why μ ignores prize count.
- **600 s** overage = the 10-minute bank the Bible already required.
- `actTimeout: 0` in the JSON does **not** mean “think forever.” The live observation still carries `remainingOverageTime`. Budget against that field, not against `actTimeout` in the spec file.
- `runTimeout: 2000` = whole episode wall clock on the host (seconds).
- `episodeSteps` is effectively uncapped; games end on engine `result`, not on a 100-step horizon.

### 6.2 Interpreter behavior (`cabt.py`)

Phase A — no battle yet (`Battle.battle_ptr is None`):

- Each agent’s first **action** is treated as a deck.
- If `len(deck) != 60` → that player `INVALID`, error `"Player i's deck does not have 60 cards."`
- `battle_start(deck0, deck1)` can also mark `INVALID` via `start_data.errorPlayer`.

Phase B — battle running:

- Only `current["yourIndex"]` is `ACTIVE`; the other is `INACTIVE`.
- Interpreter calls `battle_select(active_player.action)`.
- Exception → that player `INVALID`, opponent reward `1`.
- When `current["result"] >= 0`: both `DONE`.  
  `result == 0` → player 0 wins; `1` → player 1 wins; else draw.

Observation fields copied onto the active player:

- `select`
- `logs`
- `current`
- `search_begin_input`

`search_begin_input` is stripped before visualize export. Do not build S0 around it. Search APIs exist on the C library (`SearchBegin` / `SearchStep` / `SearchEnd` / `SearchRelease` in `cg/sim.py`) and are a **later-stage** tool, not an S0 dependency.

### 6.3 Built-in agents (use as unit-test oracles)

```python
def random_agent(obs: dict) -> list[int]:
    if obs["select"] == None:
        return deck          # 60 IDs baked into cabt.py
    return random.sample(list(range(len(obs["select"]["option"]))),
                         obs["select"]["maxCount"])

def first_agent(obs: dict) -> list[int]:
    if obs["select"] == None:
        return deck
    return list(range(obs["select"]["maxCount"]))
```

Official tests lock this behavior:

- `select is None` → action equals the module-level `deck`
- otherwise action is `list[int]`, length `maxCount`, indexes in range
- invalid deck agent → statuses `["INVALID", "DONE"]`
- invalid selection → one side `INVALID`, the other wins

### 6.4 One-line agent contract for every `main.py`

```text
if observation["select"] is None:
    return sixty_card_ids
else:
    return list_of_option_indexes   # length == select["maxCount"]
```

The engine **only offers legal options**. The bot’s job is ranking, not rules adjudication. Returning an index that is out of range or the wrong count is how you get `INVALID`.

### 6.5 Native binaries in the public tree

Under `kaggle_environments/envs/cabt/cg/`:

| File | Role |
|---|---|
| `libcg.so` | Linux x86-64 |
| `cg.dll` | Windows x64 |
| `libcg.dylib` | macOS |
| `libcg-arm64.so` | Linux/ARM (Apple Silicon containers / aarch64) |
| `game.py` | `battle_start` / `battle_select` / `battle_finish` / `visualize_data` |
| `sim.py` | ctypes load + `Search*` + `AllCard` / `AllAttack` |
| `api.py` | (in contest bundles; observation dataclasses) |

`sim.py` load order: Windows `cg.dll` → Darwin `libcg.dylib` → ARM `libcg-arm64.so` → else `libcg.so`.

S0 implication: try `pip install kaggle-environments` **before** Docker. Older “Mac ARM cannot run cabt” notes are stale if these four binaries load.

### 6.6 Minimal local smoke test (S0 gate, refined)

```python
from kaggle_environments import make

env = make("cabt", debug=True)
env.run(["random", "first"])
js = env.toJSON()
assert js["name"] == "cabt"
assert js["statuses"] == ["DONE", "DONE"]
assert sorted(js["rewards"]) in ([-1, 1], [0, 0])
```

If this fails on a machine, the problem is OS / binary / package version — not policy.

---

## 7. Dockerfile — official worker family

Path: `kaggle-environments/docker/Dockerfile`

```dockerfile
ARG BASE_IMAGE=gcr.io/kaggle-images/python:v163
FROM node:22-slim AS node_builder
FROM ${BASE_IMAGE} AS base
# copy node, COPY kaggle_environments, uv pip install --system .
FROM base AS cpu
CMD ["kaggle-environments"]
FROM base AS gpu
CMD ["kaggle-environments"]
```

Implications:

- Runtime is the **Kaggle Python notebook image**, not a custom TCG OS.
- `kaggle-environments` is installed into that image.
- GPU stage does not add a different command. Do not assume a GPU at eval (Simulation FAQ: **2 vCPUs**, no GPU listed).
- Build this image locally only if native `libcg` load fails.

---

## 8. Attached agent: `buddy-other-pokemon-v1.tar.gz`

Not a tutorial. A June 2026 **rules agent** in submission layout.

### 8.1 Tree

```
main.py          # 484 lines, function agent(obs_dict) -> list[int]
deck.pkl         # pickle of 60 int card IDs
cg/
  __init__.py
  api.py
  game.py
  sim.py
  utils.py
  libcg.so
```

Timestamps inside: **2026-06-26**.

### 8.2 Deck (from `deck.pkl`)

IDs in order (counts implied by repeats):

```
673 673                 Makuhita
674 674                 Hariyama
675 675                 Lunatone
676 676 676             Solrock
677 677 677             Riolu
678 678 678 678         Mega Lucario ex
1102 x4                 Dusk Ball
1123 x2                 Switch
1141 x4                 Premium Power Pro
1142 x4                 Fighting Gong
1152 x4                 Poké Pad
1159 x1                 Hero Cape
1182 x2                 Boss's Orders
1192 x4                 Carmine
1227 x4                 Lillie (Determination)
1252 x2                 Gravity Mountain
6 x13                   Basic Fighting Energy
```

This is the official-style **Fighting / Mega Lucario ex** starter family. For a non-player, this is the locked deck until evidence says otherwise (Bible L3).

### 8.3 How `main.py` talks to the engine

```python
from cg.api import (
    AreaType, CardType, EnergyType, Observation, SelectContext,
    OptionType, Card, Pokemon, all_card_data, to_observation_class,
)

def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select == None:
        return my_deck
    # ... heuristic scoring, returns option indexes
```

It loads card metadata via `all_card_data()` and scores Pokémon with prize-count heuristics (ex / mega-ex prize values, energy, tools, stage). That is a **worked example of a phase-aware scorer**, not a neural net.

### 8.4 Allowed uses

- Opponent in local `env.run([our_agent, buddy_main])` after S1.
- Source of one real `obs` fixture (run it, dump `obs_dict`).
- Reference for `to_observation_class` field names.

### 8.5 Forbidden uses

- Do not ask an agent to “improve this whole archive” as S0.
- Do not treat June-26 Lucario as the 2026-08 meta champion.
- Do not rewrite `cg/` inside the buddy tree; use the package from `kaggle-environments` as the engine of record.

---

## 9. Card data without the Simulation zip

Preferred order:

1. `EN Card Data.csv` from the Strategy Data tab (user stated they have this).
2. `all_card_data()` from `cg.api` / cabt engine.
3. Official API docs: https://matsuoinstitute.github.io/cabt/

Never substitute a community Pokédex. Card ID `678` in cabt is not “Pokédex #678.”

Store official dumps under `data/official/` and **do not let a coding agent edit them**.

---

## 10. Implications for Bible stages (delta only)

### S0 — Environment ownership

Updated smoke path:

1. `pip install kaggle-environments`
2. `make("cabt"); env.run(["random", "first"])` must finish `DONE`/`DONE`
3. Optional: run buddy `main.py` as one side
4. Save one raw `obs` dict + the `select` payload from that turn

Docker and the contest zip are **fallback**, not the default.

### S1 — Legal baseline

Contract tests must include:

- `select is None` → `len(action) == 60`
- otherwise `len(action) == obs["select"]["maxCount"]`
- 0 `INVALID`, 0 `ERROR`, 0 `TIMEOUT` over the gate sample

Buddy Lucario is a legal second player for this gate.

### S2 — Deck lock

Default lock = buddy / official Lucario ID list, exported as `deck.csv` (one ID per line) **and** kept as a Python list for the `select is None` return.

Do not invent a 60-card theory while the operator is not a TCG player.

### S3+ 

Unchanged from the Bible. This addendum does not authorize PPO, global ISMCTS, or a second deck.

### Strategy writeup (if eligible)

Map Bible artifacts onto the 70/20/10 rubric:

- Model Score: architecture paragraph + paired local results + “we did not timeout” + Simulation μ if one exists
- Deck Score: Lucario plan in plain language + ID table from `EN Card Data.csv`
- Report Score: one diagram of `obs → legal options → scorer → indexes`, one failure-taxonomy table from replays

Word cap 2000. No card-art scrapes.

---

## 11. Coding-agent leash updates

Add these to any S0/S1 prompt:

```text
Engine of record: pip package kaggle-environments, env name "cabt".
Do not vendor a second libcg.so unless load fails.
Agent I/O:
  select is None -> return 60 card IDs
  else -> return option indexes, length select.maxCount
Do not call SearchBegin in S0 or S1.
Do not edit data/official/ or EN Card Data.csv.
Opponent allowed: "random", "first", or the buddy main.py.
Simulation uploads are closed. Do not add submit scripts as if the ladder is open.
```

---

## 12. Operator checklist against this addendum

- [ ] `kaggle-environments` imports
- [ ] `make("cabt")` random vs first finishes
- [ ] Strategy `EN Card Data.csv` is on disk under `data/official/`
- [ ] Buddy bundle unpacked **read-only** as `refs/buddy-lucario/`
- [ ] Account check: Simulation listed under Entered? (yes/no). This decides prize vs private project.
- [ ] If yes and Strategy rules accepted before 2026-09-06: writeup calendar is live through 2026-09-13
- [ ] Leaderboard zip filed under `refs/ladder/` and not used as card metadata

---

## 13. Still unknown / do not fake

- Whether *this* Kaggle account joined Simulation before 2026-08-09.
- Exact public-vs-private difference in `api.py` between the buddy tree and current `kaggle-environments` (buddy shipped its own `api.py`; upstream tree listing on 2026-09-01 showed `game.py` + `sim.py` under `cg/` — treat observation dataclasses as “import from the bundle you can actually import,” and pin that path in S0 notes).
- Whether `deck.csv` vs `deck.pkl` is enforced by current workers (page says csv; working June agent used pkl). New code should support returning a 60-int list regardless of file format.
- Simulator vs paper-PTCG rule deltas (the Simulation page points to a differences document). Read that before writing “illegal under real TCG” claims.

---

## 14. One-page architecture of the official stack

```
main.py  agent(obs) -> list[int]
    |  first call: 60 card IDs
    |  later: option indexes
    v
kaggle_environments.make("cabt")
    v
cabt.interpreter
    v
cg.game.battle_start / battle_select
    v
libcg.*   (C engine; legal options only)
    v
obs = { logs, current, select, search_begin_input, remainingOverageTime }
    v
reward in {-1, 0, 1}  ->  Kaggle μ update (Simulation, closed)
```

That picture is the only runtime that counts. Everything in the Bible sits inside `agent()`.

---

## 15. Change log

| Date | What landed |
|---|---|
| 2026-09-01 | Initial addendum from four GitHub links, Simulation + Strategy page text, buddy tar.gz, leaderboard zip, Strategy dataset claim. |

When a later primary source contradicts a row above, edit this file and leave a dated note. Do not silently “update the Bible’s laws” because a Dockerfile changed.
