# Chess Coach — Product & Technical Spec v2.1

Oct 29, 2026 · Owner: Sam · Status: **Final specification for Claude Code**
History: v1 (Claude) → ChatGPT review → v2 (Claude) → ChatGPT second review and Sam's product decisions → **v2.1 (this document)**

Chess Coach is a personal chess coach for one player. It analyzes his chess.com games, identifies the recurring weaknesses that cost him the most, teaches him to recognize and prevent them through guided practice and targeted human-like sparring, and measures whether those mistakes become less frequent in real games. The north star is sustained rating improvement.

### Instructions for Claude Code

1. Read the whole document before writing code.
2. Build in the phase order in §27. Do not start a phase until its exit gates pass.
3. Every number marked *(tunable)* or *(hypothesis)* lives in `/server/config/coach.toml` and is never hard-coded.
4. Every item marked **[Verify]** must be confirmed from a primary source or by experiment in Phase 0 before code depends on it.
5. Do not begin implementation until Sam confirms §0.

### Evidence labels used throughout

| Label | Meaning |
| --- | --- |
| **Verified** | Confirmed from a primary source listed in §31 |
| **[Verify]** | Believed true; must be confirmed in Phase 0 |
| **Assumption** | Engineering choice; reasonable but unproven, to be tested |
| **Hypothesis** | Training-design guess with no direct evidence; tunable, never presented to Sam as fact |
| **Experimental** | Model-based metric; shown only in a labeled area and never used for headline claims |

---

## 0. Remaining decisions for Sam

All decisions are resolved. Sam answered on Oct 29, 2026.

| # | Decision | Answer |
| --- | --- | --- |
| D1 | Repertoire source | **No PGN files.** Build the starting repertoire from the lines in Sam's own games, plus recommended fixes he approves (§16) |
| D2 | Hosting and domain | **Free hosting, no domain** (§29). Start with an artifact prototype hosted on claude.ai (Phase P, §27) |
| D3 | LLM spending cap | **$15/month hard cap, warning at $10.** Above the cap, template explanations only |
| D4 | Test devices | **Latest iPhone and a 5-year-old iPad Pro.** The iPad Pro is the oldest supported device and sets the performance targets |

**Already decided by Sam:**

- Rapid (10 min) is the primary benchmark, confirmed against game history in Phase 0. Blitz is analyzed separately.
- Ratings: rapid about 1000–1100, blitz about 700. Do not treat the blitz gap as weaker understanding; investigate it (§14).
- Sessions are flexible: 10, 15, 30, or 45–60 minutes, plus sparring.
- Sparring is a core feature, server-based first.
- The repertoire stays under Sam's control. Unanswered deviations stay unresolved.
- Guided correction comes before any solution is shown.

---

## 1. Vision and principles

**North star: Sam's rating keeps going up.** Every threshold and difficulty setting serves the most real improvement per minute of training. When Sam demonstrates mastery, the bar moves up. The app maximizes improvement per minute, not time spent in the app.

**The coaching loop:**

1. Analyze Sam's games.
2. Find recurring weaknesses.
3. Rank them by importance.
4. Choose exercises that target them.
5. Teach recognition and prevention.
6. Test on unfamiliar positions.
7. Measure frequency in real games.
8. Adjust.

**Principles**

1. **Engine is truth.** Stockfish decides good and bad, tablebases decide endgames they cover, and Maia estimates what humans play. Text never states a chess fact that these sources or a validated detector did not produce.
2. **Validated consequences only.** A geometric pattern is not a cause unless an engine line shows it matters.
3. **Honest uncertainty.** The app never claims to know what Sam was thinking. Cognitive labels such as "calculation" or "habit" are assigned only when explicit evidence rules are met, and they are shown as "likely", with the evidence listed.
4. **Diagnosis separate from prescription.** One engine finds what goes wrong; another chooses training. Both are inspectable.
5. **Purposeful training.** Every exercise is linked to a diagnosed weakness, a review that is due, or a transfer test. Random puzzles are never served.
6. **Guided correction.** Sam gets a fair chance to find his own error before any solution is shown.
7. **Measure transfer.** Success means fewer of the same mistakes in new games and better results on unseen positions.
8. **Adaptive, upward difficulty.** Train mostly at the edge of ability, and move the edge up on demonstrated mastery.
9. **Phone first, offline tolerant.** The server is the system of record.
10. **Degrade gracefully.** Every model-dependent feature has a defined fallback.
11. **Educational value over technical sophistication.**

## 2. Priority tiers

| Tier | Features |
| --- | --- |
| **Essential** (initial coaching loop) | Accurate game analysis; recurring weakness identification; guided mistake correction; personalized training from Sam's own games; adaptive explanations (templates first, then LLM); measurement of real improvement; basic progress view |
| **High** (follows once the core works) | Opening repertoire development with recommendations; spaced repetition; human-like targeted sparring (server-based); adaptive difficulty; time-control gap analysis |
| **Later / Experimental** | Rating forecasts; sparring ratings; full on-device inference; responsiveness learning; FSRS-for-tactics experiment; advanced analytics |

## 3. Success criteria

**After 8 weeks** (these decide further investment):

- Sam completes at least 4 sessions a week, and most finish within the selected budget.
- The rate of the top 2 trained weaknesses falls versus the baseline, per opportunity where it can be measured reliably (§13.5) and per game otherwise. Intervals are reported.
- First-attempt success on *unseen* positions with trained motifs rises.
- Opening recall on spaced-repetition cards stays at 85% or higher.
- Sam rates the app useful enough to keep using.

**Long term:** the smoothed rapid rating rises. The ladder target is the smoothed peak + 50, re-raised each time it is hit *(tunable)*. Eight weeks of rating movement alone is not proof that training works.

**Metric trust**

| Trusted (measured) | Experimental (model-based) |
| --- | --- |
| Game results and rating history | Estimated Elo gain from a weakness |
| Engine-evaluated mistakes and their raw cost | Training priority and responsiveness weights |
| Exercise outcomes: first-attempt and eventual success, help used | Maia findability F, rating anchor, unlock rating |
| Puzzle rating from unseen first attempts | Cognitive-need labels (§12.4) |
| Opening recall | Sparring performance ratings |
| Training time | Habit findings (statistically flagged, but descriptive only) |

## 4. Scope

**MVP (Phases 0–6), in order:**

1. Import and analysis.
2. Game review.
3. Classification.
4. Guided-correction training from Sam's own games.
5. Think First cards.
6. Template explanations.
7. Basic progress view.
8. Weakness reports with measured rates.
9. Habit findings.
10. Time-control gap report.
11. Adaptive session planner.
12. Theme puzzles with a Glicko-2 puzzle rating.
13. Transfer tests.
14. Maia findability.
15. Basic targeted sparring (server-based).
16. LLM adaptive explanations.
17. Opening repertoire builder with recommendations and spaced repetition.
18. Offline drills.

**After the MVP:**

- Phase 7: advanced targeted sparring with a steered opponent and test opponents.
- Phase 8: on-device inference and offline sparring.
- Phase 9: calibration and experimental features.

**Non-goals:** native apps; assistance during active rated games; multi-user accounts; Lichess game import (roadmap); training our own neural networks.

## 5. Architecture

```
chess.com API ─► Sync ─► Stockfish 18 ─► Classifier ◄─ Tablebase (≤5 pieces)
                              │          (detectors, errors, context, needs)
                         Maia-3 (server) ───┤
                                            ▼
                ┌──────────────── DIAGNOSIS ENGINE ────────────────┐
                │ game-review importance · weaknesses (raw/train-  │
                │ able cost) · opportunities · habit findings ·    │
                │ time-control gap · trends · confidence           │
                └─────────────────────────┬────────────────────────┘
                                          ▼
                ┌─────────────── PRESCRIPTION ENGINE ──────────────┐
                │ training priority · exercise selection · diffi-  │
                │ culty mix · diversity · session recommendation   │
                └───────┬──────────────────┬──────────────┬────────┘
                        ▼                  ▼              ▼
              Exercises (guided     Sparring service   Repertoire
              correction ladder)    (Maia opponents)   builder (FSRS)
                        └───────── Explainer (templates → LLM) ──┘
                                          ▼
     iPhone/iPad PWA: session runner, board, review, sparring client,
     repertoire, offline cache, append-only event queue ──► server
```

| Where | Component | Job |
| --- | --- | --- |
| Server | Sync | chess.com import, backfill, rating snapshots |
| Server | Analysis | Stockfish passes, tablebase lookups, Maia predictions |
| Server | Classifier | Detectors, chess errors, context tags, cognitive-need labels |
| Server | Diagnosis | Game-review importance, weaknesses, opportunities, habits, time-control gap |
| Server | Prescription | Training priority, exercise selection, session plans |
| Server | Sparring service | Opponent move generation (Maia), start-position curation, post-game analysis |
| Server | Repertoire builder | History tree, theory comparison, recommendations, FSRS cards |
| Server | Explainer | Templates; LLM with validator; concept progression |
| Server | Postgres + job queue | System of record; idempotent jobs |
| Device | PWA | Session runner with the feedback ladder, board, game review, sparring client, repertoire, offline cache, event queue |
| Device (Phase 8) | On-device engines | Maia3-5M and Stockfish lite WASM for offline sparring |

## 6. Fact register

| Fact | Status |
| --- | --- |
| chess.com Published-Data API is read-only JSON with monthly archives; serial access is unlimited; parallel requests may get 429 | **Verified** ([chess.com](https://chess.com/news/view/published-data-api)) |
| The archive API returns only finished games | **[Verify]** |
| chess.com requires a descriptive User-Agent | **[Verify]** (unofficial SDK). Claude Code already has a working chess.com connection; confirm the behavior |
| Past monthly archives never change | **[Verify]**; resync is supported regardless |
| Lichess Win% = 50 + 50·(2/(1+e^(−0.00368208·cp)) − 1) | **Verified** ([Lichess](https://www.lichess.org/page/accuracy)) |
| Lichess move accuracy and game accuracy method, and mate handling | **[Verify]** against `lila` source |
| Stockfish 18 release and UCI options (`searchmoves`, MultiPV) | **[Verify]** from official Stockfish sources |
| Maia-3 sizes 3M/5M/23M/79M; UCI inference code; Elo conditioning | **Verified** repo exists ([CSSLab/maia3](https://github.com/CSSLab/maia3/wiki)); Python API and conditioning inputs **[Verify]** |
| Maia-3 license (AGPL-3.0 as stated by ports) | **[Verify]** |
| Lichess puzzle CSV fields include Rating, RatingDeviation, Popularity, NbPlays, Themes, OpeningTags | **Verified** ([database.lichess.org](https://database.lichess.org/)); license **[Verify]** |
| Lichess puzzle ratings are Glicko-2 ratings from solve attempts | **Verified** (same page describes attempts as Glicko-2 games) |
| Lichess opening explorer API availability, authentication and rate limits | **[Verify]**; fallback in §16.2 |
| Syzygy tablebase local file sizes, or Lichess tablebase API terms | **[Verify]** |
| `python-chess` exposes a SEE function | **[Verify]**; if absent, implement and test one |
| `python-chess` legal-en-passant FEN option | **[Verify]** |
| iOS home-screen web apps support Web Push | **[Verify]** on Sam's devices |
| Multi-threaded WASM needs cross-origin isolation | **Verified** ([lichess-org/stockfish.wasm](https://github.com/lichess-org/stockfish.wasm)) |
| `ts-fsrs` implements FSRS v6 | **Verified** ([ts-fsrs](https://open-spaced-repetition.github.io/ts-fsrs)) |

## 7. Data ingestion (chess.com)

### 7.1 Endpoints

Base URL: `https://api.chess.com/pub`.

| Endpoint | Use |
| --- | --- |
| `/player/{user}` | Profile; `player_id` is the stable key |
| `/player/{user}/stats` | Ratings by time class; daily snapshot |
| `/player/{user}/games/archives` | Monthly archive URLs |
| `/player/{user}/games/{YYYY}/{MM}` | One month's games with PGN |

### 7.2 Client rules

- Make requests serially.
- Send a User-Agent with the app name and a contact.
- Use ETag caching.
- Poll the current month every 30 min *(tunable)*.
- Retry 429 and 5xx responses with exponential backoff: 1 s, then doubling to a maximum of 60 s, for at most 6 tries. After that, mark the archive `failed` and retry next cycle.
- Provide a manual **Resync month** action.

### 7.3 Import order

1. Import the most recent 100 rapid games and the most recent 100 blitz games. Analyze them first.
2. Backfill everything else newest-first at low priority.
3. The app is usable after step 1.

### 7.4 Parsing and storage

Parse with `python-chess`. For each game, store:

- URL (unique key), time class, time control, rated flag, end time.
- Both players' ratings, Sam's color, result, termination.
- ECO code and opening name.

For each ply, store:

- SAN and UCI.
- Canonical position key before the move (§8.6).
- Clock from `[%clk]`; null if missing.
- Time spent, computed as the clock delta plus increment.

Corrupt PGNs get `parse_status = failed` and never block a batch.

**Filters:**

- Analyze rated bullet, blitz and rapid games.
- Store daily games but exclude them from clock statistics.
- Skip variants and unrated games.
- Do not analyze games under 6 plies.

## 8. Engine analysis

### 8.1 Passes *(budgets set after the Phase 0 benchmark)*

| Pass | Search | Scope |
| --- | --- | --- |
| First | `go nodes 1,000,000`, MultiPV 3, Threads 1, Hash 256 MB, `ucinewgame` per game | Every position |
| Played-move | `go nodes 1,000,000 searchmoves <played>` from the same root, same settings | Moves outside the first-pass top 3 |
| Deep | **One** search: `go nodes 5,000,000 MultiPV k searchmoves <top-3 moves> <played>` | Every Sam move with first-pass win_loss ≥ 5; every opponent move with win_loss ≥ 10 |
| Boundary | `go nodes 20,000,000`, same form as Deep | Deep-pass moves within ±2 Win% points of a class boundary or of the unique-solution gap |

The first and played-move passes are **separate searches**. Their difference carries search noise and is treated as provisional.

The deep pass places the played move and the top candidates inside a **single** MultiPV search, so they are compared within one search tree. The deep (or boundary) result is final for classification.

### 8.2 Evaluation uncertainty

- Each scored move stores `eval_delta` = |final win_loss − first-pass win_loss|.
- Phase 0 benchmarks the pipeline against a 50M-node reference on 500 positions. It records class agreement, mean absolute win_loss error, and the boundary-recheck rate.
- The spec claims no accuracy beyond what that benchmark measures.

### 8.3 Scores and classes

**Win%** uses the Lichess formula, with cp clamped to ±1500 first.

**Mate scores:** a mate for the mover gives Win% 100; being mated gives 0. **[Verify]** against `lila`; if it differs, match `lila`.

**Tablebase:** in positions with ≤ 5 pieces, tablebase win/draw/loss replaces the engine score: Win% is 100, 50 or 0, and DTZ is used for tie-breaks.

**Accuracy:** port move accuracy and game accuracy from `lila`, and cite the source in code.

**Classes** *(tunable; Coach's own labels, not claimed to match Lichess)*:

| Class | win_loss (Win% points) |
| --- | --- |
| Blunder | ≥ 15 |
| Mistake | 10 to < 15 |
| Inaccuracy | 5 to < 10 |
| Good | < 5 |

**Labels:**

- *Missed win*: the best Win% was ≥ 80 and the played move's Win% is ≤ 60.
- *Unique solution*: the best move leads the second-best by ≥ 10.
- *Acceptable*: win_loss < 5.

### 8.4 Suppression

A move is not flagged only when the position was already decided: the mover's Win% stays above 95 or below 5 both before and after.

**Repertoire moves are never suppressed.** A significant mistake inside the repertoire is flagged and creates a repertoire-fix proposal (§16).

### 8.5 Determinism

Results are reproducible only with the same binary, settings, hash state and machine. Every evaluation row records the engine version, build hash, settings, CPU model and pass type. Golden fixtures are listed in §25.

### 8.6 Canonical position identity

- **Key:** piece placement, side to move, castling rights, and the en passant square only when an en passant capture is actually legal. Halfmove and fullmove counters are excluded.
- **Storage:** the normalized string (`fen_norm`) plus a 64-bit Zobrist/Polyglot hash for indexing. The string decides equality, so hash collisions cannot merge positions.
- **Transpositions:** any two move orders that reach the same key share the same node in repertoire and position tables.
- **Repetition:** handled at game level (ply history), never in the key. A repertoire node is the same node no matter how often it repeats.

## 9. Detectors

### 9.1 Contract

Every detector returns facts at two levels:

- **Pattern:** geometry only, for example "the rook on d1 lines up with the knight on d4 and the queen on d8".
- **Validated:** an engine-confirmed outcome from the motif's allowed consequence types.

Only *validated* facts may be used as a mistake cause, in explanations, in weakness buckets, or in hints.

**Consequence types**

| Type | Engine-confirmed when… |
| --- | --- |
| Material | Net material change ≥ threshold, counted after exchanges resolve, within the motif's horizon |
| Mate | The line forces mate within the horizon |
| Forced draw | The line forces a perpetual check, stalemate or tablebase draw from a position the side was losing (Win% ≤ 20 before) |
| Evaluation swing | Win% changes by ≥ 15 for the side using the motif, and the motif's key move is in the line at or before the swing ply |
| Successful defense | After the move, every line that carried out the validated threat no longer wins material, mates, or swings ≥ 15 |

**Motif table** *(tunable)*

| Motif | Allowed consequences | Horizon (plies) | Material threshold |
| --- | --- | --- | --- |
| Hanging piece | Material | 2 | ≥ 1 pawn |
| Fork | Material, Mate, Swing | 4 | ≥ 2 |
| Pin | Material, Swing | 6 | ≥ 2 |
| Skewer | Material | 4 | ≥ 2 |
| Discovered attack / check | Material, Mate, Swing | 4 | ≥ 2 |
| Back-rank mate | Mate, Material | mate horizon (≤ 9) | ≥ 3 |
| Mate in ≤ 5 | Mate | 9 | n/a |
| Removal of defender / overload | Material, Mate, Swing | 6 | ≥ 2 |
| Trapped piece | Material | 6 | ≥ 2 |
| Promotion | Material, Swing | 6 | ≥ 3 |
| Intermezzo | Material, Swing | 4 | ≥ 1 |
| Perpetual / stalemate resource | Forced draw | 12 | n/a |
| Defensive resource | Successful defense | — | — |

**Strict validation rules:**

- The consequence must appear in the final-pass line.
- The motif's key move must be on that line at or before the consequence ply.
- The detector must name the pieces involved.

**SEE:** a static exchange evaluation routine is required **[Verify]** that `python-chess` provides one. If not, implement it and unit-test it.

**Positional and phase detectors** produce descriptive tags only:

- Game phase.
- King safety.
- Pawn structure, with named structure types such as Caro-Kann Advance chain, isolated queen pawn (IQP), and Carlsbad.
- Development.
- Mobility.
- Endgame type.

### 9.2 Threat detection

The null-move probe gives the opponent a free move from the position before Sam's move, searched at 200k nodes. It yields a **candidate threat**.

The candidate becomes a **validated threat** only when *either* of these holds:

- The refutation of Sam's actual move begins by carrying out that threat.
- A legal, plausible Sam move fails to the threat, confirmed by search from the real position. Plausible means Maia probability ≥ 0.05, available from Phase 4.

The probe is skipped when Sam is in check and in pawn-only endgames, where zugzwang is likely.

## 10. Classification

### 10.1 Primary chess error

Each flagged move gets exactly one error: the first rule that matches.

| # | Error | Rule |
| --- | --- | --- |
| 1 | `missed_mate` | Best line mates in ≤ 5; the played move does not |
| 2 | `hung_material` | The refutation's first move wins material the played move left hanging (by SEE) |
| 3 | `missed_recapture` | The opponent just captured; recapturing was best and was not played |
| 4 | `ignored_threat` | A validated threat existed and the refutation carries it out |
| 5 | `allowed_tactic` | The refutation contains a validated offensive motif |
| 6 | `missed_tactic` | The best line contains a validated motif for Sam; the played move does not use it |
| 7 | `missed_defense` | Sam faced a validated threat, the best move is a unique solution and a successful defense, and he didn't play it |
| 8 | `calculation_error` | Sam's move starts a forcing sequence (capture, check or threat) that the final line refutes at ply ≥ 3 *(evidence rule; see §12.4)* |
| 9 | `conversion_error` | Win% before ≥ 85 and win_loss ≥ 10 |
| 10 | `draw_trap` | The move allows stalemate, threefold repetition or a tablebase draw from Win% ≥ 70 |
| 11 | `endgame_knowledge` | ≤ 5 pieces and the move changes the tablebase result (win→draw or draw→loss) |
| 12 | `opening_error` | Opening phase, and the move loses ≥ 10 versus the best move or leaves theory (§16.2) with a loss ≥ 5 |
| 13 | `endgame_error` | Endgame phase (other cases) |
| 14 | `positional` | Middlegame, none of the above, win_loss ≥ 10 |
| 15 | `unclassified` | Anything else; never guessed |

### 10.2 Context tags

Zero or more per move:

- `time_pressure`: under 10% of the base time or under 15 s.
- `fast_move`: under 3 s while over 60 s remain.
- `slow_move`: over 3× Sam's median move time for that phase and time class.
- `out_of_book`.
- `after_opponent_capture`, `after_opponent_check`, `after_opponent_threat`.
- `piece_moved:<type>`.
- `move_type:<quiet|capture|check>`.
- `complex_position`: Maia entropy at the anchor rating above a threshold (Phase 4+).
- `repeated_position`.

### 10.3 Secondary tags

Motif, piece, phase, endgame type, structure type, color, time class.

## 11. Human context (Maia-3)

### 11.1 Placement

- **Server:** Maia3-23M *(fall back to 5M if the Phase 0 benchmark fails)* via the CSSLab `maia3` package, pinned to a commit.
- **Analysis:** Maia scores Sam's moves and flagged opponent moves.
- **Sparring:** Maia supplies opponent moves (§19).
- **Device:** on-device Maia arrives only in Phase 8.

### 11.2 Rating anchor A (per time class)

Maia was trained on Lichess ratings. Compare three models on a time-based held-out split (the most recent 20% of games):

- (a) chess.com rating as-is.
- (b) chess.com rating plus one fitted global offset.
- (c) Maximum-likelihood R_eff, shrunk toward (b).

**Fit rules:**

- Exclude repertoire moves, the first 10 plies, forced moves (one legal move), and unique solutions leading by ≥ 30.
- Search 600–2400 in steps of 50.
- Report a game-level bootstrap interval.

**Selection:** use (c) only if its held-out log-likelihood beats (b) by ≥ 1% *(tunable)*. Otherwise use (b). Use (a) if (b) does not beat it.

**Guards:**

- A changes by at most 50 per week.
- A never falls below (b) − 100.

**Blitz:** fit A separately for blitz. A blitz A far above Sam's blitz rating is evidence for the time-control gap analysis (§14). It is never used to lower rapid training difficulty.

### 11.3 Derived scores (experimental)

**F (findability).** The sum of Maia probabilities over acceptable moves, from the **full legal-move distribution**. Store the exact F and the top 10 moves.

F estimates how often players at rating A pick an acceptable move in normal play. It is not a prediction of puzzle success: in a puzzle, Sam knows something is there.

**T (temptation).** The Maia probability of the move Sam played.

**Unlock rating.** The lowest rating in A − 200 … A + 400 (steps of 100) where F ≥ 0.5. If F drops by > 0.1 between adjacent steps, mark it `uncertain`.

**Bands** *(tunable)*:

| Band | Rule |
| --- | --- |
| Should-find | F ≥ 0.5 |
| Stretch | 0.2 ≤ F < 0.5 and unlock ≤ A + 400 |
| Beyond | Otherwise |

**Before Phase 4,** a simplicity proxy stands in for F *(hypothesis)*:

- 1.0 if the best move is a capture, a check, or a validated motif within 2 plies.
- 0.6 otherwise.

### 11.4 Maia as a prior

For each motif, Sam's observed first-attempt success on unseen positions gradually replaces Maia-based difficulty when choosing exercises. The weight moves linearly from 0 at 20 attempts to 1 at 60 attempts.

## 12. Diagnosis engine

### 12.1 Two rankings

**Game Review Importance (GRI)** is objective. Findability is **not** used, so a catastrophic but hard-to-see mistake stays visible.

```
GRI = win_loss × (1.2 if a validated motif or mate is involved else 1.0)
```

**Game review rules:**

- Always show the game's single largest objective swing for Sam, whatever its F.
- Then show the next 2 highest GRI moves for Sam.
- Then show up to 2 opponent mistakes Sam failed to punish.

**Training Priority (TP)** is per weakness and is computed in §15.1. It uses severity, recurrence, findability, responsiveness and training cost.

### 12.2 Weaknesses without double counting

- **Primary weakness:** chess error + motif, for example `allowed_tactic:fork` or `endgame_knowledge:rook`. Each flagged move belongs to exactly one primary weakness.
- **Views:** phase, color, opening, structure, context and time class are filters for drill-down. Views are never summed.
- **Total preventable loss** is computed directly from moves.

### 12.3 Costs and windows

```
RawCost(w)       = Σ win_loss        / N_games   (Win% points lost per game; what the UI states)
TrainableCost(w) = Σ win_loss × F    / N_games   (input to Training Priority only)
```

**Window:** per time class, the most recent 100 games of that class, excluding games older than 180 days *(tunable)*. With fewer than 30 games, show "Not enough games yet". Rapid drives prescriptions; blitz has its own report and feeds the time-control gap analysis.

### 12.4 Cognitive-need labels (experimental, evidence-gated)

Labels are assigned only when the stated evidence is present. Otherwise the label is `undetermined`. They are always phrased as "likely … because …", with the evidence shown.

| Label | Evidence required |
| --- | --- |
| **Knowledge** | `endgame_knowledge` (tablebase-confirmed); or `opening_error` at a position where theory exists (§16.2) and Sam's move is rare among stronger players there; or a recurring error in a named, teachable technique (for example Lucena or Philidor positions recognized by detector) |
| **Pattern recognition** | `missed_tactic`, `allowed_tactic` or `hung_material` where the motif resolves within 2 Sam moves and F ≥ 0.5 (most peers find it) |
| **Calculation** | `calculation_error`; or a tactic needing ≥ 3 Sam moves, where Sam played the first move of the right idea but the line failed later |
| **Decision habit** | The error belongs to a statistically flagged habit finding (§12.6) |

### 12.5 Opportunities

Rates are reported only where the denominator can be defined reliably. Every rate shows n and a 90% Wilson interval.

| Reliability | Family | Opportunity (denominator) | Success |
| --- | --- | --- | --- |
| A | Offensive tactic `<motif>` | Sam to move; the final-pass best line contains a validated motif for Sam with gain ≥ 10 Win% | Sam plays an acceptable move that keeps the gain |
| A | Missed mate | Sam to move; the engine shows mate ≤ 5 | Sam plays a mating-line move |
| A | Recapture | The opponent just captured; recapture is best by ≥ 5 | Recaptured |
| A | Conversion | Sam to move at Win% ≥ 85 | No Mistake or worse played |
| A | Hung material | Every Sam move | No `hung_material` |
| B (Phase 4+) | Defensive tactic `<motif>` | Sam to move; at least one plausible Sam move (Maia p ≥ 0.05) allows a validated opponent motif with gain ≥ 10, and at least one acceptable move avoids it | Sam's move avoids it |
| B | Threat awareness | A validated threat exists before Sam's move | Sam's move neutralizes it |
| C | Positional, opening, other | No reliable denominator | Per-game counts only, labeled as such |

### 12.6 Habit findings (descriptive)

A habit finding is a condition under which Sam's error rate is clearly elevated. It describes **when** errors happen and never **why** Sam thought something.

**Method:**

- For each condition (context tags from §10.2 and pairs of them), compare Sam's Mistake-or-worse rate on moves with the condition against moves without it.
- Flag the condition when all of these hold *(tunable)*:
    - At least 10 errors under the condition.
    - Rate ratio ≥ 1.5.
    - A game-level bootstrap 90% interval of the ratio that excludes 1.
- Correct for multiple comparisons with Benjamini–Hochberg at q = 0.10.

**Output example:** "Your mistake rate is 2.3× higher on the move right after your opponent captures (14 of 61 moves vs 9%)."

**Teaching routine:** each finding links to a pre-move routine (§17.4) and to Think First cards drawn from those exact situations.

### 12.7 Uncertainty and improvement

- Bootstrap at game level: 1,000 resamples including zero-occurrence games, giving a 90% interval for RawCost.
- **Tentative** when there are < 8 occurrences, < 5 games, or the interval width exceeds the estimate.
- **"Improving"** only when the 90% interval of the rate difference, follow-up minus baseline, lies entirely below zero. The baseline is the 60 days before training on that weakness began; the follow-up is from 14 days after it began.

### 12.8 Weekly report

The report is produced Sunday 20:00 America/New_York, and in-app at any time.

For each of the top 3 weaknesses by Training Priority it shows:

- A plain name.
- RawCost with its interval and the tentative flag.
- Occurrences and the rate per opportunity, where reliable.
- The trend.
- The likely need label with its evidence.
- Two example positions.
- The prescription.
- A re-check date.

It also includes new habit findings and the time-control gap summary.

**No Elo forecasts.**

## 13. Measurement of real improvement

Per weakness, the app tracks four things:

1. Exposure: minutes and cards trained.
2. Exercise outcomes: first-attempt and eventual success, help used.
3. Transfer: first-attempt success on unseen positions with the same motif.
4. The real-game rate (§12.5).

These live on the Progress screen. Trained and untrained weaknesses are shown side by side as an informal comparison. That comparison is not presented as causal proof.

## 14. Time-control gap analysis (rapid vs blitz)

The question is why blitz (about 700) is far below rapid (about 1000–1100). Each hypothesis is tested with a measurable comparison, and the report states which comparisons show differences and how large, with intervals.

| Hypothesis | Comparison (blitz vs rapid) |
| --- | --- |
| Time management | Share of games lost on time; clock remaining by move 20/30; share of moves under `time_pressure` |
| Decision speed costs accuracy | Error rate by time-spent bucket; `fast_move` error rate |
| Tactical recognition under speed | Offensive and defensive opportunity success rates by motif |
| Openings | Win% at ply 15; out-of-book ply; opening error rate |
| Clock collapse late in games | Error rate by clock-remaining bucket (> 50%, 20–50%, < 20%) |
| Underlying skill | Rating anchor A per time class (§11.2), plus accuracy on moves played with ample time (> 50% clock) |

**Conclusions** are phrased as "Most of the blitz gap appears in moves made with under 20% of your clock (error rate 3.1× rapid; n = …)". If no comparison separates clearly, the report says so.

**Prescriptions:** a gap explained by time pressure prescribes timed drills (§19.4). One explained by recognition prescribes speed-graded pattern drills on mastered motifs.

## 15. Prescription engine

### 15.1 Training Priority

```
TP(w, activity) = TrainableCost(w) × Recurrence(w) × Responsiveness(activity, w)
                  / MinutesPerWeek(activity, w)
Recurrence(w)   = min(1, occurrences_in_window / 8)
```

**Responsiveness** uses fixed, configurable weights *(hypotheses; not learned automatically in the MVP)*:

| Weakness family | Activity | Weight |
| --- | --- | --- |
| Opening errors | Repertoire drills | 1.0 |
| Hung material / ignored threat / missed recapture / missed defense | Think First + guided puzzles | 1.0 |
| Motif tactics | Own-game + theme puzzles | 0.8 |
| Missed mate | Puzzles | 0.8 |
| Calculation | Multi-move guided puzzles | 0.6 |
| Conversion / defense | Sparring from curated positions | 0.6 |
| Endgame knowledge | Technique drills + sparring | 0.7 |
| Time-pressure habits | Timed drills | 0.5 |
| Positional | Sparring in structures | 0.3 |
| Unclassified | — | 0 |

The app records every training exposure and the later real-game outcomes. Statistically grounded responsiveness learning is deferred to Phase 9 (§28).

### 15.2 Difficulty mix

These shares apply within each skill block *(hypothesis)*.

| Share | Kind | Target |
| --- | --- | --- |
| 30% | Reinforcement | Failed and due cards; expected first-attempt success ≥ 75% |
| 50% | Challenge | Expected first-attempt success 55–75% |
| 20% | Stretch | Expected first-attempt success 35–55% |

**Ratchet:** a motif moves up a tier when the last 30 first attempts at that tier reach ≥ 80% independent success, including ≥ 10 unseen positions.

### 15.3 Diversity rules

- Each exact position at most once per session.
- At most 2 consecutive cards of the same motif.
- At least 25% unseen positions per motif once 5 of its cards are mastered.
- After 2 failures on a card, the next card for that motif is a fresh, easier position.
- No card is served without a link to a weakness, a due review, or a transfer test.

### 15.4 Rating smoothing

- Daily rating snapshots are smoothed with an EWMA (14-day half-life).
- Difficulty and ladder changes require the smoothed rating to stay past the threshold for 14 days.

## 16. Opening repertoire

### 16.1 Ownership and identity

- **Ownership:** Sam owns the repertoire. All engine or app suggestions are proposals until he accepts them.
- **Structure:** a DAG keyed by canonical position (§8.6), so transpositions merge. An edge is active only when Sam created or accepted it.

### 16.2 Theory reference

1. **Primary:** the Lichess opening explorer for move frequencies and scores by rating band, if its API is usable **[Verify]**. Results are cached.
2. **Fallback:** a local reference built from a sample of the Lichess open database, players rated 1400–2000. Size and processing are **[Verify]** in Phase 0.
3. **"Known theory" at a position:** the position has ≥ 50 games in the reference at bands ≥ Sam's anchor + 200 *(tunable)*.
4. **"Left theory":** the first position Sam reaches that does not meet that bar.

### 16.3 History analysis

- Build Sam's opening tree from his games: frequency, score and average Win% at ply 15 and 20, per node.
- Find recurring opening mistakes: flagged moves in the opening phase that occur in ≥ 2 games at the same node or within the same structure type.

### 16.4 Recommendations (practical lines)

For a node needing improvement, rank candidate moves by four factors:

1. **Soundness:** win_loss < 3 versus best at deep pass.
2. **Practical score:** reference score at Sam's band and one band above.
3. **Understandability:** prefer moves that lead to named structures with plan notes (§16.5), and to lines where the top engine move stays stable across the next 3 plies.
4. **Fit:** consistency with structures Sam already plays.

Each proposal shows the move, plan notes, evidence (engine verdict and reference stats), and the games of Sam's that it affects. Sam taps **Accept** or **Reject**.

### 16.5 Ideas, not lines

Every repertoire branch carries **plan notes** of 3–5 bullets: typical plans, pawn breaks, piece placement, and common traps.

- **Grounded in:** structure detectors, recurring engine plan moves across the branch's positions, and reference stats.
- **Written** by the LLM as a *coaching interpretation*, validated for board facts (§18.3).
- **Approved** by Sam before they become part of the repertoire.

Cards quiz ideas as well as moves, for example: "What pawn break does Black aim for here?", graded against the plan note's validated break move.

### 16.6 Cards, depth and deviations

**Cards:** every repertoire position where Sam is to move. Scheduled with FSRS (`ts-fsrs`), target retention 0.90.

**Line drill:** opponent replies are weighted by Sam's real opponents' frequencies, then by reference frequencies at his band.

**Depth:**

- Starts at 6–8 of Sam's moves per branch *(tunable)*.
- Extends by 2 moves when all of a branch's cards are mature (FSRS stability > 21 days) and ≥ 30% of Sam's games in that branch go past the current depth.
- Prunes proposals for branches that his opponents rarely reach.

**Deviation handling:**

| Event | Behavior |
| --- | --- |
| Sam left his repertoire | Prompt once: "Forgot, or deliberate?" **Unanswered → stays `unresolved`** in an inbox, re-shown on the next Home visit, never auto-marked. Forgot → the card gets top priority. Deliberate → offer to add it as an alternative, or ignore it |
| The opponent left the repertoire (gap) | Create a proposal (§16.4) in the inbox |
| A repertoire move was a Mistake or worse | Flagged in review like any move, with a repertoire-fix proposal |

## 17. Training exercises and guided correction

### 17.1 Exercise types

| Type | Source | Answer |
| --- | --- | --- |
| Own-game puzzle | Sam's flagged moves (and missed punishes) | Unique-solution line, up to 3 of Sam's moves |
| Theme puzzle | Lichess puzzle pack, chosen per weakness | Lichess solution line |
| Threat check | Validated threats from Sam's games | The opponent's threat move |
| Forcing scan | Any position from Sam's games | All opponent checks and captures (legal move generation) |
| What changed? | The opponent's last move in Sam's games | Squares and pieces newly attacked |
| Blunder check | Sam's actual move | Safe or unsafe (from classification) |
| Defend | `missed_defense` positions | The unique defensive move |
| Calculation drill | Multi-move lines (`calculation_error`, deep tactics) | Full line, each move graded |
| Technique drill | Tablebase positions in Sam's weak endgame types | Tablebase-correct moves to a target (for example, a win in DTZ) |
| Opening card | Repertoire | Repertoire move or idea |

**Build-time checks:** every line is replayed from its FEN for legality, side to move, and board orientation. Failing exercises are dropped and logged.

### 17.2 The feedback ladder

**Goal:** Sam finds his own error with the least help that works. The ladder adapts to difficulty and history, Sam can always ask for the solution, and no loops are allowed.

| Stage | What happens |
| --- | --- |
| **1. Independent attempt** | Position shown with the prompt ("White to move. Find the best continuation."). No hints are visible, but a quiet "Help" and a "Show solution" control are always present |
| **2. Reflection** | After a wrong move: "Not quite." The board resets to the position. The coach asks **one** question chosen from the validated facts for this exercise (table in §17.3). An optional **"Show me why"** plays the opponent's best reply to Sam's move on the board, then resets, so Sam sees the consequence without the answer |
| **3. Targeted hint** | After a second wrong move, or if Sam taps Help. A hint from the validated error type that names the category, not the move ("There is a forcing move that wins material.") |
| **4. Stronger hint** | Highlights a relevant piece, square, or the threat arrow, and names the motif if validated ("Look at what your knight can attack from e5.") |
| **5. Solution** | Plays the best move with the adaptive explanation (§18), level 1, and offers "Go deeper" |
| **6. Reinforcement** | Sam replays the full correct line from the start. A **related position** (same motif, unseen) is queued later in the session. If none exists, it is queued for the next session |

**Adaptive budget** *(hypothesis)*: the number of wrong attempts allowed before advancing a stage.

| Situation | Attempts per stage |
| --- | --- |
| Card expected easy (≥ 75%) or reinforcement | 1 |
| Challenge | 2 at stage 1, then 1 |
| Stretch or calculation drill | 2 per stage |
| Sam failed this motif twice in a row recently | 1 (move faster to teaching) |

**Hard limits:**

- After 5 total wrong moves, go straight to stage 5.
- No stage repeats.
- "Show solution" jumps to stage 5 at any time.

**Anti-guessing:**

- A wrong move made under 2 s after the previous wrong move triggers: "Take a moment: check your opponent's forcing replies first."
- That move counts as a guess.
- 2 guesses on a card cap its credit at *Revealed*.

**Near-misses:**

- A move within 3 Win% points of the best is accepted as correct, and the stronger move is named.
- A move losing 3–10 gets "Good idea, but there's something stronger". This retry does not cost a stage, once per card.

**Multi-move lines:**

- Each of Sam's moves goes through the ladder from stage 2.
- The card's credit is the lowest credit earned on any of its moves.

### 17.3 Reflection questions by validated fact

| Validated fact / error | Stage 2 question | Stage 3 hint |
| --- | --- | --- |
| Validated threat / `ignored_threat` | "What is your opponent threatening?" | "Your opponent has a forcing move next. Find it, then stop it." |
| `hung_material` | "After your move, is every one of your pieces safe?" | "One of your pieces can be captured for free." |
| `allowed_tactic:<motif>` | "What changes for your opponent after your move?" | "Your move gives your opponent a tactic." |
| `missed_tactic:<motif>` | "What forcing moves do you have: checks, captures, threats?" | "There is a forcing move that wins material." / "…that leads to mate." |
| `missed_recapture` | "What did your opponent just capture?" | "You can win back the material immediately." |
| `missed_defense` | "If you do nothing, what happens?" | "Only one move holds the position." |
| `calculation_error` | "Follow your line two moves further: what does your opponent play?" | "Your idea fails to a reply later in the line." |
| `endgame_knowledge` | "Which side's king should be more active here?" (from detector tags) | Technique name, if detected ("This is a Lucena-type position.") |
| No validated fact | "What are all the checks and captures in this position?" | "Compare your two most forcing options." |

Questions use only validated facts. Wording comes from the concept level (§18.4).

### 17.4 Pre-move routines (decision habits)

- **Base routine,** shown as a short card at session start, with an optional prompt before each puzzle:
    1. What is my opponent threatening?
    2. What are the checks, captures and threats for both sides?
    3. Is my intended move safe?
    4. What changed after my opponent's last move?
- **Habit-specific routines** come from habit findings. For example, condition `piece_moved:queen ∧ allowed_tactic` gives the routine "Before any queen move, list your opponent's checks and forks." The matching Think First cards are drawn from those exact positions.
- **Optional practice:** in **training sparring only**, a routine can be practiced as a pause prompt when the targeted condition arises. This never applies to rated games.

### 17.5 Credit and recording

| Credit | Meaning |
| --- | --- |
| **Independent first try** | Correct at stage 1 on the first move |
| **Independent after reflection** | Correct at stage 2 with no hint |
| **Hinted** | Correct after stage 3 or 4 |
| **Revealed** | Reached stage 5, or capped by guesses |

Every attempt event records: stage reached, wrong moves (with SAN), time per move, guesses, which questions and hints were shown, "Show me why" use, and the credit earned.

### 17.6 Scheduling exercises (MVP mastery scheduler, hypothesis)

Each card has a mastery level from 0 to 5. Level intervals: 0 → this session; 1 → 1 day; 2 → 3 days; 3 → 7 days; 4 → 21 days; 5 → retired to transfer testing.

| Credit | Mastery change |
| --- | --- |
| Independent first try | +1 |
| Independent after reflection | +0 (easy card: +1) |
| Hinted | 0, retest in 1 day |
| Revealed | Set to 1, plus a related position queued |

FSRS for tactics is a Phase 9 A/B test against this scheduler.

**Failures feed selection:** Revealed and Hinted outcomes raise the weakness's exposure need, and they lower its expected success used in §15.2.

## 18. Explanations

### 18.1 Content

Every explanation answers five questions:

1. What was wrong with the move?
2. Why was it wrong (the engine-confirmed consequence)?
3. What should Sam have considered instead?
4. What general lesson applies?
5. How will he recognize this next time? The recognition cue comes from detector facts, for example "an undefended piece on the same line as your king".

### 18.2 Layers

| Layer | Content | Source |
| --- | --- | --- |
| **L1 Summary** (default) | 2–4 sentences covering the five questions | Template (MVP) or LLM (Phase 5) |
| **L2 Go deeper** (on request) | Alternative lines (MultiPV top 3 in SAN with plain-word evaluations); the tactical sequence step by step; the opponent's threats; positional considerations (detector tags, marked as interpretation); a relevant principle from the concept registry | Engine + detectors; LLM narration |
| **L3 Explore** | Step through any line on the board, with arrows | Engine lines |

Difficult positions (unique solution, calculation drills, F < 0.3) offer L2 by default.

### 18.3 Templates and LLM

**Templates (Phase 2)** cover `hung_material`, `missed_recapture`, simple `allowed_tactic` and `missed_tactic` (motif within 2 plies), `missed_mate` ≤ 3, `ignored_threat`, and `endgame_knowledge` (tablebase result plus technique name).

Example: "After 18…Qd7, Ne5 forks your king and rook. Play 18…Qe7 to cover e5 first. Lesson: before moving a defender, check what it was guarding. Next time: when a knight can reach a square attacking your king and a rook, cover that square."

**LLM explanations (Phase 5)**

- **When used:** two or more validated facts, L2 narration, plan notes, or cases no template covers. Called through the Claude API from the server; model ids in config; spending capped (D3).
- **Input:** a fact packet containing:
    - FEN.
    - The played move, best line and refutation (SAN, ≤ 6 plies each).
    - Validated facts with ids and ply positions.
    - The Win% swing.
    - Error, context and cognitive-need labels with their evidence.
    - F/T/band.
    - Sam's concept level.
- **Output:** structured claims.

```json
{
  "claims": [
    {"kind": "wrong|why|consider|lesson|cue|deeper",
     "category": "engine|detector|interpretation",
     "line": "refutation|best|before|alt1|alt2",
     "at_ply": 1, "fact_ids": ["f3"], "text": "..."}
  ],
  "concepts_used": ["fork"],
  "confidence": "normal|conservative"
}
```

### 18.4 Validator (consistency checks, not proof)

The validator checks that an explanation is *consistent* with the engine and detector evidence. **It does not prove causation.**

1. Every SAN sequence replays legally from the right FEN, with the right side to move, in order.
2. Every "piece on square" phrase matches the board at its ply.
3. Every claim cites facts that exist in its stated line.
4. *Consistency:* a "why" claim must cite a fact at or before the ply where that line's Win% first falls ≥ 10 from the root.
5. Tactic words (fork, pin, skewer, discovered, back rank, trapped, overload, mate, perpetual, stalemate, zugzwang) require a validated fact of that type.
6. Numbers match the packet: within ±0.05 for probabilities, exact for counts.
7. No claims about Sam's thoughts or intent. Context may be stated only as fact ("with 9 seconds left").
8. *Interpretation* claims must be phrased as advice or general principle, never as fact about this position.
9. Concepts above Sam's level must include a plain-language definition on first use.

**Conservative mode:** when there are fewer than 2 validated facts, facts from competing lines, a large `eval_delta`, or a rule-4 warning, the explainer must use conservative phrasing ("The engine shows that after 18…Qd7, Ne5 wins material.") and make no causal "because" claim.

**On failure:** retry once with the errors. If it fails again, fall back to the template, or plain engine facts if no template applies. Every failure is logged.

### 18.5 Adaptive vocabulary: concept registry

Concepts are grouped by level *(hypothesis)*:

| Level | Concepts |
| --- | --- |
| L1 | Check, capture, hanging piece, fork, pin, threat |
| L2 | Skewer, discovered attack, back rank, overload, trade-down, opposition |
| L3 | Intermezzo, outpost, IQP, minority attack, Lucena, Philidor |
| L4 | Prophylaxis, zugzwang, pawn-break timing, piece quality |

A concept unlocks when Sam's puzzle rating passes the level threshold, or when he masters a motif that uses it. On first use the text gives a one-line definition and a mini-example. Plain words stay the default.

### 18.6 Quality feedback

Two taps per explanation: "Accurate?" and "Will this help next game?". "Wrong" reports become regression tests.

## 19. Targeted sparring (core feature)

### 19.1 Opponent types

| Type | Purpose | Move policy |
| --- | --- | --- |
| **Human-like** | Realistic practice at a set strength | Sample from Maia at rating R_opp (temperature 1.0, top-p 0.95) |
| **Targeted training** (Phase 7) | More chances to practice a weakness, realistically | Maia candidates only, gently steered (§19.3) |
| **Test** | Measure improvement | Unsteered Maia at A + 200 to A + 400; no hints; results recorded, never trained on mid-game |

### 19.2 Basic sparring (Phase 4: server-based)

- **Moves:** the device sends each move to the server, and the server returns Maia's reply. Latency target ≤ 1 s. Online only.
- **Opponent:** human-like.
- **Strength:** R_opp = A + 100 *(tunable)*.
- **Curated starts**, chosen by Training Priority:

| Start type | Built from | Realism rule |
| --- | --- | --- |
| Pre-mistake | 2–4 plies before one of Sam's triaged mistakes | Real game position |
| Conversion | Sam's own positions at Win% 70–85 that he failed to convert | Sam is better, not trivially winning |
| Defense | Sam's own positions at Win% 15–35 | Engine confirms the position is holdable: best line keeps Win% ≥ 15 at deep pass |
| Structure | Positions from Sam's games in a weak structure (for example a Caro-Kann Advance chain) at ply 12–20 | Real game position |
| Endgame | Sam's endgames of a weak type | Tablebase or engine confirms the target result is achievable |

- **Clocks:** optional. The default is no clock for structure and endgame starts, and 5+3 for others.
- **After the game:** the full analysis pipeline runs on the sparring game. Its mistakes feed training, tagged `source = sparring` and kept separate from rated-game statistics.

### 19.3 Steered opponent (Phase 7)

The goal is more relevant situations without unrealistic moves.

**Candidate set:** moves with Maia probability ≥ 0.05 at R_opp **and** Win% for the bot within 5 points of Maia's most likely move *(tunable)*.

**Relevance score:** a shallow search plus detectors on each candidate's resulting position. Relevance is 1 if the position contains an opportunity of the targeted kind, offensive or defensive, for Sam within 2 plies.

**Selection:** probability ∝ p_maia × (1 + β·relevance), with β = 1.5 *(tunable)*.

**Hard rules:**

- Never pick a move outside the candidate set.
- Never deliberately blunder.
- Log every steered choice.
- A realism audit tracks the average Maia probability of chosen moves against unsteered play. Steering is disabled if the drop exceeds 25%.

### 19.4 Timed exercises

- **Clock drills:** sparring from a middlegame start with low time, for example 1+1 or 2+1.
- **Rapid-recognition cards:** mastered motif cards with a visible timer. Speed is a separate score; correctness credit is unchanged.
- **Time-budget mode:** a fixed seconds-per-move budget with a warning at 30%.

Used when the time-control gap analysis (§14) or a `time_pressure` habit finding supports it.

### 19.5 Later

On-device sparring (Phase 8). Sparring performance ratings (Phase 9, experimental).

## 20. Theme puzzles and the puzzle rating

### 20.1 Pack

- About 500 Lichess puzzles relevant to the active weaknesses, refreshed when online.
- Filtered to Popularity ≥ 80 and NbPlays ≥ 500.
- Completed puzzles and upcoming reviews are stored separately.

### 20.2 Puzzle rating (Glicko-2)

**Scale:** the same scale as Lichess puzzle ratings. Each **unseen first attempt** at a Lichess puzzle is treated as one Glicko-2 game against the puzzle, whose rating and RD are taken as fixed from the CSV. Lichess itself rates puzzles from solve attempts as Glicko-2 games ([database.lichess.org](https://database.lichess.org/)).

**Initial state:** rating 1500, RD 350, volatility 0.06, τ = 0.5. These are the standard Glicko-2 defaults *(tunable)*.

**Placement:** the first 12 rated attempts are spread from 1000 to 2000 to converge quickly. The app does not assume any relationship between chess.com game ratings and puzzle ratings.

**Update:** one rating period per attempt.

- Win = Independent first try, with the full line correct.
- Loss = anything else: a wrong first move, a hint, reflection, or a reveal.

Reflection is a loss for rating purposes, even though it earns credit in mastery, so the rating stays a clean measure of first-attempt skill.

**Not rated:** repeated puzzles, own-game puzzles, Think First cards, and timed-mode attempts. These are tracked in their own success rates.

**Difficulty selection** uses Glicko-2 expected score with g(RD) to place each puzzle in its mix band (§15.2):

| Band | Expected success |
| --- | --- |
| Reinforcement | ≥ 75% |
| Challenge | 55–75% |
| Stretch | 35–55% |

With low RD, an expected success of 55–75% corresponds to puzzles about 190 to 35 points *below* Sam's rating. This corrects v2, which mixed a 60–75% success target with puzzles rated above him.

**Own-game difficulty:** own-game puzzles carry estimated difficulty from F (Maia, Phase 4) and line length. Their observed success later calibrates that estimate (Phase 9).

## 21. Spaced repetition

| Content | Scheduler |
| --- | --- |
| Opening cards (moves and ideas) | FSRS (`ts-fsrs`), retention 0.90. Grades: wrong → Again; correct after > 2× median time → Hard; correct → Good. Easy is never automatic. Re-fit parameters after 1,000 reviews |
| Exercises | Mastery scheduler (§17.6) |
| Transfer tests | Unseen positions per motif, inserted at 25% of motif practice once 5 cards are mastered |

## 22. Sessions

### 22.1 Modes

| Mode | Length | Typical content |
| --- | --- | --- |
| Quick | 10 min | Due reviews, then the top weakness |
| Standard | 15 min | Openings ≥ 25%, guided exercises, transfer test |
| Extended | 30 min | Standard plus calculation drill and plan-note study |
| Deep training | 45–60 min | Extended plus one targeted sparring game and its review |
| Targeted sparring | Chosen time control | One curated start, plus a post-game review |

### 22.2 Recommendation

At open, the app estimates **useful minutes available**: due reviews, plus new material whose Training Priority is above a cutoff, plus scheduled transfer tests and pending deviation and proposal decisions. It recommends the nearest mode, for example: "Recommended today: 30 min — 22 reviews due, a new fork weakness, 1 sparring start ready." Sam chooses.

### 22.3 Allocation within a session

- Openings get at least 25% and at most 50% of the time, including Forgot cards.
- Remaining time goes in proportion to Training Priority.
- No single weakness gets more than 60%.
- Due reviews come before new material.
- On the first day, with no data yet, the split is openings 35% and exercises 65%.

### 22.4 Stopping

- When the selected time is reached, Sam finishes the current exercise and the session stops. A session is never automatically extended.
- If useful work remains, the app offers an optional continuation: "10 more useful minutes available: continue?"
- The summary shows what was trained, first-attempt rates, and what is next.

## 23. Offline and sync

### 23.1 Support levels

| Level | Activities |
| --- | --- |
| **Guaranteed offline** (once downloaded; Phase 6) | Today's planned exercises and opening cards, cached explanations, the repertoire browser |
| **Conditional offline** (Phase 8) | Sparring, after the on-device model downloads and passes its self-test |
| **Online only** | Game sync and analysis, reports, server sparring, uncached LLM explanations, puzzle pack refresh |

### 23.2 Storage

- IndexedDB and Cache Storage hold **temporary copies only**.
- The app requests persistent storage but never relies on it.
- After eviction, it recovers by re-downloading.

### 23.3 Append-only events

Every attempt, review, decision (deviation or proposal) and sparring move is an event. Fields:

- `event_id`: UUIDv7.
- `device_id`.
- `device_seq`: a per-device counter that never decreases.
- `session_id`.
- `local_ts`.
- `payload`.
- `card_version`.
- `app_version`.

**Sync handshake:** the device sends its clock and the server responds with its clock. The device stores `clock_offset` = server − device, recorded with each batch.

**Reconciliation** (deterministic and pure):

1. Dedupe events by `event_id`.
2. Order each device's events by `device_seq`.
3. Merge devices by corrected time (`local_ts` + that batch's `clock_offset`). Ties break by `device_id`, then `device_seq`.
4. Rebuild scheduler state by replaying the ordered events.

**Conflicts:**

- If two devices review the same card before syncing, both events are kept. The second counts as an early review under FSRS or mastery rules.
- Decisions (accept or reject) apply in reconciled order. If two conflict, the later one wins *as a decision*, and both remain in history.
- Events are never deleted or overwritten.

**Durability:** events sync after each card when online, and on app open. A badge shows the unsynced count. The UI states plainly that unsynced events can be lost if iOS evicts storage.

### 23.4 Notifications

Web Push is optional. Without it, Home shows session status and the report is in-app.

## 24. Data model (Postgres)

All tables have `created_at` and `updated_at`. Derived rows carry the relevant `*_version` fields.

| Table | Key columns |
| --- | --- |
| `players` | `id`, `chesscom_username`, `chesscom_player_id`, `primary_time_class`, `settings`, `concept_level`, `llm_budget_month` |
| `archives` | `player_id`, `yyyymm`, `etag`, `last_fetched`, `status`, `error` |
| `games` | `id`, `source` (chesscom or sparring), `chesscom_url` (unique when chess.com), `time_class`, `time_control`, `rated`, `played_at`, `color`, `my_rating`, `opp_rating`, `result`, `termination`, `eco`, `pgn`, `parse_status`, `analysis_status` |
| `positions` | `fen_norm` (primary key), `zobrist`, `phase`, `structure_tags` |
| `plies` | `game_id`, `ply`, `fen_norm_before`, `san`, `uci`, `clock_ms`, `time_spent_ms`, `mover_is_me` |
| `engine_evals` | `fen_norm`, `pass`, `engine_version`, `build_hash`, `nodes`, `settings`, `cpu_model`, `lines` (JSON) |
| `tb_results` | `fen_norm`, `wdl`, `dtz`, `source` |
| `move_scores` | `game_id`, `ply`, `win_best`, `win_played`, `win_loss`, `eval_delta`, `final_pass`, `class`, `labels`, `gri`, `F`, `T`, `unlock`, `unlock_uncertain`, `band`, `chess_error`, `context_tags`, `secondary_tags`, `need_label`, `need_evidence` |
| `maia_preds` | `fen_norm`, `model_version`, `rating`, `F`, `entropy`, `top_moves` |
| `anchors` | `time_class`, `week`, `model_choice`, `rating`, `ci_low`, `ci_high`, `ll_by_model` |
| `facts` | `id`, `game_id`, `ply`, `line`, `at_ply`, `type`, `level` (pattern or validated), `consequence_type`, `payload`, `detector_version` |
| `opportunities` | `game_id`, `ply`, `family`, `motif`, `side` (offense or defense), `reliability`, `converted` |
| `habit_findings` | `id`, `condition`, `time_class`, `errors`, `moves`, `rate_ratio`, `ci_low`, `ci_high`, `q_value`, `status`, `routine_id` |
| `gap_reports` | `week`, `comparisons` (JSON with intervals), `summary` |
| `weakness_snapshots` | `weakness_key`, `time_class`, `week`, `raw_cost`, `ci_low`, `ci_high`, `trainable_cost`, `occurrences`, `opportunities`, `rate`, `rate_ci`, `tentative`, `trend`, `tp`, `elo_est_experimental` |
| `exposures` | `weakness_key`, `date`, `minutes`, `cards`, `activity` |
| `cards` | `id`, `version`, `type`, `source_ref`, `weakness_key`, `motif`, `fen`, `solution`, `difficulty_est`, `unseen` |
| `events` | `event_id` (primary key), `device_id`, `device_seq`, `session_id`, `local_ts`, `clock_offset_ms`, `server_received_ts`, `kind`, `payload`, `card_version`, `app_version` |
| `card_state` | `card_id`, derived scheduler state, `due_at` (rebuildable) |
| `puzzle_rating` | `date`, `rating`, `rd`, `volatility`, `attempt_event_id` |
| `repertoire_nodes` | `fen_norm`, `color`, `status`, `plan_note_id` |
| `repertoire_edges` | `from_fen`, `to_fen`, `san`, `is_my_move`, `status` (active, proposed or rejected), `source` (user, history or engine), `opp_frequency` |
| `plan_notes` | `id`, `branch_root_fen`, `bullets`, `evidence`, `status` (proposed or approved) |
| `proposals` | `id`, `kind` (gap, fix or new line), `node`, `payload`, `evidence`, `status` |
| `deviations` | `game_id`, `ply`, `kind` (sam or opponent), `resolution` (unresolved, forgot, deliberate, accepted or rejected) |
| `explorer_cache` | `fen_norm`, `band`, `moves`, `fetched_at`, `source` |
| `puzzles_lichess` | `puzzle_id`, `fen`, `moves`, `rating`, `rd`, `themes`, `opening_tags` |
| `sparring_games` | `game_id`, `start_type`, `start_fen`, `opponent_type`, `r_opp`, `clock`, `weakness_key`, `steering_log` |
| `explanations` | `cache_key`, `layer`, `packet`, `output`, `source`, `valid`, `mode` (normal or conservative), `validator_errors`, `model`, `prompt_version` |
| `concepts` | `id`, `level`, `definition`, `example_fen` |
| `concept_exposures` | `concept_id`, `first_shown`, `count` |
| `feedback` | `explanation_key`, `accurate`, `useful`, `note`, `status` |
| `ratings_history` | `time_class`, `date`, `rating`, `smoothed` |
| `jobs` | `id`, `kind`, `key` (unique), `status`, `attempts`, `last_error`, `versions`, `run_after`, `lease_until` |
| `llm_usage` | `month`, `tokens_in`, `tokens_out`, `cost_est` |

## 25. Jobs, failure recovery and degradation

**Idempotency:** every job has a natural key, such as `analyze:{game}:{engine_version}`. The queue uses `SELECT … FOR UPDATE SKIP LOCKED` with leases. Enqueuing a duplicate key does nothing.

| Failure | Behavior |
| --- | --- |
| Worker crash or DB restart | Lease expires after 10 min; the job is retried |
| Engine or Maia error | Restart the process and retry; after 3 attempts the job is `failed` with its error |
| Corrupt PGN | Stored with the error; skipped |
| Partial import | Archive marked `partial`; resumed next cycle |
| Sparring server error | Client shows "Opponent unavailable". The game is saved; Sam can resume or abort |
| LLM error or budget reached | Template fallback |
| Version change | Re-derive only the affected rows |

**Degradation:**

- Maia unavailable → simplicity proxy; sparring paused.
- Detector uncertain → no motif.
- Anchor unstable → previous anchor.
- Theory reference unavailable → no "left theory" claims.
- Server unreachable → downloaded drills only.

## 26. UI, accessibility and fair play

### 26.1 Navigation

Bottom tabs: Home, Train, Spar, Games, More (Weaknesses, Repertoire, Progress, Settings). iPad landscape uses two panes.

### 26.2 Screens

| Screen | Contents |
| --- | --- |
| Home | Recommended session with mode buttons; unsynced badge; smoothed rapid rating with ladder; #1 weakness in plain words; inbox count (deviations and proposals); latest game's top moment |
| Session runner | Board, prompt, the feedback ladder UI (reflection question card, hint chips, "Show me why", "Show solution"), credit result, explanation sheet (L1 with "Go deeper") |
| Spar | Start type picker (recommended first), opponent type and rating, clock; post-game review |
| Games / Review | GRI moments (largest swing always first), Win% graph, move classes, explanation layers, "Human view" (Phase 4+) |
| Weaknesses | Top 3 plus all; raw cost, rates with n and intervals, need labels with evidence, habit findings, time-control gap report |
| Repertoire | DAG browser, plan notes, card stats, branch results, inbox, PGN import |
| Progress (basic, MVP) | Ratings by time class (smoothed), sessions per week, first-attempt and transfer success by motif, weakness rates over time. Experimental metrics in a labeled section |
| Settings | Username, primary time class, default session mode, LLM budget, resync, data export, theme |

### 26.3 Accessibility

- `chessground` board with tap-tap and drag, large targets, and a promotion picker.
- Coordinates on by default; adjustable orientation; high-contrast piece set.
- Move classes use color plus a symbol.
- Screen-reader labels; reduced motion; safe-area insets.

### 26.4 Fair play

Coach is designed for **post-game study and independent training**. It provides no assistance during active rated games.

- Analysis covers only games the chess.com archive returns as finished **[Verify]**.
- The board opens only from imported finished games, repertoire nodes, exercises and sparring.
- No arbitrary FEN or PGN input in v2.1.
- A short notice in Settings and on first run states that using Coach during a rated game breaks chess.com's fair-play rules.

These measures reduce misuse. **They do not guarantee compliance;** responsibility stays with the user.

## 27. Build phases

Each phase lists scope, dependencies, deliverables, objective exit gates, subjective checks, and what Sam can use.

### Phase P — Artifact prototype (test first, free)

- **Why:** test the core coaching loop on Sam's own games before any server exists. Hosting is free (claude.ai artifact).
- **Form:** one self-contained HTML artifact. Scripts only from approved CDNs (cdnjs, jsdelivr, unpkg).
- **Scope:**
    - **Import.** Fetch Sam's most recent 20–30 rapid games directly from the chess.com API. **[Verify] first:** the artifact sandbox may block external fetches. If it does, fall back to PGN export: chess.com lets Sam download his games as PGN, which he pastes or uploads into the artifact.
    - **Analysis.** Run single-threaded Stockfish WASM in a Web Worker at a low budget (depth 12–14 *(tunable)*). Compute Win%, classes, the largest swing, and the basic error rules that need no Maia (§10: hung material, missed recapture, missed mate, simple tactics via a shallow detector subset).
    - **Training.** Own-game puzzles with the full feedback ladder (§17.2–17.5) and Think First threat checks.
    - **Reporting.** A simple weakness summary: raw cost and counts.
    - **Storage.** Results and progress kept in artifact storage (the database capability if available, otherwise browser storage with export).
- **Not in P:** Maia, sparring, LLM explanations (template text only), FSRS repertoire, cross-device sync.
- **Exit:**
    - Works on the latest iPhone and on the iPad Pro.
    - 20 games analyzed in ≤ 10 min on the iPad Pro.
    - Sam completes 5 ladder sessions and judges whether the loop is useful.
- **Findings feed Phase 0:** ladder tuning, detector false positives, and whether the session flow works.

### Phase 0 — Feasibility and verification (2–3 days)

- **Depends on:** nothing.
- **Scope:** benchmarks and verification only.
- **Deliverables:**
    - A spike report.
    - Pinned versions with checksums.
    - A `LICENSES.md` draft.
    - A completed fact register.
    - A fallback decision for every missed threshold.
    - Game counts by time class (via the existing chess.com connection) to confirm rapid as primary.
- **Go thresholds** *(set before testing)*:

| Check | Go |
| --- | --- |
| Engine pipeline (all passes + detectors) | ≤ 60 s per average game |
| Engine accuracy vs 50M-node reference (500 positions) | Class agreement ≥ 90% after the boundary pass |
| Maia3-23M throughput | ≤ 30 s per game for analysis scope; else use 5M |
| Server Maia move latency (sparring) | ≤ 1 s p95 |
| Full-history backfill | ≤ 72 h |
| Hosting cost | $0 on the free stack (§29), or an explicit decision by Sam to pay |
| PWA | Installs; 50 MB IndexedDB writable on Sam's oldest device |
| Opening reference | Explorer API usable, **or** the fallback build is feasible within 10 GB and 24 h |
| Tablebase | 5-piece Syzygy local, or the API, works |

- **User-visible:** none.

### Phase 1 — Import, analysis, game review

- **Depends on:** Phase 0.
- **Scope:** §7, §8 (except Maia), tablebase, GRI, PWA shell, login.
- **Deliverables:** recent-first import plus backfill; engine passes with uncertainty fields; game review with the largest-swing rule.
- **Exit (objective):**
    - Import fixtures pass.
    - Formula golden fixtures pass (Win% exact; game accuracy within 0.5 of `lila`).
    - Canonical-key tests pass (transpositions, legal en passant only, counters ignored).
    - Determinism test passes.
- **User-visible:** game list and review on the phone.

### Phase 2 — Guided training loop

- **Depends on:** Phase 1.
- **Scope:** §9–10 detectors and classification (proxy findability); §17 exercises (own-game, Think First, calculation and technique drills); the feedback ladder; mastery scheduler; templates (§18.3); events (§23.3, online); basic progress view.
- **Exit (objective):**
    - 100% of exercise lines legal and correctly oriented.
    - Detector set (§28) at validated precision ≥ 95% and recall ≥ 70%.
    - Feedback ladder state-machine tests pass (stage limits, guess capping, near-miss handling, no loops).
    - Event dedupe tests pass.
- **Exit (subjective):** Sam completes 5 sessions and finds the ladder fair.
- **User-visible:** daily guided training from his own games.

### Phase 3 — Diagnosis and measurement

- **Depends on:** Phase 2.
- **Scope:**
    - Weaknesses, costs, bootstrap and Tier A opportunities.
    - Habit findings and the time-control gap report.
    - Weekly report.
    - Prescription with fixed weights, the difficulty mix, diversity rules, and session modes with recommendation and stopping.
    - Theme puzzles with Glicko-2, and transfer tests.
- **Exit (objective):**
    - Scoring is deterministic with a fixed seed.
    - The Glicko-2 implementation matches a reference implementation on test vectors.
    - Wilson and bootstrap tests pass.
    - Benjamini–Hochberg correction is verified.
    - The session never exceeds the selected time beyond the active exercise.
- **Exit (subjective):** Sam finds the weekly report and gap report fair.
- **User-visible:** weaknesses, habits, gap report, adaptive sessions.

### Phase 4 — Maia and basic sparring

- **Depends on:** Phase 3.
- **Scope:**
    - Server Maia with anchor selection, F/T/unlock/bands, and Tier B opportunities.
    - Human view.
    - Training Priority with F.
    - Server-based human-like sparring from curated starts, with post-game analysis feeding training.
- **Exit (objective):**
    - Anchor model comparison documented.
    - F computed from full distributions (test).
    - Sparring latency ≤ 1 s p95.
    - Defense starts are holdable by deep pass (100%).
    - Sparring games enter the pipeline tagged as sparring.
- **Exit (subjective):** a one-week comparison of F-based and proxy-based ranking, reviewed by Sam.
- **User-visible:** sparring tab; Human view.

### Phase 5 — Adaptive LLM explanations

- **Depends on:** Phase 3 (Phase 4 for F in packets).
- **Scope:** fact packets, structured claims, validator with conservative mode, layers L1–L3, concept registry, plan-note generation (for Phase 6), budget cap.
- **Exit (objective):** 300-packet validator suite (including adversarial cases: tactic appearing only after a later error, wrong numbers, mind-reading phrasing, unlevelled jargon) shows 0 invalid outputs.
- **Exit (subjective):** "Accurate?" ≥ 98% yes and "Will this help?" ≥ 70% yes over 50 explanations.
- **User-visible:** richer explanations and "Go deeper".

### Phase 6 — Opening repertoire and offline drills (MVP complete)

- **Depends on:** Phases 4–5.
- **Scope:** §16 in full; FSRS opening cards; guaranteed-offline drills and full sync reconciliation.
- **Exit (objective):**
    - Transposition merging verified.
    - Deviation detection correct on fixture games; unanswered deviations stay unresolved.
    - Repertoire moves that are mistakes are flagged.
    - Sync tests pass: two-device offline conflicts, clock skew of ±10 min, kill mid-session, eviction recovery. No synced event is lost or duplicated, and state rebuilds identically.
- **Exit (subjective):** Sam approves his starting repertoire and plan notes.
- **User-visible:** repertoire builder, inbox, offline sessions.

### Phase 7 — Advanced sparring

- **Depends on:** Phase 6.
- **Scope:** steered opponent with the realism audit, test opponents, timed drills and time-budget mode, structure starts from the reference database, routine pause prompts.
- **Exit (objective):**
    - 100% of steered moves inside the candidate set.
    - Realism audit within limits.
    - Test-opponent games are never used for training mid-game.
- **User-visible:** targeted and test opponents; timed drills.

### Phase 8 — On-device inference and offline sparring

- **Depends on:** Phase 7.
- **Scope:** Maia3-5M via `onnxruntime-web` or `maia3-web`, and Stockfish lite WASM, both in Web Workers; conditional offline sparring.
- **Exit (objective):**
    - Parity vs upstream on 500 positions × 3 ratings: top-1 ≥ 97%, mean |ΔF| ≤ 0.02, KL divergence and max absolute probability error reported.
    - On Sam's oldest device: ≤ 300 ms per move, memory within budget, a 15-minute battery check, and recovery after suspension.
- **User-visible:** offline sparring.

### Phase 9 — Calibration and experiments

- **Depends on:** Phase 6+ with ≥ 8 weeks of data.
- **Scope:**
    - Responsiveness learning: a statistical model of exposure against later per-opportunity rates (for example hierarchical regression comparing trained and untrained weaknesses), proposed to Sam before use.
    - Elo-forecast validation.
    - Sparring performance ratings.
    - FSRS-for-tactics A/B test.
    - Own-game difficulty calibration.
    - Advanced progress analytics.
- **Exit:** each experiment either produces a documented validation result or stays hidden.

**Standing rules:**

- Configuration in `coach.toml`.
- Tests before formula code.
- `CLAUDE.md` kept current.
- Idempotent jobs.
- Test on a physical iPhone each phase.
- No **[Verify]** dependency enters code unverified.

## 28. Testing summary

### Objective gates

**Import and formulas:** import fixtures; formula golden fixtures; canonical keys; determinism.

**Engine:** class agreement against the reference set.

**Detectors:** a hand-verified set of 400 positions containing:

- Positives.
- Hard negatives.
- Multi-motif positions.
- Irrelevant motifs.
- Motifs that vanish on calculation.
- Defensive resources.
- Forced draws.

Lichess tags are used only to find candidates.

**Exercises and statistics:**

- Exercise legality and orientation.
- Feedback-ladder state machine.
- Glicko-2 test vectors.
- Statistical routines (bootstrap, Wilson, Benjamini–Hochberg).

**Sync and LLM:**

- Sync and clock-skew reconciliation.
- Validator suite.

**Sparring:**

- Sparring latency.
- Defense-start holdability.
- Steering candidate-set compliance.

**Devices:**

- Maia parity (Phase 8).
- Physical-device tests: install, offline, memory, battery, suspension.
- Playwright WebKit end-to-end tests at iPhone and iPad viewports. These do not replace the physical tests.

### Subjective checks (Sam)

- Key-moment agreement ≥ 80%.
- Explanation accuracy ≥ 98% and usefulness ≥ 70%.
- The feedback ladder feels fair, not frustrating.
- The reports are fair.

## 29. Tech stack, deployment, licenses, privacy

### Stack

**Frontend:** React, TypeScript, Vite, `vite-plugin-pwa`, `chessground`, `chess.js`, `ts-fsrs`, Dexie. From Phase 8 only: `onnxruntime-web` and Stockfish lite WASM.

**Backend:**

- Python 3.12, FastAPI, `python-chess`.
- Native Stockfish 18.
- `maia3`, pinned.
- Syzygy 5-piece tablebases, or the API.
- Postgres 16 with the job queue.
- APScheduler.
- The Claude API from Phase 5.

**Contracts:** JSON Schema in `/shared`, generating TypeScript types and Pydantic models.

**Repo:** `/web`, `/server`, `/shared`, `docker-compose.yml`, `CLAUDE.md`, `LICENSES.md`.

### Hosting (free, no domain)

| Stage | Hosting | Address |
| --- | --- | --- |
| Phase P | claude.ai artifact | Artifact link |
| Phases 1+ (frontend) | Free static host for the PWA, such as Cloudflare Pages **[Verify] free-tier terms** | Free `*.pages.dev` subdomain, HTTPS included |
| Phases 1+ (backend) | A free-tier cloud VM, such as Oracle Cloud Always Free Arm instances **[Verify] current limits and Arm builds of Stockfish and Maia** | Same subdomain via an API route, or the VM's provider hostname |

**Backend VM layout:** Docker Compose with Caddy, api, workers and Postgres. Encrypted nightly backups to free object storage, kept 30 days.

**If no free VM fits Phase 0 thresholds:** Phase 0 reports the gap. Options are a paid VPS (Sam decides), or running workers on a home computer that pushes results to the server.

**Free-tier risks:** idle reclamation, capacity limits, terms changes. Backups and infrastructure-as-code keep a move to another host to under 1 hour of work.

### Licenses

`LICENSES.md` records every dependency, model, weight file and browser bundle, with its license and whether it runs only on the server or ships to the browser.

- Browser-shipped GPL and AGPL code is distribution, even to one user: `chessground`, the Stockfish WASM, and (from Phase 8) Maia weights.
- Server-side AGPL Maia is a network service.
- Review the obligations for this exact architecture before deployment.
- **Engineering default:** keep the source available to every user of the app under compatible terms. This is not legal advice.

### Privacy

- Single-user login with an argon2id-hashed password.
- Secrets live in environment variables.
- The Claude API receives chess fact packets only.
- Access logs are kept 30 days.
- Full export (JSON plus PGN) and a "delete all data" command.
- Device ids are random per install.

## 30. Configuration (`coach.toml`)

| Key | Default | Label |
| --- | --- | --- |
| `sync.poll_minutes` | 30 | tunable |
| `import.initial_games_per_class` | 100 | tunable |
| `engine.first_nodes` / `deep_nodes` / `boundary_nodes` | 1M / 5M / 20M | set after Phase 0 |
| `engine.boundary_margin` | 2 Win% pts | tunable |
| `classes.inaccuracy` / `mistake` / `blunder` | 5 / 10 / 15 | tunable |
| `labels.unique_gap` / `acceptable` | 10 / 5 | tunable |
| `detectors.*` (horizons, thresholds) | per §9.1 table | tunable |
| `context.time_pressure_pct` / `_s` / `fast_s` / `slow_mult` | 10% / 15 / 3 / 3× | tunable |
| `gri.motif_mult` | 1.2 | tunable |
| `proxy.simple` / `other` | 1.0 / 0.6 | hypothesis |
| `window.games` / `max_days` / `min_games` | 100 / 180 / 30 | tunable |
| `tentative.min_occ` / `min_games` | 8 / 5 | tunable |
| `bootstrap.n` / `ci` | 1000 / 0.90 | fixed |
| `habits.min_errors` / `min_ratio` / `fdr_q` | 10 / 1.5 / 0.10 | tunable |
| `maia.server_model` / `sparring_offset` | 23M / +100 | set after Phase 0 / hypothesis |
| `anchor.min_ll_gain` / `weekly_cap` / `floor` | 1% / 50 / −100 | tunable |
| `bands.should_find` / `stretch` | 0.5 / 0.2 | tunable |
| `responsiveness.*` | §15.1 table | hypothesis |
| `mix.reinforce` / `challenge` / `stretch` | 0.30 / 0.50 / 0.20 | hypothesis |
| `mix.success_bands` | ≥ 0.75 / 0.55–0.75 / 0.35–0.55 | hypothesis |
| `ratchet.window` / `success` / `min_unseen` | 30 / 0.80 / 10 | hypothesis |
| `ladder.attempts` | §17.2 table | hypothesis |
| `ladder.max_wrong` / `guess_s` / `guess_cap` | 5 / 2 / 2 | hypothesis |
| `ladder.near_miss` / `good_idea` | 3 / 3–10 | tunable |
| `mastery.intervals_days` | [0, 1, 3, 7, 21] | hypothesis |
| `glicko.r0` / `rd0` / `vol0` / `tau` | 1500 / 350 / 0.06 / 0.5 | tunable |
| `glicko.placement_count` / `range` | 12 / 1000–2000 | tunable |
| `puzzles.pack_size` / `min_pop` / `min_plays` | 500 / 80 / 500 | tunable |
| `fsrs.retention` | 0.90 | tunable |
| `repertoire.start_depth` / `extend_by` / `extend_reach` | 6–8 / 2 / 30% | hypothesis |
| `theory.min_games` / `band_offset` | 50 / +200 | tunable |
| `session.modes_min` | 10 / 15 / 30 / 45–60 | Sam |
| `session.opening_min` / `max` / `max_weakness` | 0.25 / 0.50 / 0.60 | hypothesis |
| `steer.min_p` / `max_win_gap` / `beta` / `realism_drop_max` | 0.05 / 5 / 1.5 / 25% | hypothesis |
| `rating.half_life_days` / `sustain_days` / `ladder_step` | 14 / 14 / 50 | tunable |
| `llm.budget_usd_month` / `warn_usd` | 15 / 10 | Sam (D3) |

## 31. Sources

- [Chess.com Published-Data API](https://chess.com/news/view/published-data-api)
- [Unofficial chess.com TypeScript SDK](https://github.com/denispianelli/chesscom) (secondary)
- [Lichess accuracy and Win%](https://www.lichess.org/page/accuracy)
- [Lichess open database: puzzles, evaluations, openings](https://database.lichess.org/)
- [CSSLab/maia3](https://github.com/CSSLab/maia3/wiki)
- [CSSLab/maia2](https://github.com/CSSLab/maia2)
- [maia3-web](https://github.com/GeoffreyPlitt/maia3-web)
- [chessoracle-maia](https://github.com/BastiQ/chessoracle-maia)
- [OpenChessCoach Maia-3 ONNX release](https://github.com/inprealpha/OpenChessCoach/releases/tag/maia3-5m-v1)
- [Maia platform frontend](https://github.com/csslab/maia-platform-frontend)
- [lichess-org/stockfish.wasm](https://github.com/lichess-org/stockfish.wasm)
- [Stockfish 18 WASM build notes](https://huggingface.co/cstr/stockfish-js-wasm) (secondary)
- [ts-fsrs](https://open-spaced-repetition.github.io/ts-fsrs)
- [Building a Chess Coach — AI Engineer Europe 2026](https://ai.engineer/talks/FlzpEGHNVKQ-building-chess-coach)
- [Chessigma: chess AI tools 2026](https://www.chessigma.com/blog/best-chess-ai-tools) (secondary)
- To verify before citing in the product: Glickman's Glicko-2 paper (reference test vectors); Benjamini & Hochberg 1995; Cepeda et al. 2006; Roediger & Karpicke 2006; Ericsson et al. 1993

---

# Appendices

## A. Change log from v2

1. **Sparring is now core.** Basic server-based, human-like sparring from curated starts moves to Phase 4. Steered and test opponents follow in Phase 7, and on-device inference in Phase 8. Three opponent types are defined, with realism rules.
2. **Guided correction.** A six-stage feedback ladder with adaptive attempt budgets, reflection questions tied to validated facts, "Show me why", anti-guessing, near-miss handling, credit levels and reinforcement.
3. **Two rankings.** Game Review Importance (objective) and Training Priority (findability, recurrence, responsiveness, cost). The largest swing is always shown.
4. **Engine evaluation clarified.** The first pass and the played-move pass are separate searches. The deep pass compares best and played within one MultiPV `searchmoves` search. Boundary rechecks run at 20M nodes. Accuracy is benchmarked against a 50M reference, and uncertainty is stored per move.
5. **Responsiveness learning deferred.** Fixed weights; exposure is logged; statistical learning moves to Phase 9.
6. **Puzzle rating specified.** Glicko-2 on the Lichess puzzle scale, unseen first attempts only, any help counts as a loss, placement attempts, expected-score difficulty bands. This corrects v2's offset contradiction.
7. **Detector validation** moves to motif-specific consequence types (material, mate, forced draw, evaluation swing, successful defense), with horizons and strict rules.
8. **Opportunities** split into offensive and defensive with reliability tiers. Rates come with n and Wilson intervals; there is no rate where no reliable denominator exists.
9. **Canonical position identity** defined: legal en passant only, counters excluded, Zobrist index plus string equality.
10. **Explanation validation** is now a consistency check with a conservative mode. Explanations have five content questions and layers L1–L3, plus a concept registry for adaptive vocabulary.
11. **Offline sync:** device sequence numbers, clock-offset correction, and a deterministic, pure reconciliation; decisions are events too.
12. **New diagnostics:** evidence-gated cognitive-need labels (knowledge, pattern, calculation, habit); habit findings with false-discovery-rate control and linked pre-move routines; the rapid-vs-blitz time-control gap analysis.
13. **Openings:** history analysis, theory reference (explorer or fallback), practical recommendations ranked on soundness, score, understandability and fit, approved plan notes, idea cards, adaptive depth. Unanswered deviations stay unresolved. Repertoire mistakes are never suppressed.
14. **Sessions:** Quick, Standard, Extended, Deep and Sparring modes, a recommendation based on useful work, and strict stopping with an optional continuation.
15. **Tablebases** added for endgame truth and knowledge labels. `calculation_error`, `endgame_knowledge` and the forced-draw consequence are added.
16. **Fair-play wording** corrected: the measures reduce misuse; they don't guarantee compliance.
17. **Contradictions fixed:** the basic progress view is in the MVP (Phase 2); responsiveness learning is in Phase 9; the session cap is now an explicit stop rule.
18. **Priority tiers** (essential, high, later) added, and the phase plan reordered to match.

### Points where this spec departs from the second review or Sam's notes

- **Deep pass:** instead of only documenting the noise between separate searches, v2.1 also moves the final comparison into one search. This fixes the problem rather than just disclosing it.
- **Sparring phase:** basic sparring is placed at Phase 4, not earlier, because it needs server Maia and the curated starts depend on diagnosis (Phase 3). An earlier sparring opponent would be untargeted, which Sam explicitly does not want.
- **Cognitive-need labels:** Sam asked to distinguish knowledge, pattern, calculation and habit "when evidence supports it". The spec implements this, but the available evidence supports these labels only for a subset of errors. Many will be `undetermined`, which is the honest outcome.

## B. Remaining Phase 0 verification tasks

1. Use Claude Code's chess.com connection to get game counts by time class (last 90 days and all time) and confirm rapid as primary.
2. Confirm User-Agent behavior, whether archives return only finished games, and whether past archives change (re-fetch 3 old months and compare ETags).
3. Confirm `lila` move accuracy, game accuracy and mate handling; build golden fixtures.
4. Confirm the Stockfish 18 release, UCI `searchmoves` with MultiPV behavior, and determinism with Threads 1 and a cleared hash.
5. Run the engine benchmark: 500 positions against a 50M-node reference; class agreement; boundary-recheck rate; seconds per game.
6. Confirm the Maia-3 Python API, rating-conditioning inputs, full-distribution output, throughput (23M vs 5M) and p95 sparring latency.
7. Confirm Maia-3 code and weight licenses; draft `LICENSES.md` for all dependencies.
8. Confirm the Lichess puzzle CSV fields and license; build a 500-puzzle pack.
9. Confirm Lichess opening explorer API access, authentication and rate limits, or size the fallback reference build.
10. Decide between Syzygy 5-piece local and the tablebase API; measure disk and latency.
11. Confirm `python-chess` SEE availability and the legal-en-passant FEN option.
12. Choose a Glicko-2 reference implementation and test vectors.
13. Confirm the PWA install, IndexedDB quota and Web Push on Sam's devices.
14. Price the VPS and confirm sizing, including tablebases and the opening reference.

## C. Recommended MVP boundary

**MVP = Phases 0–6:** accurate game analysis and review; recurring weaknesses with measured rates; habit findings; the time-control gap report; guided-correction training from Sam's games, including Think First, calculation and technique drills; template and LLM adaptive explanations; theme puzzles with Glicko-2; transfer tests; adaptive sessions in all modes; Maia findability; **basic server-based targeted sparring from curated starts**; opening repertoire builder with recommendations, plan notes and FSRS; offline drills; a basic progress view.

**After the MVP:** steered and test opponents, timed sparring drills, on-device inference with offline sparring, responsiveness learning, Elo forecasts, sparring ratings, the FSRS-for-tactics A/B test, and advanced analytics.

## D. Revised implementation sequence

| Phase | Theme | User gets |
| --- | --- | --- |
| P | Artifact prototype (free, client-side) | Analysis of recent games plus guided own-game puzzles, to test the loop |
| 0 | Feasibility and verification | — |
| 1 | Import, engine analysis, game review | Game review on the phone |
| 2 | Detectors, classification, guided training loop, templates, basic progress | Daily guided training from his own games |
| 3 | Diagnosis, measurement, habits, gap report, prescription, sessions, theme puzzles | Weakness reports and adaptive sessions |
| 4 | Maia findability; server sparring from curated starts | Targeted human-like sparring |
| 5 | Adaptive LLM explanations and concept registry | Deeper, level-appropriate explanations |
| 6 | Opening repertoire builder and offline drills | Personal repertoire; offline training (**MVP complete**) |
| 7 | Steered and test opponents; timed drills | Smarter sparring; improvement tests |
| 8 | On-device inference | Offline sparring |
| 9 | Calibration and experiments | Validated advanced metrics |

## E. Risks most likely to undermine educational value

1. **Shallow or wrong cause labels.** If detectors over-claim, the coaching teaches the wrong lesson. Mitigations: validated-only facts, the hand-verified detector set, `undetermined` and `unclassified` as honest defaults, and conservative explanations.
2. **Puzzle skill that does not transfer.** Sam might get better at these exercises without changing in-game behavior. Mitigations: unseen-position transfer tests, per-opportunity real-game rates, and habit routines that target in-game conditions.
3. **A feedback ladder that frustrates or leaks answers.** Too many questions annoy; hints that are too strong teach nothing. Mitigations: adaptive budgets, hard limits, Show solution always available, and Sam's fairness check in Phase 2.
4. **Unrealistic sparring.** A steered opponent that plays oddly teaches false lessons. Mitigations: Maia-only candidate sets, a Win% gap cap, a realism audit with automatic disabling, and real-game starting positions.
5. **Noisy measurement read as progress.** Small samples and shifting opponent pools can fake improvement. Mitigations: game-level bootstrap, Wilson intervals, tentative flags, the trusted/experimental split, and no Elo forecasts.
6. **Memorized openings without understanding.** Mitigations: idea cards, plan notes approved by Sam, practical move selection, and depth that grows only with mastery and real-game reach.
