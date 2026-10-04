# PTCG AI Build Bible

**Status:** canon. One file. Re-read at the start of every work session.  
**Date locked:** 2026-09-01  
**Purpose:** build a competition-grade Pokémon TCG agent without letting an AI coding agent invent architecture, skip gates, or confuse research vocabulary with a working player.

If a later note, chat, or generated plan disagrees with this file, this file wins.

---

## 0. How to use this file

1. Open this file before writing code.
2. Identify the current **stage** (S0–S7). Do only that stage.
3. Do not start the next stage until the **exit gate** is green.
4. After every coding session, append one line to `docs/notes/session_log.md`: date, stage, what changed, what was measured, what failed.
5. Never paste this whole file plus the three old briefs into an agent. This file replaces them.

### What this file is not

- Not a Kaggle Strategy writeup.
- Not permission to train PPO on day one.
- Not a promise that this Kaggle Simulation ladder is still accepting bots.

---

## 1. Contest reality (do not lie to yourself)

Official first-round structure is two linked categories on Kaggle, announced by The Pokémon Company with Matsuo Institute and HEROZ.

| Track | What you submit | Window | Money |
|---|---|---|---|
| Simulation | agent bundle (`main.py`, `deck.csv`, code) | 2026-06-16 → 2026-08-17 08:59 JST | none |
| Strategy | report about **that same** Simulation agent | 2026-06-16 → 2026-09-14 08:59 JST | $30k × top 8, then Japan finals |

Sources:

- Official site: https://ptcg-abc.pokemon.co.jp/
- Simulation: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle
- Strategy: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy
- TPC press release: https://prtimes.jp/main/html/rd/p/000000872.000026665.html

Hard constraints from official materials:

- Card pool is organizer-provided Standard subset (~2,000 cards). You may not invent cards.
- Match clock: **10 minutes per player**. Timeout is a loss.
- Simulation scoring: Kaggle rating (TrueSkill-style μ). Win/loss, not prize differential.
- Strategy scoring axes (official wording): agent **stability**, **deck concept**, **Simulation performance**.
- Strategy is not enterable without a Simulation submission.
- Finals (top 8): BO3, same deck + same agent, 30 minutes per game; later games may use earlier-game logs.

As of 2026-09-01: Simulation uploads are closed. Building from scratch is still the correct *engineering* path. It does not reopen the official ladder. If this team already uploaded a bot, the official Strategy packet may only claim what that bundle does.

Field size reported publicly: thousands of teams (one August post cited 5,723 teams / 12,394 people; a late-August analysis of the public board cited 6,806 teams). Treat those as order-of-magnitude, not as your KPI.

---

## 2. Standing laws

These are not suggestions.

**L1. Environment before model.**  
If the adapter, legal-action wrapper, or local match runner is untrusted, every later number is fiction.

**L2. Legal and on time, or it is not an agent.**  
Invalid action rate target: **0**. Timeout rate target: **0**. A higher win rate that times out is a worse agent.

**L3. One deck, one policy.**  
Do not start with a universal net over the full card pool. Deck choice *is* part of the state distribution and is a judged Strategy axis.

**L4. Heuristic competence before search, search before learning.**  
A phase-aware action scorer is the policy. Search is a gated refinement. A learned value model is an optional leaf/ranker upgrade that must beat the scorer in a paired test.

**L5. Hidden information is state, not noise.**  
Do not pretend the public board is the full game. Do not attempt exact inference over all hidden cards on day one.

**L6. Measurement is the only language of progress.**  
No claim without: opponent identity, deck freeze, N games, pairing rule, 95% CI, timeout rate, invalid-action rate, code version.

**L7. Replays are the debugger.**  
If you cannot open a losing turn and see legal actions + scores + chosen action, you are guessing.

**L8. Inference constraints beat training fantasy.**  
Whatever you train must run in the official worker. The public `pkm` stack had to export **NumPy-only** weights (no PyTorch at eval), bundle `main.py` + `deck.csv`, stay under **~198 MiB**, and talk to the official **cabt** C engine. Copy that discipline even if you never submit.

**L9. Do not confuse local win rate with ladder μ.**  
Local gates filter. Ladder sorts. After a freeze, ratings can still drift from matchmaking, not from new intelligence.

**L10. The coding agent does not choose architecture.**  
It implements the current stage. It may not add PPO, transformers, multi-deck policies, or global MCTS because those words appear in papers.

---

## 3. What the problem actually is

Formal type: **two-player, zero-sum, stochastic POMDP** with a combinatorial action set and a hard real-time budget.

You observe: public board, your hand, your prizes as the engine exposes them, legal action list.  
You do not observe: opponent hand, opponent deck order, unrevealed prizes, future draws.

That combination kills two naive frames:

1. Supervised next-action cloning — identical public boards can demand different actions because hidden state differs (state aliasing).
2. Generic PPO from random play — sample-hungry, brittle under sparse delayed reward, opaque when it fails, and not automatically “belief-aware” just because it is neural.

This is closer to **online planning under uncertainty** than to Kaggle tabular ML.

---

## 4. Evidence this doctrine is not taste

Use these as load-bearing citations. Do not cite them as “Pokémon TCG is solved.”

### 4.1 Imperfect-info search structure

Cowling, Powley, Whitehouse, **Information Set Monte Carlo Tree Search**, IEEE TCIAIG 2012.  
https://doi.org/10.1109/TCIAIG.2012.2200894  

ISMCTS searches information sets / sampled consistent worlds, not a fake perfect-information tree. Plain MCTS on a single determinization is the thing you outgrow, not the thing you ship first.

### 4.2 Heuristic vs PPO vs ISMCTS in a hidden-info card game

Malla, **AI Agents for the Dhumbal Card Game: A Comparative Study**, arXiv:2510.11736.  
https://arxiv.org/abs/2510.11736  

Across 1024 rounds, a rule-based Aggressive agent reported **88.3%** win rate (95% CI 86.3–90.3) vs ISMCTS **9.0%** and PPO **1.5%** in the cross-category setting they published. Within search methods, ISMCTS beat plain MCTS.  

Read this as a **warning about naïve RL-first and naïve search-first**, not as a theorem that heuristics always win Pokémon. Different game, different action semantics. The transferable lesson: domain structure + evaluation discipline beat fashionable defaults.

### 4.3 Observation-space planning vs reconstructing the whole hidden state

Rebstock et al., **GO-MCTS**, arXiv:2404.13150.  
https://arxiv.org/abs/2404.13150  

Searching in observation space with a generative model can beat naïve hidden-state reconstruction in trick-taking games. Implication for us: you do not need a perfect posterior over the opponent’s 60-card deck to make better decisions. You need a decision-relevant uncertainty model.

### 4.4 Factored / limited-horizon search in CCG-like games

Planning work on Duelyst-style CCGs: one-ply / end-of-turn rollouts plus **action factoring** (type → source → grounded action), because full-game rollouts under hidden decks are lies and grounded action lists explode.  
NSF copy: https://par.nsf.gov/servlets/purl/10465745  

Implication for us: search **this turn’s high-impact fork**, not the rest of the match, until the leaf evaluator is trustworthy.

### 4.5 Learned models do not automatically handle hidden info

MuZero (Schrittwieser et al. 2020) is planning with a learned model in **perfect-information / single-agent** settings. The authors explicitly note imperfect-info games such as poker are not directly addressed.  
https://arxiv.org/abs/1911.08265  

Belief-aware / IIG look-ahead (e.g. LAMIR, arXiv:2510.05048) is a research direction, not a week-2 deliverable.  
https://arxiv.org/abs/2510.05048

### 4.6 In-contest field signal (this exact environment)

Public participant workspace `TomBombadyl/kaggle_pokemon` (early snapshot, not gospel): after 21 complete submissions, official **Dragapult pilot ~880.9 μ**; best home-grown cited as **SearchScorer × Lucario ~660.5 μ**; a field **RL+MCTS v5 regressed to ~580.6 μ on the same deck**.  
https://github.com/TomBombadyl/kaggle_pokemon  

Kaggle itself pointed builders at a **rule-based Mega Lucario ex** starter, not at PPO.  
X, @kaggle, 2026-07-08: starter notebook for a rule-based Lucario agent.  
https://x.com/kaggle/status/2074876018083406068

Participants who finished Simulation publicly described staying on **heuristic + Mega Lucario ex** rather than switching stacks late.  
X, @VaibhavGandotr1, 2026-08-16.  
https://x.com/VaibhavGandotr1/status/2089073695386169474

Independent post-freeze board analysis (Habr, 2026-08-26): ~6,806 teams; last legal submit 16 Aug 23:58; post-freeze μ movement is matchmaking, not new code.  
https://habr.com/ru/articles/1074532/

Public engine/submission mechanics from `jibai-devs/pkm`: cabt C ABI, Kaggle-shipped `libcg.so`, submission `main.py` + `deck.csv`, ~197.7 MiB cap, 5 submits/day while live, NumPy inference if you train torch.  
https://github.com/jibai-devs/pkm

Local env writeups confirm official notebook **[Basics] Build a local battle environment** (guregu321) plus Docker/`kaggle-environments` as the real on-ramp.  
https://zenn.dev/redzonegen/articles/redzonegen-kaggle-ptcg-local-env  
https://note.com/rii_pokeka/n/n7586e5cf20a3

X is **anecdote**. Papers and official pages are **constraints**. In-contest repos are **existence proofs**. None of them license skipping L1–L10.

---

## 5. Target architecture (frozen)

Seven layers. Each is independently testable. Policy code never imports raw simulator JSON.

```
1. env adapter        official obs  ->  CanonicalState
2. schema             pydantic/dataclasses with validation
3. cards/decks        roles, tags, one locked 60-card list
4. actions            legal list -> typed Action
5. policy             phase detector + feature scorer + weights
6. beliefs + search   optional, gated, budgeted
7. eval + replay      the only way a change ships
```

Decision loop (this is the agent):

```text
obs = adapter.parse(raw)
legal = [type_action(a) for a in obs.legal_actions]
phase = detect_phase(obs)
ranked = score(obs, legal, phase, beliefs)
if should_search(obs, ranked, phase) and budget_remaining():
    choice = search(obs, ranked[:K], beliefs, node_budget, time_budget)
else:
    choice = ranked[0]
log_turn(...)
return choice.to_engine()
```

If time or node budget expires: return `ranked[0]`. Never throw. Never return an action not in `legal`.

---

## 6. Repository law

```text
pokemon-tcg-ai-agent/
  README.md
  pyproject.toml
  configs/decks/  configs/experiments/  configs/weights/
  data/official/          # immutable official dumps
  data/processed/  data/cache/
  docs/notes/session_log.md
  docs/notes/experiment_log.md
  docs/notes/failure_taxonomy.md
  src/env/adapter.py
  src/schema/models.py
  src/cards/
  src/decks/
  src/features/action_features.py
  src/policies/baseline.py
  src/policies/heuristic.py
  src/beliefs/opponent_model.py
  src/search/selective_search.py
  src/evaluation/batch.py
  src/replay/logger.py
  tests/unit/  tests/integration/  tests/regression/  tests/fixtures/
  scripts/run_local_match.py  scripts/batch_evaluate.py
  submission/main.py  submission/deck.csv
  output/
```

Rules:

- Official files live only under `data/official/` and are never edited.
- Weights live in YAML under `configs/weights/`. No magic numbers buried in `heuristic.py` after v1.
- Every experiment writes JSON under `output/experiments/<id>/`.
- Every discovered bug becomes a fixture in `tests/regression/`.

---

## 7. Stages and exit gates

A coding agent may only work in the current stage. Paste **one stage** into the agent, not this whole file plus extra wishes.

### S0 — Environment confirmation

Work:

- Install official local path (Kaggle CLI + competition files + `kaggle-environments` / official notebook).
- Run a starter or random agent for one full match.
- Confirm card CSV and rule materials are archived.

Exit gate:

- [ ] One match completes locally.
- [ ] Official assets exist under `data/official/` with a checksum or date stamp.
- [ ] You can print the legal action list from a real observation.

Forbidden: policy code, neural nets, deck originality essays.

### S1 — Safe baseline

Work:

- `CanonicalState` schema.
- Adapter with unit tests on fixture payloads.
- `policies/baseline.py`: always legal; prefer a cheap default (attack if legal else first legal, or official starter clone).
- JSONL replay of every turn.

Exit gate:

- [ ] 100 games vs starter/random finish.
- [ ] Invalid actions = 0.
- [ ] Crashes = 0.
- [ ] Replay file exists and one turn can be reconstructed from it.

Forbidden: search, PPO, feature weights.

### S2 — Deck lock

Work:

- Tag cards with roles (attacker, draw, search, energy, recovery, gust, pivot, dead-last).
- Score **three** candidate lists only, then lock one.

Score each candidate 1–5 on: opening consistency, branching chaos, prize-path clarity, recoverability, AI-explainability.

Compute, do not vibe:

- P(at least one playable Basic in opening)
- P(primary attacker can attack by turn T)
- Search/draw/energy counts
- Distinct high-branch trainers

Exit gate:

- [ ] One `configs/decks/primary.yaml` + `submission/deck.csv`.
- [ ] Written rationale in `docs/notes/deck_lock.md` (why this list, what was rejected).
- [ ] Baseline rerun on the locked deck (100 games, still 0 invalid).

Forbidden: “we will support all archetypes.” Official starter Lucario / official pilot Dragapult are **allowed starting lists**, not finished concepts. If you use them, measure deviations.

### S3 — Heuristic tactical agent

This is the first real player.

Feature families (implement all six; weights vary by phase):

1. Prize race — expected prizes this turn / denied next turn / KO probability.
2. Tempo — energy attach, attack availability next turn, setup speed.
3. Board — Active survivability, bench quality, liability exposure.
4. Resources — draw/search value, supporter scarcity, dead-card reduction.
5. Risk — topdeck dependence, gust exposure, hidden-card sensitivity.
6. Endgame — forced lethal, prize-map collapse, preserve outs.

Phases: opening, development, pressure, prize conversion, stabilization, closure.

Exit gate:

- [ ] Every legal action gets a typed object + feature vector + scalar score.
- [ ] Phase detector has unit tests.
- [ ] 500–1,000 paired games vs S1 baseline, same deck, recorded CI.
- [ ] Invalid = 0, timeout = 0 locally.
- [ ] 20 inspected replays with at least 5 labeled mistakes.

Forbidden: training loops. One weight cluster change per experiment.

### S4 — Belief layer

Track only variables that can flip action order:

1. Revealed-card memory.
2. Coarse opponent archetype posterior from public cards.
3. Remaining plausible copies of scare cards (gust / boss / recovery / extra attacker).
4. “Can they KO me this turn given energy in play + one unseen attach?”
5. Own prize constraints if the engine exposes enough to reason.

Start with **one consistent guessed world**. Sample extra worlds later, and only at search nodes.

Exit gate:

- [ ] Belief object updates on every reveal and is logged.
- [ ] At least one documented turn where belief changed the top action vs S3.
- [ ] Ablation: S3 vs S4, 500+ paired games, CI reported.
- [ ] Latency p95 still safe vs 10-minute match budget.

Forbidden: full Bayesian hand enumeration.

### S5 — Selective search

Triggers (only these until data says otherwise):

- Multiple knockout / prize-map attacks.
- Retreat vs stay.
- Multi-target search cards.
- Supporter vs attack when both are live.
- Endgame sequencing.

Design:

- Expand top-K from the heuristic ranker only.
- Hard node budget + hard millisecond budget.
- Leaf value = S3/S4 scorer (or later the learned value if it passed S6).
- Hidden handling: start with the single guessed world; ISMCTS-style sampled worlds only if S4 ablation was positive and latency allows.

Exit gate:

- [ ] `should_search` fires on a minority of decisions (log the rate; target well under 20% until proven).
- [ ] Abort-to-heuristic is tested.
- [ ] Paired 500–1,000 games vs S4.
- [ ] p95 decision time and match-level time-used are reported.
- [ ] Search off vs search on is an official ablation row.

Forbidden: MCTS on every item play. Forbidden: unbounded trees.

### S6 — Learned value (optional)

Allowed only after S5 is stable.

Job: estimate P(win) or expected prize differential from a snapshot. Use it to re-rank close actions or score leaves.

Training data must come from S3–S5 agents, not from random legal play alone.

Keep the model only if:

- paired win rate vs frozen S5 improves with non-overlapping CI, **or**
- search-with-value beats search-with-heuristic on the same node budget,

and inference stays inside worker constraints (prefer NumPy export).

Exit gate:

- [ ] Held-out games + calibration plot.
- [ ] Fallback to S5 if the weight file is missing.
- [ ] Size budget respected.

Forbidden: “PPO learned the game from scratch.” Forbidden: shipping torch in the worker if the worker will not import it.

### S7 — Freeze and explain

Work:

- Pin git hash, deck hash, weight file, experiment IDs.
- Large evaluation suite.
- Failure histogram.
- Write the short report from measurements, not from this bible’s rhetoric.

Exit gate:

- [ ] Reproducible command reproduces the table.
- [ ] Every sentence in the public writeup maps to a logged experiment or a code path that exists.

---

## 8. Evaluation protocol (non-negotiable)

Minimum comparison:

- Same decks unless the experiment *is* a deck test.
- Paired seeds / paired seats (p0 and p1 swapped).
- N = 200 for coarse cuts; N = 500–1,000 before you believe a small gain.
- Report Wilson or Clopper-Pearson 95% CI on win rate.
- Always also report: invalid actions, timeouts, errors, mean and p95 latency, mean turns.

Do not ship a change if CIs overlap and replays do not show a consistent tactical fix.

Experiment JSON required fields:

```json
{
  "experiment_id": "exp_YYYYMMDD_NNN",
  "git": "hash",
  "agent_a": "heuristic_v2",
  "agent_b": "baseline_v1",
  "deck_a": "primary_v1",
  "deck_b": "primary_v1",
  "games": 1000,
  "seed_policy": "paired",
  "win_rate_a": 0.0,
  "ci95_low": 0.0,
  "ci95_high": 0.0,
  "timeouts_a": 0,
  "invalid_actions_a": 0,
  "mean_latency_ms": 0.0,
  "p95_latency_ms": 0.0
}
```

A 3-point win-rate bump with N=40 is not a result.

---

## 9. Failure taxonomy

Label losses. Count them. Fix the top bucket, not the most interesting one.

- opening inconsistency
- resource starvation
- overextension
- missed lethal
- wrong gust / wrong target
- premature supporter
- retreat error
- recovery mistiming
- search-target miss
- belief misread
- timeout / latency
- weight pathology (scorer systematically wrong)

Each major bucket must eventually have a regression fixture.

---

## 10. Coding-agent contract

When you invoke an AI coding agent, the prompt must include:

1. Current stage (exactly one).
2. Exit gate checklist.
3. “Do not add modules from later stages.”
4. “Do not install a new training framework unless this stage is S6.”
5. “Do not edit `data/official/`.”
6. “Every new behavior needs a test or a replay fixture.”
7. “If the simulator API is unclear, stop and write the unknown down; do not guess card effects.”

Banned phrases in agent output unless backed by a passing experiment:

- end-to-end RL
- just use PPO
- universal policy
- full MCTS every turn
- the model will learn hidden information
- 3% better

If the agent starts scaffolding `train_ppo.py` during S0–S5, revert the commit.

---

## 11. Weight tuning

1. Hand-initialize phase weights from the locked deck’s plan.
2. Inspect 20–50 replays.
3. Change **one cluster** (e.g. only prize-race terms).
4. Run 200 paired games. If promising, 1,000.
5. Keep a changelog: old value, new value, experiment id, keep/revert.

No Bayesian optimization theater until S3 is already respectable and you have a scorer that is not obviously mis-ordering lethals.

---

## 12. First 10 tasks (do in order)

1. Create the repo skeleton above.
2. Mirror official competition assets into `data/official/`.
3. Run official / starter match path once.
4. Implement adapter + `CanonicalState`.
5. Unit-test the parser on fixtures.
6. Implement legal-only baseline.
7. JSONL replay logger.
8. Card-role table for the locked-deck candidates.
9. Deck-lock note + `deck.csv`.
10. 100-game baseline batch archived under `output/experiments/`.

If task 10 is not done, you are not “building an AI.” You are still wiring the socket.

---

## 13. Anti-patterns (instant revert)

- Mixing raw engine tokens into policy scoring.
- Training before 0-invalid baseline exists.
- Measuring only win rate.
- Changing deck and policy in the same experiment.
- Copying a human netdeck and calling it a concept without consistency stats.
- Search without top-K restriction.
- Writing the Strategy essay before experiment_log has rows.
- Claiming ladder rank you did not earn.
- Publishing official card text dumps or engine binaries against competition / license rules.

---

## 14. Source list (keep these, ignore the rest)

### Official

- https://ptcg-abc.pokemon.co.jp/
- https://www.kaggle.com/competitions/pokemon-tcg-ai-battle
- https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy
- https://prtimes.jp/main/html/rd/p/000000872.000026665.html
- Official starter orientation via Kaggle: rule-based Mega Lucario ex notebook (The Pokémon Company / Kaggle social post 2026-07-08)

### Environment / field implementations

- https://github.com/jibai-devs/pkm — cabt ABI, submission shape, NumPy export
- https://github.com/TomBombadyl/kaggle_pokemon — in-contest notes on μ vs local gates (snapshot; verify before copying claims)
- https://zenn.dev/redzonegen/articles/redzonegen-kaggle-ptcg-local-env
- https://note.com/rii_pokeka/n/n7586e5cf20a3
- Episode dumps published by Kaggle under “PTCG AI Battle Challenge Simulation Episodes”

### Papers (read before implementing the matching stage)

- ISMCTS: Cowling et al. 2012, IEEE TCIAIG  
  https://doi.org/10.1109/TCIAIG.2012.2200894
- Dhumbal comparison (heuristic vs ISMCTS vs PPO): arXiv:2510.11736  
  https://arxiv.org/abs/2510.11736
- GO-MCTS observation-space planning: arXiv:2404.13150  
  https://arxiv.org/abs/2404.13150
- Duelyst-style factored / one-ply CCG search: https://par.nsf.gov/servlets/purl/10465745
- MuZero (know its limits): arXiv:1911.08265  
  https://arxiv.org/abs/1911.08265
- IIG look-ahead with learned models (S6+ research only): arXiv:2510.05048  
  https://arxiv.org/abs/2510.05048

### X (signal, not authority)

- https://x.com/kaggle/status/2074876018083406068 — official-adjacent starter push: rule-based Lucario
- https://x.com/VaibhavGandotr1/status/2089073695386169474 — participant froze heuristic + Mega Lucario ex for final Simulation submit
- https://x.com/Light_88_/status/2086405046439211256 — public scale snapshot of the field
- https://x.com/kaggle — check for later official notebooks; do not treat quote-tweets as rules

---

## 15. One-screen recap

You are building a **legal, timed, deck-specific decision system**.

Order: adapter → legal baseline → lock deck → score actions by phase → light beliefs → search only on costly forks → learn only if it beats the scorer.

Every upgrade needs paired games, a CI, a replay, and a revert path.

If the coding agent wants to skip to training, it is wrong.

That is the whole project.
