# Chess Coach — notes for Claude Code

Personal chess coach for one player (chess.com `turners1110`, "Sam"). The source of truth is
**`docs/chess-coach-spec-v2.2.md`**. If anything here or in a chat message conflicts with the spec,
the spec wins; tell Sam about the conflict. Phase 0 findings and proposed spec edits are in
`docs/phase0-report.md`. Do not edit the spec yourself; propose edits there.

## Current state

- **Phase 0: complete — conditional GO** (`docs/phase0-report.md` §10). Spec v2.2 applies Sam's approved edits.
  Still open: the engine host (Vercel is frontend only), the Lichess API token, the iPad device test, and Sam's go for Phase 1.
- **Phase P prototype: published** (claude.ai artifact, source in `web/prototype/`). Sam is testing it; read its
  `sessions` collection (ArtifactData) for ladder findings.
- Do **not** start Phase 1 until Sam gives the go-ahead after reading `docs/phase0-report.md`.

## Rules that always apply

1. **No [Verify] item enters code unverified.** Every spec item marked **[Verify]** must be resolved
   (Confirmed / Corrected / Unavailable, with a primary source or experiment) in the fact register in
   `docs/phase0-report.md` before any code depends on it. If it is Unavailable, the code must not rely on it.
2. **Every tunable number lives in `server/config/coach.toml`.** Never hard-code thresholds, budgets,
   weights or limits. Label: tunable / hypothesis / fixed / sam / phase0.
3. **Build in phase order** (§27). A phase starts only when the previous phase's exit gates pass.
4. **Tests before formula code.** Golden fixtures (Win%, accuracy, Glicko-2, canonical keys) come first.
5. **chess.com access is serial only** (§7.2): one request at a time, descriptive User-Agent, ETag caching,
   backoff 1 s doubling to 60 s, max 6 tries.
6. **Engine is truth** (§1): text never states a chess fact that Stockfish, the tablebase, Maia or a
   validated detector did not produce.
7. Idempotent jobs; keep this file current; test on a physical iPhone each phase.
8. Ask Sam before anything that costs money, creates accounts, or cannot be undone.

## Architecture (spec §5, §29)

```
chess.com API → Sync → Stockfish 18 (native) → Classifier ← Tablebase (≤5 pieces)
                        Maia-3 (server, PyTorch) ─┘
        → Diagnosis engine (GRI, weaknesses, habits, time-control gap)
        → Prescription engine (training priority, exercise selection, sessions)
        → Exercises (feedback ladder) · Sparring (Maia opponents) · Repertoire (FSRS)
        → Explainer (templates → Claude API with validator)
iPhone/iPad PWA: session runner, board, review, sparring client, offline cache, append-only event queue → server
```

| Dir | Contents |
| --- | --- |
| `web/` | React + TypeScript + Vite PWA (`vite-plugin-pwa`, `chessground`, `chess.js`, `ts-fsrs`, Dexie). `web/device-test/` is the Phase 0 device check page |
| `server/` | Python 3.12, FastAPI, `python-chess`, native Stockfish, `maia3` (pinned commit), Postgres 16 job queue, APScheduler |
| `server/config/coach.toml` | All tunables (§30) |
| `server/phase0/` | Phase 0 spikes and benchmarks (not product code) |
| `server/tests/` | Tests and golden fixtures |
| `shared/` | JSON Schema contracts → generated TypeScript types and Pydantic models |
| `docker-compose.yml` | Caddy, api, workers, Postgres (Phase 1) |

Hosting (§29): free static host for the PWA (Vercel Hobby or Cloudflare Pages); the engine backend needs real CPU
(free Oracle 2-OCPU Arm VM, paid VPS or home computer: Sam decides). See the hosting section of the Phase 0 report for the current recommendation.

## Phase plan (§27)

| Phase | Theme | Exit gate highlights |
| --- | --- | --- |
| P | Artifact prototype (client-side, claude.ai) | Works on iPhone + iPad Pro; 20 games ≤ 10 min on iPad |
| 0 | Feasibility and verification | Go thresholds in §27; fact register complete |
| 1 | Import, engine analysis, game review | Import fixtures; Win% exact; accuracy within 0.5 of lila; canonical keys; determinism |
| 2 | Detectors, classification, guided training, templates, basic progress | Detector precision ≥ 95%, recall ≥ 70%; ladder state machine tests |
| 3 | Diagnosis, habits, gap report, prescription, sessions, theme puzzles | Glicko-2 test vectors; bootstrap/Wilson/BH tests |
| 4 | Maia findability; server sparring | Sparring ≤ 1 s p95; defense starts holdable |
| 5 | LLM explanations | 300-packet validator suite, 0 invalid |
| 6 | Repertoire + offline drills (MVP complete) | Sync tests; transposition merging |
| 7 | Steered/test opponents, timed drills | 100% steered moves in candidate set |
| 8 | On-device inference | Parity vs upstream on 500 positions × 3 ratings |
| 9 | Calibration and experiments | Each experiment validated or hidden |

## Pinned versions (from Phase 0; see report for checksums)

- Stockfish 18 — tag `sf_18`, commit `cb3d4ee9b47d0c5aae855b12379378ea1439675c`;
  nets `nn-c288c895ea92.nnue` (big) and `nn-37f18f62d772.nnue` (small).
- Maia-3 — `CSSLab/maia3` commit `1e13597c42d4858b7cfd7cfdae01e297263364b2`; weights from Hugging Face
  `UofTCSSLab/Maia3-23M` / `Maia3-5M` (revision to pin once downloadable).
- python-chess 1.11.2 (no SEE function — implement and unit-test our own; use `fen(en_passant="legal")`
  for canonical keys and compute the Zobrist hash from the normalized board).

## Commands

```bash
# Phase 0 tests
cd server && python -m pytest -q tests
# Pipeline benchmark (needs a Stockfish 18 binary and a PGN of Sam's games)
STOCKFISH=/path/to/stockfish python server/phase0/pipeline_bench.py --pgn games.pgn --me turners1110 --out out.jsonl
```
