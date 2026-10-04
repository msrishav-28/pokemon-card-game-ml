# Inventory

**Date:** 2026-09-01

**Stage:** S0

## Workspace contents found at `c:\Users\Vignesh\Downloads\pokemon`

| File | What it is | Status |
|---|---|---|
| `PTCG_AI_BUILD_BIBLE.md` | Canon build doctrine, L1–L10, S0–S7 | Copied to `docs/canon/` read-only |
| `PTCG_AI_FIELD_ADDENDUM.md` | Canon field sheet, cabt I/O, worker limits | Copied to `docs/canon/` read-only |
| `buddy-other-pokemon-v1.tar.gz` | June 2026 Lucario rules agent + cg/ + deck.pkl | Unpacked read-only to `refs/buddy-lucario/` |
| `EN Card Data.csv` | Official EN card catalog (Strategy dataset) | Copied to `data/official/` |
| `EN_Card_Data.csv` | Variant copy of EN card data | Copied to `data/official/` |
| `JP Card Data.csv` | Official JP card catalog | Copied to `data/official/` |
| `JP_Card_Data.csv` | Variant copy of JP card data | Copied to `data/official/` |
| `Card_ID List_EN.pdf` | Official EN card ID PDF (~131 MiB) | Preserved locally in `data/official/`; not Git-tracked |
| `Card_ID List_EN_.pdf` | Byte-identical EN PDF duplicate | Preserved locally; not Git-tracked |
| `Card_ID List_JP.pdf` | Official JP card ID PDF (~174 MiB) | Preserved locally in `data/official/`; not Git-tracked |
| `Card_ID List_JP_.pdf` | Byte-identical JP PDF duplicate | Preserved locally; not Git-tracked |
| `pokemon_tcg_ai_master_plan.md` | Retired planning doc (do not read) | Left in place, not used |
| `pokemon_tcg_ai_rationale_report.md` | Retired report (do not read) | Left in place, not used |
| `pokemon_tcg_ai_senior_researcher_report.md` | Retired report (do not read) | Left in place, not used |

## Leaderboard zip

| File | Location | Status |
|---|---|---|
| `pokemon-tcg-ai-battle-privateleaderboard-2026-09-01T15_46_13.zip` | Found at `C:\Users\Vignesh\Downloads\` | Unpacked to `refs/ladder/` |

Inner file: `pokemon-tcg-ai-battle-privateleaderboard-2026-09-01T15_46_13.csv` (6,807 teams)

## Buddy bundle tree after unpack

```
refs/buddy-lucario/
  main.py           (17,855 bytes, 484 lines)
  deck.pkl           (183 bytes)
  cg/
    __init__.py
    api.py           (26,933 bytes — enums, dataclasses, observation types)
    game.py          (2,225 bytes — battle_start / battle_select)
    sim.py           (2,273 bytes — ctypes load + Search* + AllCard)
    utils.py         (1,970 bytes — to_dataclass helpers)
    libcg.so         (1,342,400 bytes — Linux x86-64 only)
```

## Strategy CSV status

**PRESENT.** `EN Card Data.csv` and variants found in workspace root and copied to `data/official/`.

The player reads `EN Card Data.csv`; the card-ID PDFs are not runtime inputs.
All four PDFs exceed GitHub's per-file limit, so the pushed repository records
their names, sizes, and hashes in `data/official/README.md` while the unchanged
local copies remain ignored.

## Missing items

- None. All expected attachments are present.
