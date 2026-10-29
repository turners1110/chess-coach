# Chess Coach — Phase 0 report

Date: 2026-10-29 · Spec: `docs/chess-coach-spec-v2.1.md` · Scope: §27 Phase 0 and Appendix B only.
Machine for all measurements unless stated: cloud container, Intel Xeon @ 2.10 GHz (AVX-512, BMI2),
4 vCPU, 15 GB RAM, Linux x86-64. Raw outputs: `server/phase0/out/` (git-ignored; regenerate with the scripts).

> **Status: COMPLETE, except the steps only Sam can do** (device tests, hosting decision, and the choices in §10).
> Session 1 did the source verification. Session 2 at first found every host blocked; after the network change
> the hosts were reachable, and all of handoff §2 was run on Sam's real games. Two items stayed blocked by
> the network and are marked **BLOCKED**: the Maia weight files (the Hugging Face CDN `us.aws.cdn.hf.co`)
> and the Syzygy file hosts. Neither blocks a gate. Nothing below is estimated or mocked unless it says
> **projection**.

---

## 1. Conflicts found between your instructions and the spec

| # | Conflict | Resolution |
| --- | --- | --- |
| C1 | Spec §6 / Appendix B1 say to use "Claude Code's existing chess.com connection". There is no such connector | Used the public Published-Data API (§7.1). It works without any account. Proposed edit E1 |
| C2 | Spec §27 orders **Phase P (artifact prototype) before Phase 0**. You asked for Phase 0 only | Followed your instruction. Phase P findings are not available to this report. Proposed edit E2 |
| C3 | Spec §0 / `coach.toml` set **rapid as the primary time class**. Your recent play is almost all **blitz**: 161 rated blitz vs 13 rated rapid games in the last 90 days (all time: 822 rapid vs 171 blitz). See §5 | **Your decision (§10, D-A).** The spec's default stands until you choose |
| C4 | Spec §29 repo layout assumed a fresh repo | Done: `turners1110/chess-coach` |

## 2. Fact register (spec §6), every [Verify] resolved

Legend: **Confirmed** (spec right), **Corrected** (spec wrong or outdated: see edit), **Unavailable** (could not be
checked in Phase 0; code must not depend on it yet).

| Fact | Spec status | Phase 0 result | Source / experiment |
| --- | --- | --- | --- |
| chess.com Published-Data API: read-only JSON, monthly archives; serial unlimited, parallel may 429 | Verified | **Confirmed** for serial use: 32 serial requests, no 429 and no retries | `server/phase0/chesscom_check.py`, 2026-10-29 15:00 UTC |
| Archive API returns only finished games | [Verify] | **Confirmed (observational).** 0 unfinished games among all 1,115 archived games (every game has `end_time`, both results, and a Result tag other than `*`). The current month was fetched 3 min after your latest game ended. You had no ongoing daily games (`/games` empty). A live game in progress during the fetch could not be arranged; keep a cheap `Result != "*"` guard in the importer | same script, `checks.json` |
| chess.com requires a descriptive User-Agent | [Verify] | **Confirmed, with detail:** with no User-Agent header → **403**; empty UA → 403; `python-requests/2.32` → 403; `curl/8.5.0`, `Mozilla/5.0` and our descriptive UA → 200. So a UA is required, and some library defaults are refused. Use the descriptive UA from `coach.toml` | experiment (curl + urllib) |
| Past monthly archives never change | [Verify] | **Confirmed for the test window.** The 3 oldest months (2025-01…03) re-fetched: same ETag and same body SHA-256, and `If-None-Match` returns **304**. ETags are weak (`W/"…"`); `Last-Modified` is the fetch time, so it is useless for caching. "Never" cannot be proven; keep the Resync action (§7.2) | same script |
| Lichess Win% = 50 + 50·(2/(1+e^(−0.00368208·cp)) − 1) | Verified | **Confirmed**, with a **correction to §8.3**: Lichess clamps cp to **±1000**, not ±1500 | `scalachess` `core/src/main/scala/eval.scala` @ `a4988192` (`Cp.CEILING = 1000`, `MULTIPLIER = -0.00368208`) |
| Lichess move accuracy, game accuracy, mate handling | [Verify] | **Corrected.** Move accuracy = `103.1668100711649·e^(−0.04354415386753951·Δ) − 3.166924740191411 + 1`, clamped 0–100 (100 if Win% did not drop). Game accuracy = mean of (volatility-weighted mean, harmonic mean); window = clamp((n−1)/10, 2, 8); weights = population std-dev of Win% in the window, clamped 0.5–12; harmonic mean floors each value at 1. **Mate = Win% of ±1000 cp ≈ 97.53 / 2.47, not 100 / 0.** Game accuracy uses `forceAsCp`. The initial position is scored cp +15 (`legacyInitial`) | `lila` `AccuracyPercent.scala`, `eval.scala` @ `898ad2cd`; `scalalib` `Maths.scala` @ `31fc151b`. Port `server/phase0/lila_accuracy.py` passes all 18 upstream cases; golden fixtures from 3 real games in `server/tests/fixtures/accuracy_golden.json` |
| Stockfish 18 release and UCI options (`searchmoves`, MultiPV) | [Verify] | **Confirmed.** Tag `sf_18`, released 2026-01-31. `go nodes N searchmoves a b c d` with MultiPV 4 returns exactly those moves as ranked PVs from one search. **Stockfish 19 was released 2026-09-05**; see edit E3 | Stockfish tags and blog; experiment |
| Stockfish determinism with Threads 1 and cleared hash | (B4) | **Confirmed**: identical scores, PVs and node counts on repeat. The session-2 rebuild produced a binary with the **same SHA-256** as session 1 (`6bc75c1b…`) | experiment |
| Maia-3 sizes; UCI code; Elo conditioning | Verified (repo); Python API and conditioning [Verify] | **Confirmed with corrections.** 5M = 5,230,084 params; 23M = 22,936,580. **No documented Python API**: import `maia3.models.MAIA3Model` and `maia3.dataset` directly. Conditioning = `SelfElo`, `OppoElo`, continuous 0–5000. Full legal distribution via logits (4,352 moves) + legal mask + softmax; the UCI wrapper gives only top-k. Input: 8-position history, **no castling or en passant encoded**; the UCI default ignores history unless `--use-uci-history`. Clocks unused in released presets | `CSSLab/maia3` @ `1e13597c` |
| Maia-3 license | [Verify] | **Code: Confirmed AGPL-3.0.** **Weights: Confirmed by reference.** The model cards carry no license tag. They say "License: CC BY 4.0 (paper); see repo for code/weights license", and the repo is AGPL-3.0, so treat the weights as AGPL-3.0. HF revisions pinned (§4). **Weight files: BLOCKED** (CDN host `us.aws.cdn.hf.co`) | `huggingface.co/api/models/UofTCSSLab/Maia3-23M`, model card README @ `51a0145a` |
| Lichess puzzle CSV fields | Verified | **Confirmed** on the real file: `PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags,DailyDate`. FEN is the position **before the opponent's move** | download 2026-10-29 (§4) |
| Lichess puzzle license | [Verify] | **Confirmed CC0** | `lichess-org/database` `web/index.html.tpl` @ `76ffe830` |
| Lichess puzzle ratings are Glicko-2 from solve attempts | Verified | **Confirmed** | same |
| Lichess opening explorer API availability, authentication, rate limits | [Verify] | **Corrected.** Host is **`explorer.lichess.org`**. Live test: **HTTP 401 without a token for both `/lichess` and `/masters`**, so a Lichess account and personal API token are needed for every explorer call. Rate limit (spec): one request at a time; on 429 wait one minute. Rating groups 0/1000/1200/1400/1600/1800/2000/2200/2500 | live test 2026-10-29; `lichess-org/api` specs @ `c1644a78` |
| Syzygy local file sizes, or Lichess tablebase API terms | [Verify] | **API: Confirmed**: no auth; **50 serial lookups, all HTTP 200, median 0.39 s, p95 0.48 s, max 0.72 s** (3–5 pieces, random legal positions; from this container through its proxy). **Local file size: BLOCKED** (file hosts blocked); not needed while the API works | live test 2026-10-29 |
| `python-chess` exposes a SEE function | [Verify] | **Corrected: no** (1.11.2). Implement and unit-test our own (Phase 2) | `dir(chess.Board)`; PyPI |
| `python-chess` legal-en-passant FEN option | [Verify] | **Confirmed**: `Board.fen(en_passant="legal")` is the default. **Caveat:** `chess.polyglot.zobrist_hash` hashes the pseudo-legal ep square; compute it from `chess.Board(fen_norm)` | experiment |
| iOS home-screen web apps support Web Push | [Verify] | **Pending your devices** (§8) | — |
| Multi-threaded WASM needs cross-origin isolation | Verified | Unchanged | — |
| `ts-fsrs` implements FSRS v6 | Verified | Unchanged; latest 6.0.0 | npm |
| Cloudflare Pages free-tier terms | [Verify] (§29) | **Confirmed**: 500 builds/month, 20,000 files and 25 MiB per file, static requests free and unlimited; `*.pages.dev` with HTTPS | Cloudflare Pages limits page and Jan 2026 changelog |
| Oracle Always Free Arm limits | [Verify] (§29) | **Corrected, now from the primary source:** "the first **1,500 OCPU hours and 9,000 GB hours per month** … equivalent to **2 OCPUs and 12 GB of memory**" (was 4 / 24). **200 GB** block volume storage. **Idle reclamation:** an instance may be reclaimed if, over 7 days, 95th-percentile CPU < 20 % **and** network < 20 % **and** (A1 only) memory < 20 % | `docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm`, fetched 2026-10-29 |
| Arm builds of Stockfish and Maia | [Verify] (§29) | **Confirmed** (session 1): Stockfish 18 `armv8-dotprod` gives the same bench signature as x86 under qemu; PyTorch publishes aarch64 wheels. **Arm speed: Unavailable** (needs a real Arm VM) | session 1 experiment; PyPI |

## 3. Benchmarks vs go thresholds

All on Sam's real games: the **20 most recent rated rapid games** (10+0, mean 68.0 plies) and the **10 most recent
blitz games** (mean 62.1 plies). Stockfish 18 (pinned build), Threads 1, Hash 256 MB, 4 parallel workers
(one engine per core). Detectors are not built yet and are excluded.

| Check (spec §27) | Go threshold | Result | Pass? |
| --- | --- | --- | --- |
| Engine pipeline, spec budgets (1M / 5M / 20M) | ≤ 60 s per average game | **Rapid: 107.7 s/game** throughput on 4 cores (single core: 344.8 s/game, 5.07 s/ply). **Blitz: 98.1 s/game** (single core 355.5 s) | **FAIL** |
| — variant A: first + played at 300k | same | 78.8 s/game on 4 cores (single core 250.7 s) | FAIL |
| — variant **Lite**: first + played 300k, deep 2M, boundary 5M | same | **31.1 s/game** on 4 cores (single core 106.6 s, 1.57 s/ply). **Projection** for 2 equal x86 cores: ≈ 53 s | **PASS on 4 cores** (see accuracy) |
| Engine accuracy vs 50M reference (500 positions) | Class agreement ≥ 90 % after the boundary pass | See §3.2 | see §3.2 |
| Maia3-23M throughput (analysis scope) | ≤ 30 s per game, else 5M | **5.8 s/game** (1 thread), 3.2 s (2 threads); 5M: 2.0 s. 245 forward passes per game. Random weights, same architecture: inference cost does not depend on weight values | **PASS** |
| Server Maia move latency (sparring) | ≤ 1 s p95 | 23M **p95 43.8 ms** (1 thread); 5M p95 25.0 ms | **PASS** |
| Full-history backfill | ≤ 72 h | 1,022 analyzable games (822 rapid, 171 blitz, 29 bullet), 69,090 plies. Spec budgets: 97.3 core-hours → **24.3 h on 4 cores**, 48.7 h on 2 x86 cores (**projection**). Lite: 30.1 core-hours → 7.5 h on 4 cores, 15 h on 2 | **PASS** (≥ 2 x86-equivalent cores) |
| Hosting cost | $0 on the free stack, or Sam decides to pay | See §6 | your decision |
| PWA | Installs; 50 MB IndexedDB writable on the oldest device | Headless Chromium passes. Needs your iPad Pro | pending you |
| Opening reference | Explorer API usable, **or** fallback ≤ 10 GB and 24 h | Explorer needs a token (401 without one). Fallback measured: see §3.3 | **PASS (fallback)**, or explorer with a token |
| Tablebase | 5-piece local, or the API works | API works: median 0.39 s; about 1 tablebase position per game (21 of 1,359 plies in the rapid sample) | **PASS (API)** |

### 3.1 Where the engine time goes (rapid sample, spec budgets)

| Pass | Share of time | Notes |
| --- | --- | --- |
| First (1M, MultiPV 3) | 25.6 % | every position |
| Played-move (1M) | 8.6 % | 34.5 % of moves are outside the first-pass top 3 |
| Deep (5M) | 19.3 % | 191 of 1,359 moves |
| Boundary (20M) | **44.0 %** | **57 % of deep-pass moves** land within ±2 Win% of a boundary and get rechecked |
| Threat probe (200k) | 2.4 % | |

The boundary pass is the main cost. The ±2 margin around three class boundaries plus the unique-solution gap
covers most of the Win% range where flagged moves live, so most deep moves get a 20M recheck.

### 3.2 Engine accuracy vs the 50M reference

ACCURACY_PLACEHOLDER

### 3.3 Opening-reference fallback (§16.2), measured on the 2026-09 Lichess dump

- Dump `lichess_db_standard_rated_2026-09.pgn.zst`: **29.2 GB**, **89.6 M games**.
- Scanned the first 2 GiB (6,575,309 games, single core): decompression + header filter at **52,447 games/s**.
  **32.7 %** of games are blitz or rapid with both players rated 1400–2000.
- Replaying the first 20 plies and counting (position, move) with W/D/L: **784 games/s per core**.
  100,000 games → 1.11 M entries, of which 1,677 have ≥ 50 games.
- **Projection** for one full month: scan ≈ 29 min; ≈ 29 M matching games → tree build ≈ 10.4 core-hours
  (2.6 h on 4 cores); download 29.2 GB ≈ 40 min at 100 Mbit/s. Storage after dropping entries with < 5 games:
  well under 10 GB. Raw dictionaries in Python do not scale to a whole month in RAM; Phase 6 should build into
  SQLite or sorted on-disk runs. **Fits 24 h and 10 GB.** A 3–5 M-game sample (1–2 core-hours) is enough for
  the "≥ 50 games" theory bar at common nodes.

## 4. Pinned versions and checksums

| Item | Pin | SHA-256 |
| --- | --- | --- |
| Stockfish 18 source | tag `sf_18`, commit `cb3d4ee9b47d0c5aae855b12379378ea1439675c` (2026-01-31) | — |
| NNUE big `nn-c288c895ea92.nnue` (108,919,594 B) | `official-stockfish/networks` | `c288c895ea924429ea9092e3f36b2b3c1f00f2a3a4c759ff7e57e79e3b43e4a7` |
| NNUE small `nn-37f18f62d772.nnue` (3,519,630 B) | same | `37f18f62d772f3107e1d6aaca3898c130c3c86f2ab63e6555fbbca20635a899d` |
| Stockfish 18 binary, x86-64-avx512, gcc 13.3, PGO | built here, reproduced in session 2 | `6bc75c1b2b689aec0f3b61b787e3cce139631894e9f57d6f5f2a319a2392cc4a` |
| Stockfish 18 binary, armv8-dotprod, aarch64-linux-gnu-g++ 13 | built here (session 1) | `f57874eface2d30ae8d0b029a0c27fdfcb1c27bb8f2716014504587bc14ab0ba` |
| (comparison) Stockfish 19 | tag `sf_19`, commit `edb0d9db6731067ec50ce619ff372b463bc4dd5d`; net `nn-1a298aa575a0.nnue` | net `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` |
| Maia-3 code | `CSSLab/maia3` commit `1e13597c42d4858b7cfd7cfdae01e297263364b2`, package 0.1.0 | — |
| Maia3-23M weights `maia3-23m.pt` (91,799,307 B) | HF `UofTCSSLab/Maia3-23M` revision **`51a0145a8178046f7de23119160b136672deeb2b`** | `bce6cd1af5f0399ac7eed33fabb7a6a2ef6193662c2740f262bf93af7bfb3569` (from HF LFS metadata; file download BLOCKED) |
| Maia3-5M weights `maia3-5m.pt` (20,968,049 B) | HF `UofTCSSLab/Maia3-5M` revision **`b6559de2398d7140b985f28fd2c19fb5e47ddabe`** | `ba14208b2992d85502f5fb501934abf6aaaeb355e9f3fdf90e326911f562524f` (same) |
| Lichess puzzle CSV `lichess_db_puzzle.csv.zst` (307,234,795 B, Last-Modified 2026-10-02) | 6,157,341 puzzles; 2,739,910 with Popularity ≥ 80 and NbPlays ≥ 500 | `76335bfa7d7c4a7f93c1366d81549e53951ebb79dd43d34904cab8f22d962f8d` |
| 500-puzzle pack `server/phase0/out/puzzle_pack.csv` | `puzzle_pack.py`, seed 7 | `6b8bdf80e69667fbdaaecc6597fae9f17a530fa8da4358eddfb1283e333e9438` |
| Golden fixture `server/tests/fixtures/accuracy_golden.json` | `accuracy_golden.py`, 3 games | `e50eb333a6d6a4283e399b63b9d604b312f1719f87a14259ad2dc4c375a9fb91` |
| python-chess | 1.11.2 | (PyPI wheel) |
| PyTorch | 2.15.0 (PyPI x86 build is `+cu132`; CPU use only) | (PyPI wheel) |

**Puzzle pack:** 500 puzzles, rated 1000–2000 (`glicko.placement_range`), Popularity ≥ 80, NbPlays ≥ 500, equal
shares over 12 themes that match the §9.1 detectors (hangingPiece, fork, pin, skewer, discoveredAttack,
backRankMate, mate, capturingDefender, trappedPiece, promotion, intermezzo, defensiveMove). Your own motif
frequencies need the Phase 2 detectors; the shares are re-weighted then.

## 5. Game counts by time class and primary time class

Account `turners1110` (player_id 425089135), joined 2025-01-30. 22 monthly archives, **1,115 games**.
Current ratings: rapid 1026 (best 1062), blitz 640 (best 862), bullet 438.

| Time class (standard chess) | All time, rated | All time, unrated | Last 90 days, rated |
| --- | --- | --- | --- |
| Rapid | **823** | 55 | 13 |
| Blitz | 171 | 1 | **161** |
| Bullet | 29 | 3 | 2 |
| Daily | 1 | 10 | 0 (2 unrated) |
| Variants (chess960, odds) | 16 | 6 | — |

By month: rapid every month from Feb 2025 to Jul 2026 (up to 98 a month), then **blitz from Aug 2026**
(19 → 61 → 81 games) with almost no rapid.

**Recommendation:** rapid has 4.8× more history, so it gives the stronger diagnosis today. But if blitz is now
what you play, the coach should measure improvement where you play. Choose (D-A in §10): keep **rapid primary**
(spec default), or switch to **blitz primary** with rapid as history. Either way both are analyzed (§7.3, §14).

## 6. Hosting

- **Frontend: Cloudflare Pages (free).** Recommended. Needs a free Cloudflare account (your action).
- **Backend: Oracle Always Free Arm = 2 OCPU / 12 GB** (confirmed on docs.oracle.com).
  - **Maia, Postgres, API: fit easily.** Maia 23M needs 5.8 s per game; memory ≈ 3–4 GB in total.
  - **Engine: does not fit at the spec budgets.** 345 core-seconds per rapid game means ≈ 172 s/game on 2 x86
    cores (**projection**), and Ampere cores are slower per core than this Xeon for Stockfish (not measured).
    With the **Lite** budgets: ≈ 53 s/game on 2 x86 cores (**projection**), so marginal on 2 Arm cores.
  - **Ongoing load is tiny:** you play about 2–3 rated games a day (176 in the last 90 days, peak 81 a month).
    At spec budgets that is ≈ 15 core-minutes a day. The 60 s gate matters for import latency and the one-off backfill,
    not for daily use.
  - **Idle reclamation risk:** reclaimed only if CPU (p95), network **and** memory all stay under 20 % for 7 days.
    Keeping Maia and Postgres resident (> 2.4 GB of 12 GB) keeps the memory condition false.
- **Backfill on the free VM:** 1,022 games ≈ 49 h at spec budgets on 2 x86-equivalent cores (**projection**);
  within 72 h only if an Ampere core is at least ≈ 0.68× this Xeon core. With Lite: ≈ 15 h.

| Option | Cost | Engine result |
| --- | --- | --- |
| Oracle Always Free A1 (2 OCPU, 12 GB) + Lite budgets | $0 | Meets the gate as **projection** only, if accuracy holds (§3.2). Needs one benchmark run on a real A1 VM |
| Oracle Always Free + spec budgets, gate read as daily throughput (E14) | $0 | Daily load fine; first import of 200 games ≈ 10 h; backfill ≈ 2–3 days |
| Oracle A1 beyond free (pay-as-you-go) | ≈ $0.01/OCPU-h + $0.0015/GB-h (list; verify) | e.g. +2 OCPU ≈ $15/month |
| Hetzner CAX21 (4 Arm vCPU, 8 GB) / CAX31 (8 vCPU, 16 GB) | ≈ €8–10 / €16–21 per month (verify) | 4–8 cores: spec budgets at ≈ 45–90 s/game if an Ampere core matched this Xeon (**projection**; not measured) |
| Workers on a home computer pushing to the free VM | $0 | Spec §29 fallback; analysis whenever the computer is on |

## 7. Fallback decisions for missed thresholds

| Threshold | Missed? | Decision |
| --- | --- | --- |
| Pipeline ≤ 60 s/game | **Yes** at spec budgets (107.7 s on 4 cores) | FALLBACK_PIPELINE_PLACEHOLDER |
| Accuracy ≥ 90 % | ACC_MISSED_PLACEHOLDER | ACC_DECISION_PLACEHOLDER |
| Maia 23M ≤ 30 s/game | No | Keep `maia.server_model = "23M"` (re-check with real weights; timing is weight-independent) |
| Explorer API | Needs a Lichess account | Use the local fallback reference (§3.3) unless you create a Lichess account and token (D-C) |
| Tablebase | No | Use the Lichess tablebase API, serial, cached; Syzygy local files optional later |

## 8. Device checks (iPhone + 5-year-old iPad Pro)

Test page: `web/device-test/` (index.html, sw.js, manifest, icons). No third-party code. It checks home-screen
install (standalone mode), persistent-storage request, a **50 MB IndexedDB write + read-back with
verification**, storage estimate, notification permission, a local notification, and a real Web Push
subscription (VAPID). It passes in headless Chromium (50 MB written in 1.1 s, read back intact).

**Steps for you:** host `web/device-test/` over HTTPS (Cloudflare Pages: create a project, upload the folder;
or GitHub Pages if the repo is public). On each device: open it in Safari → Share → Add to Home Screen → open
from the home screen → press each button and screenshot the results. For the push test, a VAPID key pair is
needed: I generate one and put only the public key in `index.html` (the private key stays out of git).

## 9. Proposed spec edits (do not apply without Sam's approval)

| # | Section | Proposed edit |
| --- | --- | --- |
| E1 | §6 row "User-Agent", Appendix B1 | Replace "Claude Code already has a working chess.com connection" with "Use the public Published-Data API (§7.1); no connector is required. A User-Agent is required (no UA → 403)" |
| E2 | §27 / Appendix D | State whether Phase 0 may run before Phase P (it did); "Findings feed Phase 1 tuning" |
| E3 | §5, §8, §29, §6 | Stockfish 18 vs 19. Proposed: keep 18 for Phase 1 (pinned, benchmarked); evaluate 19 as a version bump with re-derivation (§25) |
| E4 | §8.3 Win% | "cp clamped to ±1000 first (Lichess `Cp.CEILING`)" instead of ±1500 |
| E5 | §8.3 Mate scores | "A mate for the mover scores as +1000 cp (Win% ≈ 97.53); being mated as −1000 cp (≈ 2.47), matching lila." With this, Win% never reaches 100/0, and the §8.4 suppression rule (> 95 / < 5) already applies above ≈ +800 cp |
| E6 | §8.3 Accuracy | Add the exact formulas and the +15 cp initial-position convention from §2, citing `lila@898ad2cd` |
| E7 | §8.6 | "Compute the Zobrist hash from the normalized position (`chess.Board(fen_norm)`)" |
| E8 | §9.1 SEE | "python-chess has no SEE; implement `see(board, move)` with unit tests (Phase 2)" |
| E9 | §11.1 Maia | "No Maia-3 Python API: import `MAIA3Model` and `maia3.dataset`; feed the real 8-ply history; pin the HF revision (§4). Maia-3 does not encode castling rights or en passant" |
| E10 | §11.2 / §11.3 | Conditioning inputs are `SelfElo` and `OppoElo` (continuous). Use the opponent's chess.com rating mapped by the same anchor offset |
| E11 | §16.2 | Explorer host `explorer.lichess.org`; **a token is required for every endpoint, including `/masters`** (401 without); rating groups 0/1000/…/2500, so "anchor + 200" must round to a group |
| E12 | §29 Hosting | Oracle Always Free Arm is 2 OCPU / 12 GB; add the idle-reclamation rule; size `engine.workers = 2` there |
| E13 | §29 Stack | `chessground` → `@lichess-org/chessground` |
| E14 | §27 Phase 0 table | Define "per average game" as throughput: wall-clock for N games with all workers ÷ N, on the production host |
| E15 | §16.2 / §20 | Lichess puzzle FEN is the position *before* the opponent's move; exercises start after applying `Moves[0]` |
| E16 | §7.2 | "ETags are weak; `Last-Modified` is the response time and must not be used for caching" |
| E17 | §8.1 / §30 | ENGINE_EDIT_PLACEHOLDER |

## 10. GO / NO-GO

VERDICT_PLACEHOLDER
