# Retained live replay fixtures

These JSONL files are byte-for-byte subsets of result-linked evaluation
replays produced by official `kaggle-environments==1.32.7` cabt matches. They
contain every decision for the named game plus its single `game_end` record.
They are not mocked observations and were not reconstructed from summaries.

- `final-submission-vs-random-win.jsonl`: actual promoted-entry win from the
  final 200-game evaluation versus `random`; the retained game has the
  clean-win median of 47 engine steps.
- `final-submission-vs-first-win.jsonl`: actual promoted-entry win from the
  final 200-game evaluation versus `first`; the retained game has the
  clean-win median of 75 engine steps.
- `final-submission-vs-buddy-win.jsonl`: promoted-submission win from the
  result-grade 200-game buddy evaluation (game 117, 148 engine steps).
- `final-submission-vs-buddy-loss.jsonl`: promoted-submission loss from the
  same evaluation (game 126, 147 engine steps).
- `planned-vs-random-win.jsonl`: representative B3 win versus `random`.
- `planned-vs-first-win.jsonl`: representative B3 win versus `first`.
- `planned-vs-buddy-win.jsonl`: representative B3 win versus frozen buddy.
- `planned-vs-buddy-loss.jsonl`: representative clean loss for diagnosis; no
  causal mistake is asserted without evidence.

The two final-submission fixtures straddle that evaluation's median game
length of 147.5 engine steps. Both games ended `DONE`/`DONE` with no runner
error, action-contract failure, policy exception, or policy fallback.

Each adjacent `.meta.json` records the source replay name and SHA-256, game
ID, record counts, output SHA-256, and exact byte size. Recreate an extraction
with `scripts/extract_replay_fixture.py`; audit the retained set with:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_replays.py fixtures\replays
```
