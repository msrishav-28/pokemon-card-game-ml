# Failure Taxonomy

Label losses. Count them. Fix the top bucket, not the most interesting one.

Categories (from Bible §9):

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

## Evidence rules

- A terminal outcome comes only from a result-linked `game_end` record. Prize
  snapshots are never treated as results.
- A decision pathology is a signal, not automatically the cause of a loss.
- If a replay does not carry an explicit causal decision reference, the loss
  remains `gameplay loss; decision cause unclassifiable`.

## Frozen incumbent audit (2026-09-04)

`scripts/diagnose_replays.py` read 61,175 JSON objects from the three N=200
incumbent evaluations against random, first, and buddy. All 600 games had
explicit terminal records and all 60,572 decisions were linked by `game_id`.

| Evidence | Count | Interpretation |
|---|---:|---|
| wins / losses | 257 / 343 | terminal outcomes across the frozen trio |
| invalid / timeout / error | 0 / 0 / 0 | no safety failure to fix first |
| gameplay losses with an explicit causal decision | 0 | all 343 causes remain honestly unclassified |
| all-zero feature vectors | 10,698 | the six-family scorer contains many contexts it does not explain |
| flat score vectors | 7,063 | many prompts receive no meaningful ordering signal |
| visible base-damage last-prize opportunities | 9 | narrow Lucario attack facts only |
| visible base-damage last-prize misses | 3 | actionable B2 signal; not promoted to a causal loss label |

The previous `resource starvation` row was removed because its prize snapshot
did not prove either the terminal outcome or the decision that caused it.

## Promoted AttackPlan audit (2026-10-03)

The three final `submission/main.py` evaluations contributed 56,734 valid
JSON objects from 600 official cabt games. All 56,131 decisions and every
terminal record share an explicit `game_id`; malformed and ungrouped records
were zero.

| Evidence | Count | Interpretation |
|---|---:|---|
| wins / losses | 451 / 149 | terminal outcomes across the frozen trio |
| invalid / timeout / error / fallback | 0 / 0 / 0 / 0 | no safety or degraded-policy bucket |
| losses with an explicit causal decision | 0 | all 149 gameplay causes remain unclassified |
| all-zero feature vectors | 124 | uncommon neutral contexts, not a failure label |
| flat score vectors | 6,399 | includes forced/equivalent selections |
| visible base-damage last-prize opportunities | 33 | conservative Lucario-only signal |
| apparent last-prize misses | 6 | sequence-level audit needed; not a causal label |

The frozen evidence supports B4 as a diagnostic bet: follow flagged decisions
through the rest of the same turn before deciding whether an attack was
actually missed. No opening, resource, gust, supporter, or retreat cause is
assigned without an explicit causal reference.
