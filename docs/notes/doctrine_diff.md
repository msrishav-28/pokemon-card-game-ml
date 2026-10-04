# Doctrine difference: linear feature scorer → tactical AttackPlan

**Decision date:** 2026-10-03

**Evaluation data:** official cabt runs captured 2026-09-04 and 2026-10-03

## What was discarded

The shipped policy no longer requires every action to be ordered by the S3
six-family, phase-weighted linear scorer before a stronger tactical policy may
exist. The unproven S4 belief adjustment was also removed from the submission
path. Both implementations remain in the repo as measured baselines; neither
is used by the frozen player.

This does **not** discard the engine, legal-index action contract, locked deck,
live-fixture rule, result-linked evaluation, safety gates, or the requirement
that search/learning earn their place in an ablation.

## What replaced it

`planned_candidate.py` is a deck-specific, interpretable AttackPlan policy. It
uses the one `CanonicalState` adapter, visible board state, legal options, and
unchanged official EN card metadata. Before ranking actions it selects a
visible attacker/target/attack line, then makes attachments, evolutions,
switches, gust choices, and the final attack follow that plan. A narrow
last-prize knockout invariant is part of the planner.

It never simulates a second rules engine, invents hidden observations, trains a
model, or calls search. `submission/main.py` validates the exact distinct
index contract and retains the first-index safety fallback.

## Measurement that justified the change

All rows use the locked 60-card Lucario list and `kaggle-environments==1.32.7`.
Native cabt chance is not seed-controllable, so external rows are independent
seat-balanced samples, not falsely labeled deterministic pairs.

| Opponent | Incumbent N=200 | AttackPlan N=200 | Change | AttackPlan safety |
|---|---:|---:|---:|---:|
| random | 66.5% | 97.0% | +30.5 pp | 0 invalid / 0 timeout / 0 error |
| first | 34.5% | 81.0% | +46.5 pp | 0 / 0 / 0 |
| buddy-lucario | 27.5% | 41.5% | +14.0 pp | 0 / 0 / 0 |

The direct policy match was 156–44 for AttackPlan: **78.0%**, Wilson 95% CI
**[71.8%, 83.2%]**, zero invalid/timeout/error. Its p95 decision latency was
1.071 ms and minimum remaining overage was 599.450 s. This clears the written
B3 gate; the result is too large to defend keeping the weaker architecture as
the submission policy.

The independently loaded, promoted `submission/main.py` was then frozen in a
second N=200 trio: 94.0% versus `random`, 82.5% versus `first`, and 49.0%
versus buddy. All 600 games completed with zero invalid, timeout, error,
contract-failure, or fallback events. The buddy Wilson interval is
[42.2%, 55.9%], so the release is not claimed to be statistically above buddy;
the measured claim is recovery from 27.5% to a near-parity point estimate.

The experiment summaries record Git commit `5f463b8` with `git_dirty=true` and
do not embed imported-module hashes. The freeze therefore records this as a
provenance limitation and identifies the released runtime with the bundle
manifest and per-file SHA-256 hashes instead of claiming that the summaries
cryptographically prove byte identity.

## How a regression will be detected

- Every candidate must run N=200 against the same named trio and report Wilson
  intervals, seats, invalid, timeout, error, fallback, and remaining overage.
- Any invalid action, timeout, or policy fallback is an automatic regression,
  regardless of win rate.
- A replacement must beat this frozen policy directly with a Wilson lower
  bound above 50%, then avoid a material regression on the frozen trio.
- Result-linked JSONL is audited for option/score alignment and exact action
  cardinality; retained live fixtures make schema drift testable.
- Missing official metadata must degrade strategy only. It may never change
  the legal-action guarantee.
