# Chess Coach — Phase 0 report

Date: 2026-10-29 · Spec: `docs/chess-coach-spec-v2.1.md` · Scope: §27 Phase 0 and Appendix B only.
Machine for all measurements unless stated: cloud container, Intel Xeon @ 2.10 GHz (AVX-512, BMI2),
4 vCPU, 15 GB RAM, Linux x86-64. Raw outputs: `server/phase0/out/` (when present).

> **Status of this report: PARTIAL.** This session's network policy blocks `api.chess.com`,
> `huggingface.co`, `database.lichess.org`, `explorer.lichess.org`, `tablebase.lichess.org`,
> `tests.stockfishchess.org`, `docs.oracle.com` and `glicko.net`. Every item that depends on them is marked
> **BLOCKED** below, with what is needed to finish it. Nothing below is estimated or mocked unless it says so.

---

## 1. Conflicts found between your instructions and the spec

| # | Conflict | Resolution |
| --- | --- | --- |
| C1 | You asked me to use "your existing chess.com connection" (spec §6, Appendix B1). There is no chess.com connector in this session, and `api.chess.com` is blocked by the network policy | Use the public API (spec §7.1) once the host is allowed. Spec §6/B1 should drop "existing connection" (proposed edit E1) |
| C2 | Spec §27 orders **Phase P (artifact prototype) before Phase 0** ("test first"; "findings feed Phase 0"). You asked for Phase 0 only | Followed your instruction. Phase P's findings (ladder tuning, detector false positives) are therefore not available to this report. Proposed edit E2 |
| C3 | You asked for Phase 0 tasks, which include "SHA-256 for … the puzzle data". The puzzle CSV host is blocked | BLOCKED (§5) |
| C4 | Spec §29 puts `/web`, `/server`, `/shared` at a repo root; this session only had `family-playbook` | You chose a new repo `turners1110/chess-coach`. It does not exist yet, so the work is committed in a local repo and will be pushed once you create it |

## 2. Fact register (spec §6), every [Verify] resolved

Legend: **Confirmed** (spec right), **Corrected** (spec wrong or outdated: see edit), **Unavailable** (could not be
checked in Phase 0; code must not depend on it yet).

| Fact | Spec status | Phase 0 result | Source / experiment |
| --- | --- | --- | --- |
| chess.com Published-Data API: read-only JSON, monthly archives; serial unlimited, parallel may 429 | Verified | Unchanged (not re-tested: host blocked) | spec §31 |
| Archive API returns only finished games | [Verify] | **Unavailable — BLOCKED** (`api.chess.com`) | Test: fetch the current month during a live game, check it is absent |
| chess.com requires a descriptive User-Agent | [Verify] | **Unavailable — BLOCKED**. No chess.com connector exists in this session (C1) | Test: request with and without UA, compare status |
| Past monthly archives never change | [Verify] | **Unavailable — BLOCKED** | Test: re-fetch 3 old months, compare ETag and body hash |
| Lichess Win% = 50 + 50·(2/(1+e^(−0.00368208·cp)) − 1) | Verified | **Confirmed**, with a **correction to §8.3**: Lichess clamps cp to **±1000**, not ±1500 | `scalachess` `core/src/main/scala/eval.scala` @ `a4988192` (`Cp.CEILING = 1000`, `MULTIPLIER = -0.00368208`) |
| Lichess move accuracy, game accuracy, mate handling | [Verify] | **Corrected.** Move accuracy = `103.1668100711649·e^(−0.04354415386753951·Δ) − 3.166924740191411 + 1`, clamped 0–100 (100 if Win% did not drop). Game accuracy = mean of (volatility-weighted mean, harmonic mean); window = clamp((n−1)/10, 2, 8); weights = population std-dev of Win% in the window, clamped 0.5–12; harmonic mean floors each value at 1. **Mate = Win% of ±1000 cp ≈ 97.53 / 2.47, not 100 / 0** (spec §8.3 says 100/0; spec also says "if it differs, match lila"). Game accuracy uses `forceAsCp` (mate → ±Int.MaxValue, then ceiled to ±1000). The initial position is scored cp +15 (`legacyInitial`) | `lila` `modules/analyse/src/main/AccuracyPercent.scala`, `modules/tree/src/main/eval.scala` @ `898ad2cd`; `scalalib` `Maths.scala` @ `31fc151b`. Python port `server/phase0/lila_accuracy.py` passes all 18 upstream cases from `AccuracyPercentTest.scala` (`server/tests/test_lila_accuracy.py`) |
| Stockfish 18 release and UCI options (`searchmoves`, MultiPV) | [Verify] | **Confirmed**, with a note: Stockfish 18 = tag `sf_18`, released 2026-01-31. `go nodes N searchmoves a b c d` with MultiPV 4 returns exactly those 4 moves as 4 PVs, ranked, from one search. **Stockfish 19 was released 2026-09-05** (tag `sf_19`); see edit E3 | `official-stockfish/Stockfish` tags; [Stockfish 18 blog](https://stockfishchess.org/blog/2026/stockfish-18/); [Stockfish 19 blog](https://stockfishchess.org/blog/2026/stockfish-19/); experiment `uci_check.sh` |
| Stockfish determinism with Threads 1 and cleared hash | (B4) | **Confirmed**: two runs (`ucinewgame`, Threads 1, Hash 256, `go nodes 1000000`, MultiPV 4) gave identical scores, PVs and node counts. The node limit overshoots slightly (1,000,064 searched) and repeats identically | experiment |
| Maia-3 sizes 3M/5M/23M/79M; UCI code; Elo conditioning | Verified (repo); Python API and conditioning [Verify] | **Confirmed with corrections.** Sizes confirmed in `maia3/model_registry.py` (5M = 5,230,084 params; 23M = 22,936,580, counted by instantiating the models). **There is no documented Python API**; the package exposes a UCI engine (`maia3-uci`). Analysis must import `maia3.models.MAIA3Model` and `maia3.dataset` directly. **Conditioning** = two integers, `SelfElo` and `OppoElo`, linearly interpolated between two learned embeddings over 0–5000 (continuous, not bucketed). **Full distribution:** the model emits logits over 4,352 moves; masking to legal moves + softmax gives the full legal distribution (needed for F). The UCI wrapper exposes only top-k (MultiPV ≤ 20), so F must use the Python path. **Input:** 8-position history (piece planes only; **castling rights and en passant are not encoded**), board mirrored for Black. The UCI default **ignores move history** unless `--use-uci-history` is passed; analysis must feed real history. `include_time_info` is false for the released presets (clocks are not used). Weight download is via Hugging Face with **no pinned revision** in the registry | `CSSLab/maia3` @ `1e13597c` (`uci.py`, `models.py`, `dataset.py`, `model_registry.py`) |
| Maia-3 license (AGPL-3.0 as stated by ports) | [Verify] | **Code: Confirmed AGPL-3.0** (`LICENSE`). **Weights: Unavailable — BLOCKED** (`huggingface.co`) | `CSSLab/maia3/LICENSE` |
| Lichess puzzle CSV fields | Verified | **Confirmed** and extended: `PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags,DailyDate`. FEN is the position **before the opponent's move**; the puzzle starts after applying the first move. Popularity is −100…100 | `lichess-org/database` `web/index.html.tpl` @ `76ffe830` (the source of database.lichess.org) |
| Lichess puzzle license | [Verify] | **Confirmed CC0** ("Database exports are released under the Creative Commons CC0 license") | same file; lichess-org/api spec: "Our collection of puzzles is in the public domain" |
| Lichess puzzle ratings are Glicko-2 from solve attempts | Verified | **Confirmed** ("each attempt to solve is considered as a Glicko2 rated game between the player and the puzzle") | same file |
| Lichess opening explorer API availability, authentication, rate limits | [Verify] | **Corrected.** Host is now **`explorer.lichess.org`** (not `.ovh`). The `/lichess` endpoint declares **`security: OAuth2`** → a Lichess account and personal API token are needed. Rate limit: "Only make one request at a time"; on 429 wait one minute. Rating groups are 0, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500. Live call **BLOCKED** | `lichess-org/api` `doc/specs/tags/openingexplorer/lichess.yaml`, `lichess-api.yaml` @ `c1644a78` |
| Syzygy local file sizes, or Lichess tablebase API terms | [Verify] | **API: Confirmed** host `tablebase.lichess.org`, `security: []` (no auth), same one-request-at-a-time rule. **Local 5-piece size: Unavailable — BLOCKED** (download hosts blocked; widely cited as ≈ 939 MiB for 3-4-5 WDL+DTZ, unconfirmed) | `lichess-org/api` `doc/specs/tags/tablebase/standard.yaml` |
| `python-chess` exposes a SEE function | [Verify] | **Corrected: no.** python-chess 1.11.2 (latest on PyPI) has no SEE / static-exchange function → implement and unit-test our own (Phase 2) | `dir(chess.Board)`; PyPI |
| `python-chess` legal-en-passant FEN option | [Verify] | **Confirmed**: `Board.fen(en_passant="legal")` is the default and omits an ep square whose capture is illegal (tested with a pinned capturer). **Caveat:** `chess.polyglot.zobrist_hash(board)` hashes the *pseudo-legal* ep square, so the hash differs from the normalized key. Compute the Zobrist from `chess.Board(fen_norm)` | experiment in python-chess 1.11.2 |
| iOS home-screen web apps support Web Push | [Verify] | **Pending Sam's devices** — test page ready (§8) | — |
| Multi-threaded WASM needs cross-origin isolation | Verified | Unchanged | — |
| `ts-fsrs` implements FSRS v6 | Verified | Unchanged; latest is 6.0.0 (npm) | npm registry |
| Cloudflare Pages free-tier terms | [Verify] (§29) | **Confirmed (secondary + official snippets)**: 500 builds/month, 1 concurrent build, 20-min build timeout, 20,000 files per site, 25 MiB per file, static requests free and unlimited; Pages Functions count against Workers Free (100,000 requests/day). `*.pages.dev` subdomain with HTTPS. `developers.cloudflare.com` itself was blocked for direct fetch | [Pages limits](https://developers.cloudflare.com/pages/platform/limits); [Jan 2026 changelog](https://developers.cloudflare.com/changelog/post/2026-01-23-pages-file-limit-increase/index.md) |
| Oracle Always Free Arm limits | [Verify] (§29) | **Corrected: halved in 2026** to **2 OCPU / 12 GB** (1,500 OCPU-h and 9,000 GB-h per month), reported effective 2026-06-15 with no announcement; 200 GB block storage unchanged. `docs.oracle.com` was blocked for direct confirmation | [InfoQ, Jul 2026](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/); [Linuxiac](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/); [Oracle Always Free page](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm) |
| Arm builds of Stockfish and Maia | [Verify] (§29) | **Stockfish 18: Confirmed** — cross-compiled `ARCH=armv8-dotprod` (Ampere Altra supports dotprod); under qemu the `bench 16 1 8` signature is **182,602 nodes, identical to x86** (functionally correct). **Arm speed: Unavailable** (needs real Arm hardware). **Maia: Confirmed installable** — PyTorch 2.15.0 publishes `manylinux_2_28_aarch64` wheels (cp312: 484 MB); Maia3 is pure Python on top | experiment; PyPI |

## 3. Benchmarks vs go thresholds

| Check (spec §27) | Go threshold | Result | Pass? |
| --- | --- | --- | --- |
| Engine pipeline (all passes + detectors) | ≤ 60 s per average game | **BLOCKED** on your games. Per-search cost measured (below). Detectors don't exist yet and are excluded | — |
| Engine accuracy vs 50M reference (500 positions) | Class agreement ≥ 90% after boundary pass | **BLOCKED** on your games. Script ready: `server/phase0/accuracy_bench.py` | — |
| Maia3-23M throughput | ≤ 30 s per game (analysis scope), else 5M | **Timing only** (random weights, same architecture): 3.0 s for a 33-ply game, 1 thread, x86. Real-game number BLOCKED on your games | likely pass (x86) |
| Server Maia move latency (sparring) | ≤ 1 s p95 | 23M: **p95 58.6 ms** (1 thread), 42.9 ms (2 threads); 5M: p95 29.8 ms. x86, random weights | **pass (x86)** |
| Full-history backfill | ≤ 72 h | **BLOCKED** (needs your game count) | — |
| Hosting cost | $0 on the free stack | See §6 | — |
| PWA | Installs; 50 MB IndexedDB writable on oldest device | Test page ready; passes in headless Chromium (50 MB written in 1.1 s, read back intact). **Needs your iPad Pro** | — |
| Opening reference | Explorer API usable, or fallback ≤ 10 GB and 24 h | Explorer needs OAuth2 (Lichess account). Fallback sizing BLOCKED | — |
| Tablebase | Syzygy 5-piece local, or API works | API needs no auth (spec); live call BLOCKED | — |

### 3.1 Stockfish per-search cost (x86, 1 thread, Hash 256 MB, mean of 4 middlegame/endgame positions)

| Pass | Search | Stockfish 18 | Stockfish 19 |
| --- | --- | --- | --- |
| First | 1M nodes, MultiPV 3 | 1.74 s | 1.53 s |
| Deep | 5M nodes, MultiPV 4 (searchmoves) | 6.57 s | 7.19 s |
| Boundary | 20M nodes, MultiPV 4 | 26.9 s | 28.8 s |
| Threat probe | 200k nodes | 0.33 s | 0.32 s |

Implication (to be confirmed with real games): an 80-ply game costs ≈ 80 × 1.7 s ≈ 140 s for the first pass alone
on one core, before deep and boundary passes. On a 33-ply test game the full pipeline took 235 s on one core,
of which 136 s was boundary rechecks. **At the spec's node budgets the ≤ 60 s/game threshold can only be met as
throughput across ≥ 4 cores, and probably not on a 2-OCPU free Arm VM.** The fallback options are in §7.

## 4. Pinned versions and checksums

| Item | Pin | SHA-256 |
| --- | --- | --- |
| Stockfish 18 source | tag `sf_18`, commit `cb3d4ee9b47d0c5aae855b12379378ea1439675c` (2026-01-31) | — |
| NNUE big `nn-c288c895ea92.nnue` (108,919,594 B) | from `official-stockfish/networks` | `c288c895ea924429ea9092e3f36b2b3c1f00f2a3a4c759ff7e57e79e3b43e4a7` |
| NNUE small `nn-37f18f62d772.nnue` (3,519,630 B) | same | `37f18f62d772f3107e1d6aaca3898c130c3c86f2ab63e6555fbbca20635a899d` |
| Stockfish 18 binary, x86-64-avx512, gcc 13.3, PGO | built here (build-specific, not portable) | `6bc75c1b2b689aec0f3b61b787e3cce139631894e9f57d6f5f2a319a2392cc4a` |
| Stockfish 18 binary, armv8-dotprod, aarch64-linux-gnu-g++ 13 | built here | `f57874eface2d30ae8d0b029a0c27fdfcb1c27bb8f2716014504587bc14ab0ba` |
| (comparison) Stockfish 19 | tag `sf_19`, commit `edb0d9db6731067ec50ce619ff372b463bc4dd5d`; net `nn-1a298aa575a0.nnue` | net `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Maia-3 code | `CSSLab/maia3` commit `1e13597c42d4858b7cfd7cfdae01e297263364b2` (2026-05-25), package 0.1.0 | — |
| Maia3-23M / 5M weights | `UofTCSSLab/Maia3-23M`, `UofTCSSLab/Maia3-5M` | **BLOCKED** (`huggingface.co`) |
| Lichess puzzle CSV | `lichess_db_puzzle.csv.zst` | **BLOCKED** (`database.lichess.org`) |
| python-chess | 1.11.2 | (PyPI wheel) |
| PyTorch | 2.15.0 (CPU use) | (PyPI wheel) |

The network filenames are the first 12 hex digits of their SHA-256, and both downloads matched.

## 5. Game counts by time class and primary time class

**BLOCKED** (`api.chess.com`). Needed: `/pub/player/turners1110/games/archives`, then each month serially.
Recommendation pending; the spec's default (rapid primary, blitz analyzed separately) stands until counted.

## 6. Hosting

- **Frontend: Cloudflare Pages (free).** Fits easily: the PWA is static, far below 20,000 files and 25 MiB per
  file, with unmetered static bandwidth and a free `*.pages.dev` HTTPS subdomain. Needs a free Cloudflare
  account (your action). Recommended.
- **Backend: Oracle Always Free Arm** is now **2 OCPU / 12 GB** (halved in 2026). Stockfish 18 and Maia-3 both
  run on aarch64. Memory is fine (Postgres + 23M Maia + 2 engines at 256 MB hash ≈ 3–4 GB). **CPU is the
  problem**: 2 cores, each slower than this Xeon core for Stockfish (Arm speed not measured; needs a VM). Known
  risks: idle-instance reclamation, "out of capacity" in popular regions, terms that changed without notice.
- **Verdict so far:** the free VM meets every threshold except, probably, the engine pipeline at the spec's
  budgets. The final call waits for the real-game benchmark.

| Option | Cost | Notes |
| --- | --- | --- |
| Oracle Always Free A1 (2 OCPU, 12 GB) | $0 | Needs an Oracle account and card verification (your action). Pipeline throughput likely short at spec budgets |
| Oracle A1 beyond free (pay-as-you-go) | ≈ $0.01/OCPU-h + $0.0015/GB-h (list price; verify) | e.g. +2 OCPU ≈ $15/month |
| Hetzner CAX21 (4 Arm vCPU, 8 GB) / CAX31 (8 vCPU, 16 GB) | ≈ €8–10 / €16–21 per month after 2026 price rises; ordering reportedly paused at times in Oct 2026 | Verify on hetzner.com |
| Workers on a home computer pushing results to the free VM | $0 | Spec §29 fallback; analysis runs whenever the computer is on |
| Lower engine budgets on the free VM | $0 | Trades accuracy for speed; decide after the accuracy benchmark |

## 7. Fallback decisions for missed thresholds (draft)

| Threshold | If missed | Fallback |
| --- | --- | --- |
| Pipeline ≤ 60 s/game | Likely on 2 OCPU | (1) Treat the gate as throughput (wall-clock ÷ games with all workers); (2) cut `engine.first_nodes` (e.g. 1M → 300k) if the accuracy benchmark still shows ≥ 90% agreement; (3) skip the boundary pass for opponent moves; (4) home-computer workers |
| Accuracy ≥ 90% | — | Raise deep/boundary budgets only for Sam's moves |
| Maia 23M ≤ 30 s/game | Unlikely | `maia.server_model = "5M"` |
| Explorer API | Needs a Lichess account | Either you create a Lichess account and token, or use the local fallback reference |

## 8. Device checks (iPhone + 5-year-old iPad Pro)

Test page: `web/device-test/` (index.html, sw.js, manifest, icons). No third-party code. It checks home-screen
install (standalone mode), persistent-storage request, a **50 MB IndexedDB write + read-back with
verification**, storage estimate, notification permission, a local notification, and a real Web Push
subscription (VAPID).

**Exact steps:** in §9 of the summary message / below once hosted (the page must be served over HTTPS).

## 9. Proposed spec edits (do not apply without Sam's approval)

| # | Section | Proposed edit |
| --- | --- | --- |
| E1 | §6 row "User-Agent", Appendix B1 | Replace "Claude Code already has a working chess.com connection" with "Use the public Published-Data API (§7.1); no connector is required" |
| E2 | §27 / Appendix D | State explicitly whether Phase 0 may run before Phase P (it did); move "Findings feed Phase 0" to "Findings feed Phase 1 tuning" |
| E3 | §5, §8, §29, §6 | Decide Stockfish 18 vs 19. Stockfish 19 (2026-09-05, single smaller net, +44 Elo vs 18) is current. Proposed: keep 18 for Phase 1 (pinned, benchmarked) and evaluate 19 as a version bump with re-derivation (§25 "Version change") |
| E4 | §8.3 Win% | "cp clamped to ±1000 first (Lichess `Cp.CEILING`)" instead of ±1500 |
| E5 | §8.3 Mate scores | "A mate for the mover scores as +1000 cp (Win% ≈ 97.53); being mated as −1000 cp (≈ 2.47), matching lila." Note: with this, a mate-in-1 missed for a "+9 cp" move loses only ≈ 47 Win% points, and Win% never reaches 100/0, so the §8.4 suppression rule (Win% > 95 / < 5) behaves differently: above +800 cp is already > 95 |
| E6 | §8.3 Accuracy | Add the exact formulas and the +15 cp initial-position convention from §2 of this report, citing `lila@898ad2cd` |
| E7 | §8.6 | "Compute the Zobrist hash from the normalized position (`chess.Board(fen_norm)`), because python-chess's Polyglot hash includes pseudo-legal en passant squares" |
| E8 | §9.1 SEE | Replace [Verify] with "python-chess has no SEE; implement `see(board, move)` with unit tests (Phase 2)" |
| E9 | §11.1 Maia | "There is no Maia-3 Python API: import `MAIA3Model` and `maia3.dataset` directly; feed the real 8-ply history; pin the Hugging Face revision (the registry does not). Maia-3 does not encode castling rights or en passant, so identical piece placements with different rights get the same distribution" |
| E10 | §11.2 / §11.3 | Conditioning inputs are `SelfElo` and `OppoElo` (continuous, 0–5000). State which opponent rating to use for F and unlock (proposal: the opponent's actual chess.com rating mapped by the same anchor offset) |
| E11 | §16.2 | Explorer host `explorer.lichess.org`; **OAuth2 token required** (Lichess account); rating groups 0/1000/1200/1400/1600/1800/2000/2200/2500, so "anchor + 200" must be rounded to a group |
| E12 | §29 Hosting | Oracle Always Free Arm is 2 OCPU / 12 GB since mid-2026; size the worker pool (`engine.workers = 2`) accordingly |
| E13 | §29 Stack | `chessground` → `@lichess-org/chessground` (the unscoped package is deprecated) |
| E14 | §27 Phase 0 table | Define "per average game" for the pipeline gate as throughput: wall-clock time for N games with all workers ÷ N, on the production host |
| E15 | §16.2 / §20 | Lichess puzzle FEN is the position *before* the opponent's move; exercises start after applying `Moves[0]` |

## 10. GO / NO-GO

**Not decided yet: Phase 0 is incomplete.** Blockers: network access to `api.chess.com`, `huggingface.co`,
`database.lichess.org`, `explorer.lichess.org`, `tablebase.lichess.org` (and optionally `docs.oracle.com`,
`tests.stockfishchess.org`); the device test on your iPhone and iPad Pro; and a decision on hosting.
