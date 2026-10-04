# Policy audit: official area semantics

Date: 2026-09-04

## Evidence

- `refs/buddy-lucario/cg/api.py` defines `AreaType.ACTIVE = 4` and
  `AreaType.BENCH = 5` (`DISCARD = 3`).
- The live `fixtures/obs_sample.json` independently confirms the mapping: our
  player has one Active and an empty Bench, while every legal attach option
  targets `inPlayArea = 4`.
- `src/ptcg_agent/features/action_features.py` currently defines Active as 3
  and Bench as 4. On that live fixture, the incumbent heuristic consequently
  gives every attach option zero tempo and every legal option a total score of
  zero. The chosen index is therefore only an input-order tie-break.
- Existing heuristic unit tests encode the same wrong mapping (for example,
  they label `inPlayArea = 4` as Bench), so their green result does not cover
  the live contract.

This affects target lookup for energy/tool attachment and evolution, plus
Active/Bench card selections after Switch, gust, KO replacement, and attach
effects. It does not by itself create an illegal index, but it erases the
target-specific strategy those features claim to implement.

## Proposed bet (recorded before implementation)

Add an opt-in policy candidate that maps official Active/Bench values (4/5)
to the incumbent scorer's internal legacy values before scoring. Keep the
shared adapter, incumbent heuristic, and `submission/main.py` unchanged. This
isolates one schema correction and makes reversal trivial.

Promote only after:

1. regression tests prove the live fixture's Active target receives a
   non-zero target-aware score and an official-area Riolu/Lunatone choice is
   ranked correctly;
2. a live 20-game smoke has zero invalid actions and zero timeouts; and
3. paired `N >= 200` evaluation against the same frozen opponents shows no
   statistically credible win-rate regression.

Falsify/reject the candidate immediately for any invalid action or timeout.
Reject it as a strategy change if a paired 95% interval shows a negative win
rate delta against any frozen opponent. Until the paired gate is run, this is
a correctness candidate, not a measured improvement.

### Candidate smoke after implementation

A seat-balanced 20-game live run against `random` completed 18 wins and 2
losses with 0 invalid actions, 0 timeouts, and 0 errors. This was not a seeded,
paired comparison with the incumbent, so it satisfies only the smoke gate and
is not evidence of a win-rate improvement.

## Other audited defects (not changed in this bet)

- `_score_card_option` resolves every non-field `CARD` from our hand. Buddy's
  implementation resolves by `AreaType` (Deck, Hand, Discard, Prize, Stadium,
  or Looking), and the API says `select.deck` is populated for deck choices.
  The existing TO_HAND tests place pretend deck cards in `state.me.hand`, so
  they do not exercise the documented engine shape.
- Live adapter values for `PokemonView.is_ex`, `is_mega_ex`, and
  `retreat_cost` are always placeholders. Tests manually set EX flags that a
  live adapted state cannot currently produce. Thus the incumbent's generic
  Boss's Orders EX bonus and retreat-cost check do not operate as tested
  (Lucario ID 678 is the one hard-coded exception).
- Buddy computes an attack plan from damage, HP, weakness/resistance, prize
  value, attach availability, and possible switching. The incumbent attack
  feature does not compute damage or a KO and biases away from attack ID 983
  irrespective of target HP. Official `AllAttack` data reports Aura Jab (982)
  as 130 damage and Mega Brave (983) as 270 damage. Using the repository's
  existing test-state helper with two energy, an opponent at 200 HP, and one
  prize remaining, the incumbent chooses Aura Jab with scores 644 versus 626.
  It therefore selects a guaranteed non-KO over a game-winning KO in that
  represented state. No attack-planning change is proposed in this bet.
- Several feature descriptions disagree with official `AllCard` data:
  Premium Power Pro adds 30 attack damage (it does not draw to six), Fighting
  Gong searches the deck for a Basic Fighting Energy or Basic Fighting
  Pokemon (it is not an extra attachment), and Carmine discards the whole hand
  then draws five (not two cards to draw six). These wrong semantics directly
  feed the current resource/tempo scores. They need a separate, replay-gated
  candidate rather than being mixed into the area-code correction.

## Unknowns needed for the next bet

- Frequency and outcome cost of the area bug in locked-deck games; the current
  fresh live artifact is a match summary plus one non-Lucario observation, not
  decision-level Lucario JSONL.
- Live examples for Deck/Looking/Discard selection contexts.
- Whether card metadata can be loaded within the submission packaging and
  latency budget without adding a second source of truth.
