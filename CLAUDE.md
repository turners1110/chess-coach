# Chess Coach — notes for Claude Code

Personal chess coach for one player (chess.com `turners1110`, "Sam"). The source of truth is
**`docs/chess-coach-spec-v2.2.md`**. If anything here or in a chat message conflicts with the spec,
the spec wins; tell Sam about the conflict. Phase 0 findings and proposed spec edits are in
`docs/phase0-report.md`. Do not edit the spec yourself; propose edits there.

## Current state

- **Phase 0: complete** (`docs/phase0-report.md`). Spec v2.2 applies Sam's approved edits (E1–E19).
- **Phase P prototype: published** (claude.ai artifact, source `web/prototype/`); its `sessions` collection holds ladder findings.
- **Phase 1: built (2026-10-31), awaiting Sam's install and phone check.** Backend runs on Sam's home computer
  (`docs/setup-home-computer.md`, Docker Compose). Exit gates pass in tests: import fixtures, Win% and accuracy
  golden fixtures, canonical keys, determinism. Report card v1 (§12.10) with a 1500-level reference set is included.
- Do **not** start Phase 2 until Sam confirms Phase 1 works on his iPhone.

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
| `web/app/` | React + TypeScript + Vite PWA (`vite-plugin-pwa`, `@lichess-org/chessground`, `chess.js`; later `ts-fsrs`, Dexie). `web/device-test/` is the Phase 0 device check page; `web/prototype/` the Phase P artifact |
| `server/` | Python 3.12, FastAPI, `python-chess`, native Stockfish, `maia3` (pinned commit), Postgres 16 job queue, APScheduler |
| `server/config/coach.toml` | All tunables (§30) |
| `server/phase0/` | Phase 0 spikes and benchmarks (not product code) |
| `server/tests/` | Tests and golden fixtures |
| `shared/` | JSON Schema contracts → generated TypeScript types and Pydantic models (not generated yet: Phase 1 types are hand-written in `web/app/src/types.ts`) |
| `docker-compose.yml` | Postgres, api (also serves the app), worker, on Sam's home computer |

Hosting (§29): Sam's home computer runs everything (Docker Compose; phone access via Tailscale HTTPS or home Wi-Fi).
The app can alternatively be served from Vercel Hobby with `COACH_ALLOWED_ORIGINS` set; the engine cannot run on Vercel.

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
# Tests (Postgres 16 at postgresql://coach:coach@localhost/coach_test; engine tests need STOCKFISH)
cd server && STOCKFISH=/path/to/stockfish python -m pytest -q tests
# Local API (serves web/app/dist when COACH_WEB_DIST is set) and worker
DATABASE_URL=postgresql://coach:coach@localhost/coach COACH_PASSWORD_HASH='…' uvicorn coach.api:app --port 8000
STOCKFISH=/path/to/stockfish python -m coach.worker --workers 2
# Phone app
cd web/app && npm ci && npm run build      # npm run dev proxies /api to :8000
# Home computer (everything)
docker compose up -d --build               # see docs/setup-home-computer.md
```

## Code map (Phase 1)

| Module | Job |
| --- | --- |
| `coach/config.py` | Loads `coach.toml` |
| `coach/winpct.py`, `coach/accuracy.py`, `coach/positions.py` | Win%, lila accuracy, canonical keys |
| `coach/chesscom.py`, `coach/importer.py` | Serial chess.com client; archives → games → plies; analysis jobs |
| `coach/jobs.py`, `coach/worker.py` | Postgres job queue; worker processes and the one-thread sync scheduler |
| `coach/analysis.py`, `coach/tablebase.py` | §8 passes with `engine_evals` cache, tablebase, labels, GRI |
| `coach/review.py` | §12.1 review moments |
| `coach/reportcard.py`, `coach/reference.py` | §12.10 report card and the goal-level reference crawl |
| `coach/api.py`, `coach/passwd.py` | FastAPI app (login, games, review, report card, sync) |
| `coach/migrations/` | SQL migrations, applied in order by `coach.db.migrate()` |
