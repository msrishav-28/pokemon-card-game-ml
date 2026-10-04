# Decision bets

Each strategic change is written here before implementation or integration. A bet is accepted only if legality and timing remain perfect; win-rate language requires at least 200 games against the same frozen opponent set.

## B0 — Establish a live legal floor

- **Evidence:** stale Python launcher; no trustworthy fresh run at session start.
- **Bet:** repair the local runtime and run the existing submission unchanged before changing strategy.
- **Success:** official `make("cabt")` completes; exact path submission completes; 20 games versus `random` have zero invalid, timeout, and engine errors.
- **Result:** accepted. The 20-game smoke was 11–9, zero invalid/timeout/error, mean decision latency 0.5 ms. This is not an improvement claim.

## B1 — Correct the live AreaType mapping before tuning weights

- **Evidence:** the live fixture offers ATTACH targets with `inPlayArea=4` when only an Active Pokémon exists. The official buddy API enumerates Active=4 and Bench=5. `action_features.py` currently uses Active=3 and Bench=4, so target resolution silently returns the wrong Pokémon or none.
- **Bet:** correct only the area constants and lock them with a live-fixture regression test.
- **Expected effect:** attachments/evolutions can be ranked using their actual target; no action-encoding change.
- **Accept:** all contract tests pass, zero invalid/timeout in smoke, and a 200-game seat-balanced ablation against the frozen pre-fix policy does not show a material regression.
- **Reject/revert:** any invalid/timeout, or a material head-to-head loss against the pre-fix policy. Because current `cabt` exposes no proven deterministic chance seed, call this seat-balanced rather than paired-seed evidence.
- **Result:** accepted as a correctness repair, not as the final policy. Against
  the incumbent in 200 seat-balanced games it scored 112–88 (56.0%, Wilson
  49.1–62.7%) with zero safety failures. Against the same frozen external set,
  random improved 66.5%→76.0%, first 34.5%→36.5%, and buddy changed
  27.5%→26.5%. Native chance is unseeded, so only the direct match and separate
  confidence intervals are reported; the buddy row shows that area mapping
  alone does not solve tactical play.

## Next bet selection

After B1, choose the largest replay-derived loss bucket against `first` and buddy. Search, learning, a second deck, and broad weight tuning remain out of scope until the runner associates every decision with a terminal result and at least 50 legal live games exist.

## B2 — Never choose a visible non-KO over a visible game-winning KO

- **Evidence:** official `AllAttack` data gives Aura Jab (982) 130 damage and Mega Brave (983) 270. In a deterministic policy state with Mega Lucario ex, both attacks legal, opponent Active at 200 HP, and one prize remaining, the incumbent ranks Aura Jab 644 over Mega Brave 626. That declines a visible game-winning knockout.
- **Bet:** add a narrow lethal-first attack comparator using official attack damage and visible Active HP. Treat only base-damage certainty as lethal initially; do not invent weakness, buffs, or effect state. If both attacks KO, prefer the lower-cost/non-locking attack.
- **Accept:** regression test proves 983 is selected in the 200-HP/one-prize state; all contract tests pass; zero invalid/timeout; and a 200-game seat-balanced B2-vs-B1 ablation is not materially worse.
- **Reject/revert:** any legality/timing regression or a material head-to-head loss. Report opponent win-rate changes separately; do not call synthetic-state correctness a measured win-rate improvement.
- **Result:** accepted as a narrow invariant. B2 versus B1 over 200 games was
  94–1–105 (47.0%, Wilson 40.2–53.9%), with zero invalid/timeout/error and
  sub-millisecond p95 latency. The guard fired in 23 decisions, selected a
  flagged last-prize attack every time, changed the unboosted argmax 10 times,
  and all 23 affected games ended in wins. The aggregate interval includes
  50%, so this is not claimed as a general win-rate improvement.

## B3 — Replace the hallucinated linear scorer with a visible attack plan

- **Evidence:** the frozen incumbent scored 55–145 (27.5%) against buddy over
  200 games. The B1-corrected scorer scored 53–147 (26.5%). Replay audit found
  10,698 all-zero feature vectors and 7,063 flat score vectors, while the policy
  audit found wrong official semantics for four trainers and no damage-aware
  attack target plan. The frozen buddy's deck-specific `AttackPlan` is therefore
  measured evidence, not a hypothetical architecture.
- **Bet:** cleanly port the buddy's plan/follow-through into a policy that still
  consumes the single `CanonicalState`, uses official AreaType 4/5, reads only
  official card metadata, emits an aligned score/feature row for every legal
  option, and retains the B2 last-prize guard.
- **Accept:** focused contract tests pass; 20-game smoke against every frozen
  opponent has zero invalid/timeout/error; in N=200 evaluation, zero safety
  regressions, p95 comfortably below the clock, the direct incumbent match has
  a Wilson lower bound above 50%, and the buddy Wilson lower bound exceeds the
  incumbent's 27.5% point estimate.
- **Reject/revert:** any safety failure; dependency on a second engine/native
  library; a direct-match interval that includes 50%; or no material recovery
  against buddy. If accepted, record the scorer-architecture change in
  `doctrine_diff.md`.
- **Result:** accepted and promoted. AttackPlan beat the frozen incumbent
  156-44 (78.0%, Wilson 71.8-83.2%) with zero safety failures, so the direct
  gate is decisive. Its policy-selection runs scored 97.0% versus `random`,
  81.0% versus `first`, and 41.5% versus buddy. A separate result-grade run of
  the promoted `submission/main.py` scored 94.0%, 82.5%, and 49.0%
  respectively (N=200 each), again with zero invalid, timeout, error,
  contract-failure, or fallback events. The buddy interval, 42.2-55.9%, does
  not prove greater-than-50% strength; it does prove a material recovery from
  the incumbent's 27.5% point estimate.

## B4 — Establish turn-sequence causality before another strategy change

- **Evidence:** the final 600-game replay audit links all 149 losses to their
  exact decisions, but no terminal record identifies a causal decision. The
  conservative detector flags 33 visible last-prize base-damage opportunities
  and six apparent misses among 56,131 decisions; these may be sequencing
  steps before an attack rather than errors. There are also 594 `ACTIVATE`
  prompts, where an optional-ability choice could affect a tactical plan.
- **Bet:** add a read-only, turn-sequence diagnostic that follows each flagged
  opportunity through the remainder of the same turn and distinguishes a
  delayed lethal attack, a state-changing legal line, and a turn ending
  without the visible attack. Audit optional ability prompts the same way
  before changing their response policy.
- **Accept:** every flag is linked only by explicit `game_id`, player, turn,
  and decision order; retained observations remain byte-for-byte live data;
  focused tests cover sequencing; no policy or engine behavior changes.
- **Reject:** any inferred hidden state, prize-snapshot outcome, cross-game
  join, or strategy change made before the diagnostic supplies causal evidence.
- **Status:** parked after freeze. The B3 player is the release candidate; B4
  is the next evidence-gathering step, not an unmeasured policy patch.

## Parked correction set — trainer semantics

Official EN data also contradicts several incumbent feature comments: Premium Power Pro adds 30 attack damage, Fighting Gong searches a Basic Fighting Energy or Basic Fighting Pokémon, Carmine discards the whole hand then draws five, and Gravity Mountain reduces Stage 2 HP (Mega Lucario ex is Stage 1). These are confirmed defects, but they will not be mixed into B2. After result-linked replay counts identify which one changes decisions most often, record a separate bet and ablate it.
