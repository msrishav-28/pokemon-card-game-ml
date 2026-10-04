# Unknowns and Observation Key Inventory

Every observation key verified from `fixtures/obs_sample.json` and cabt live execution.

Rules:
- guessed=yes is a defect. Prefer leaving a field unmapped.
- All unmapped keys are recorded below.

---

## Unmapped or Partially Mapped Keys

key: obs.search_begin_input
seen_in: live
mapped: no
guessed: no
notes: C engine search input struct; stripped before visualize export. Not used in S0–S3.

key: obs.select.deck
seen_in: live
mapped: no
guessed: no
notes: Cards exposed from deck during deck-search contexts. Not needed for S0 legal selection.

key: obs.select.remainDamageCounter
seen_in: live
mapped: no
guessed: no
notes: Remaining damage counters to assign during damage placement contexts.

key: obs.select.remainEnergyCost
seen_in: live
mapped: no
guessed: no
notes: Remaining energy cost to fulfill during energy-paying contexts.

key: obs.current.players[i].active[0].serial
seen_in: live
mapped: no
guessed: no
notes: Unique per-instance integer serial assigned by the C engine to distinguish physical card instances.

key: obs.current.players[i].active[0].playerIndex
seen_in: live
mapped: no
guessed: no
notes: Owner index of the in-play Pokemon. Implied by players[yourIndex] vs players[oppIndex].

key: obs.current.players[i].active[0].appearThisTurn
seen_in: live
mapped: no
guessed: no
notes: Boolean indicating if Pokemon was played this turn (relevant for evolution rules).

key: obs.current.players[i].active[0].energyCards
seen_in: live
mapped: no
guessed: no
notes: List of attached energy card objects (serial, cardId), distinct from energies summary.

key: obs.current.players[i].active[0].preEvolution
seen_in: live
mapped: no
guessed: no
notes: List of pre-evolution card IDs underneath an evolved Pokemon.

key: obs.current.players[i].benchMax
seen_in: live
mapped: no
guessed: no
notes: Maximum bench capacity (typically 5, modified by certain card effects).

---

## Complete Observation Key Inventory

| Key | Seen in | Mapped | Guessed | Notes |
|---|---|---|---|---|
| `remainingOverageTime` | live | yes | no | Time bank remaining in seconds (starts at 600.0) |
| `logs` | live | yes | no | Event logs tail from the engine |
| `select` | live | yes | no | Selection prompt object (None in deck phase) |
| `select.type` | live | yes | no | SelectType integer enum |
| `select.context` | live | yes | no | SelectContext integer enum |
| `select.minCount` | live | yes | no | Minimum options to select |
| `select.maxCount` | live | yes | no | Maximum options to select (length of returned list) |
| `select.remainDamageCounter` | live | no | no | Context-specific damage counter tracker |
| `select.remainEnergyCost` | live | no | no | Context-specific energy cost tracker |
| `select.option` | live | yes | no | List of legal option dicts |
| `select.deck` | live | no | no | Deck cards exposed during search |
| `select.contextCard` | live | yes | no | Card triggering the selection |
| `select.effect` | live | yes | no | Effect object associated with selection |
| `search_begin_input` | live | no | no | C engine search struct (stripped before visualize) |
| `current` | live | yes | no | Current battle state object |
| `current.turn` | live | yes | no | Current turn number (1-indexed) |
| `current.turnActionCount` | live | yes | no | Number of actions taken this turn |
| `current.yourIndex` | live | yes | no | Active player index (0 or 1) |
| `current.firstPlayer` | live | yes | no | Index of player who went first |
| `current.supporterPlayed` | live | yes | no | Supporter card played this turn |
| `current.stadiumPlayed` | live | yes | no | Stadium card played this turn |
| `current.energyAttached` | live | yes | no | Energy attached for turn |
| `current.retreated` | live | yes | no | Active retreated this turn |
| `current.result` | live | yes | no | Game result (-1 ongoing, 0 p0 wins, 1 p1 wins) |
| `current.stadium` | live | yes | no | In-play stadium card list |
| `current.looking` | live | yes | no | Cards currently being looked at |
| `current.players` | live | yes | no | 2-element array of PlayerState dicts |
| `players[i].active` | live | yes | no | In-play active Pokemon list (0 or 1 item) |
| `players[i].bench` | live | yes | no | In-play bench Pokemon list |
| `players[i].benchMax` | live | no | no | Max bench capacity (default 5) |
| `players[i].deckCount` | live | yes | no | Cards remaining in deck |
| `players[i].discard` | live | yes | no | Cards in discard pile |
| `players[i].prize` | live | yes | no | Prizes list (face-down as None, face-up as card) |
| `players[i].handCount` | live | yes | no | Total cards in hand |
| `players[i].hand` | live | yes | no | Full card list for self, None for opponent |
| `players[i].poisoned` | live | yes | no | Poison special condition |
| `players[i].burned` | live | yes | no | Burn special condition |
| `players[i].asleep` | live | yes | no | Asleep special condition |
| `players[i].paralyzed` | live | yes | no | Paralyzed special condition |
| `players[i].confused` | live | yes | no | Confused special condition |

---

## Freeze-time unknowns

- Native cabt chance is not seed-controllable through the installed Python
  API. Evaluations alternate seats and reset Python RNG, but are not paired on
  identical engine chance.
- The 149 final gameplay losses have result-linked decisions but no explicit
  causal-decision field. Assigning deck, sequencing, or target causes would be
  speculation until B4 adds turn-sequence evidence.
- The portable bundle passed the official engine on Windows. Its source-only
  runtime layout is platform neutral and contains no native library, but this
  machine did not execute the Kaggle Linux worker image.
- Final experiment summaries recorded a dirty worktree and did not hash the
  imported module graph. Bundle-manifest hashes are the release identity; the
  summary/replay hashes prove result integrity, not byte-identical source
  provenance.
