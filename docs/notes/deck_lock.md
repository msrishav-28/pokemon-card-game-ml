# Deck Lock Rationale

**Date:** 2026-09-04

**Stage:** S2
**Status:** LOCKED

> “Official-style Mega Lucario Fighting list from buddy bundle; operator is not a TCG designer; lock until S7.”

No card swaps.

---

## 1. Locked Deck List & Role Taxonomy

Source: `refs/buddy-lucario/deck.pkl`, exported to `configs/decks/primary.yaml`, `submission/deck.csv`, and `submission/deck.json`.

| Card ID | Card Name | Count | Category | Primary Role | Secondary Role / Tactical Note |
|---|---|---|---|---|---|
| 673 | Makuhita | 2 | Pokémon (Basic) | Basic / Pivot | Early meat-shield (80 HP); pre-evolution |
| 674 | Hariyama | 2 | Pokémon (Stage 1) | Secondary Attacker / Gust | 150 HP; Wild Press does 210 and 70 self-damage; evolution Ability gusts |
| 675 | Lunatone | 2 | Pokémon (Basic) | Draw Engine | Lunar Cycle discards a Basic Fighting Energy to draw 3 when Solrock is in play |
| 676 | Solrock | 3 | Pokémon (Basic) | Single-energy Attacker | Cosmic Beam does 70 only while Lunatone is on the Bench |
| 677 | Riolu | 3 | Pokémon (Basic) | Pre-evolution | Key setup target; evolves to Mega Lucario |
| 678 | Mega Lucario ex | 4 | Pokémon (Mega ex) | Primary Attacker | High-damage anchor (340 HP, multi-prize threat) |
| 1102 | Dusk Ball | 4 | Trainer (Item) | Search | Looks at the bottom 7 cards for a Pokémon |
| 1123 | Switch | 2 | Trainer (Item) | Pivot | Emergency retreat without energy cost |
| 1141 | Premium Power Pro | 4 | Trainer (Item) | Buff / Tempo | Flat damage amplification on attacks |
| 1142 | Fighting Gong | 4 | Trainer (Item) | Search | Finds a Basic Fighting Energy or Basic Fighting Pokémon |
| 1152 | Poké Pad | 4 | Trainer (Item) | Search | Finds a Pokémon without a Rule Box |
| 1159 | Hero Cape | 1 | Trainer (Tool) | Survivability | Massive +100 HP boost to survive 2HKO/OHKO |
| 1182 | Boss's Orders | 2 | Trainer (Supporter) | Gust | Pulls vulnerable benched Pokémon for KO |
| 1192 | Carmine | 4 | Trainer (Supporter) | Draw | Fast opening hand refresh (playable turn 1) |
| 1227 | Lillie's Determination | 4 | Trainer (Supporter) | Draw | Shuffles the hand into the deck, then draws 6 (8 at exactly 6 prizes) |
| 1252 | Gravity Mountain | 2 | Trainer (Stadium) | Board Control | Reduces each Stage 2 Pokémon's HP by 30; Mega Lucario ex is Stage 1 |
| 6 | Basic Fighting Energy | 13 | Energy | Energy | Powers attacks across all Fighting Pokémon |

**Total Cards:** 60

- **Basics:** 10
- **Evolutions:** 6
- **Trainers:** 31 (8 Draw Supporters, 2 Gust Supporters, 12 search Items, 4 damage buffs, 2 pivot Items, 1 Tool, 2 Stadiums)
- **Energy:** 13

---

## 2. Quantitative Deck Metrics (Computed, Not Vibed)

- **P(at least one Basic in opening 7 cards):**
  $$P(X \ge 1) = 1 - \frac{\binom{50}{7}}{\binom{60}{7}} = 1 - \frac{99,884,400}{386,206,920} \approx 0.7414 \quad (74.14\%)$$
  Expected mulligans before a valid 7-card hand: $\sim 0.35$.
- **P(Mega Lucario ex ready to attack by Turn 3):** not claimed. Search/draw effects and turn order make a closed-form estimate misleading; live replay measurements are the accepted evidence.
- **Search count:** 12 cards (4 Dusk Ball, 4 Fighting Gong, 4 Poké Pad), with different legal targets
- **Draw count:** 8 cards (4 Carmine, 4 Lillie's Determination)
- **Energy count:** 13 basic Fighting Energy
- **Distinct high-branch trainers:** 0 complex multi-modal search engines (unlike Arven / Irida / Ultra Ball branching trees, Dusk Ball and Fighting Gong have strictly constrained decision branches).

---

## 3. Candidate Scoring (1–5 scale, 5 is best)

| Criterion | Candidate 1: Mega Lucario ex (Buddy/Starter) | Candidate 2: Dragapult Pilot (In-Contest) | Candidate 3: Miraidon/Lightning (Theoretical) |
|---|---|---|---|
| **Opening Consistency** | **4** (10 Basics, 8 draw supporters) | **3** (Stage 2 line; requires multiple rares) | **5** (Tandem Set ability fetches basics) |
| **Branching Chaos** | **5** (Linear Fighting attacks; low search branching) | **2** (Complex damage counter spreads on bench) | **3** (Multiple generator targets) |
| **Prize-Path Clarity** | **5** (2-2-2 or 1-2-1-2 straightforward KOs) | **3** (Multi-turn bench snipe setup) | **4** (Direct prize race) |
| **Recoverability** | **4** (4 Poké Pad + 4 Gong + high HP basics) | **3** (Slow to rebuild Stage 2 if KO'd) | **3** (Resource hungry) |
| **AI-Explainability** | **5** (Attach energy, evolve, attack, retreat, gust) | **2** (Phantom Dive counter distribution requires 2D solver) | **4** (Fast energy acceleration) |
| **Total Score** | **23 / 25** | **13 / 25** | **19 / 25** |

### Decision
Candidate 1 (Mega Lucario ex) decisively wins for a heuristic / gated search agent architecture. It provides maximum AI-explainability, minimal branching complexity, and reliable prize-path mechanics for an operator who is not a competitive TCG designer.

---

## 4. Verification & Baseline Rerun

- `submission/deck.csv`: 60 valid integer card IDs.
- `configs/decks/primary.yaml`: Identical 60 card IDs.
- Baseline 100-game run on locked deck: **0 INVALID, 0 ERROR, 0 TIMEOUT**, 69.0% win rate vs `"random"`.
- Gate cleared. Deck is frozen through S7.
