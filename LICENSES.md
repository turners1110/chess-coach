# Licenses (draft, Phase 0)

Every dependency, model, weight file and browser bundle, its license, and **where it runs**.
Spec §29: browser-shipped GPL/AGPL code counts as distribution, even to one user; server-side AGPL code
used over a network triggers AGPL §13 (offer the source to network users).
**Engineering default:** keep the complete source of this app available to every user under
GPL-3.0-or-later-compatible terms (in practice AGPL-3.0, because of Maia-3). This is not legal advice;
review the obligations for this exact architecture before deployment.

Status: **Confirmed** = read from the project's LICENSE file or registry metadata on 2026-10-29.
**Unverified** = could not be read in Phase 0 (host blocked or not yet chosen).

## Server-side only

| Component | Version / pin | License | Status | Notes |
| --- | --- | --- | --- | --- |
| Stockfish | 18, tag `sf_18` (`cb3d4ee9`) | GPL-3.0 | Confirmed (`Copying.txt`) | Native binary built from source. Running it on our server is not distribution |
| Stockfish NNUE nets `nn-c288c895ea92`, `nn-37f18f62d772` | — | CC0-1.0 | Confirmed (`official-stockfish/networks` README) | Embedded in the binary by the build |
| Maia-3 inference code (`CSSLab/maia3`) | commit `1e13597c` | AGPL-3.0 | Confirmed (`LICENSE`) | Network service → AGPL §13: our server source must be offered to users |
| Maia-3 weights 23M / 5M (`UofTCSSLab/Maia3-23M`, `-5M`) | HF revision TBD | **Unverified** | huggingface.co blocked in Phase 0 | Read the model-card license before downloading. Ports state AGPL-3.0 |
| python-chess (`chess`) | 1.11.2 | GPL-3.0-or-later | Confirmed (PyPI) | |
| PyTorch (`torch`) | 2.15.0 | BSD-3-Clause (plus bundled permissive licenses) | Confirmed (PyPI `license_expression`) | CPU wheels exist for x86-64 and aarch64 |
| NumPy | 2.5.x | BSD-3-Clause and others (permissive) | Confirmed (PyPI) | |
| huggingface-hub | 2.3.x | Apache-2.0 | Confirmed (PyPI) | Weight download only; can be avoided by pinning local files |
| FastAPI | 0.162.x | MIT | Confirmed (PyPI) | |
| Pydantic | 2.14.x | MIT | Confirmed (PyPI) | |
| Uvicorn | 0.54.x | BSD-3-Clause | Confirmed (PyPI) | |
| APScheduler | 3.11.x | MIT | Confirmed (PyPI) | |
| psycopg | 3.3.x | LGPL-3.0-only | Confirmed (PyPI) | Dynamic use from Python; no static linking |
| argon2-cffi | 25.1.x | MIT | Confirmed (PyPI) | |
| anthropic (Claude API SDK) | 2.3.x | Apache-2.0 | Confirmed (PyPI) | Phase 5 |
| PostgreSQL | 16 | PostgreSQL License (permissive) | Unverified (not yet installed) | |
| Caddy | 2.x | Apache-2.0 | Unverified (not yet chosen version) | |
| Syzygy 3-4-5 tablebase files | — | Unverified | tablebase hosts blocked | Freely redistributed by Lichess and others; confirm terms before mirroring |
| Lichess tablebase API | — | Service (no license); no auth | Confirmed (lichess-org/api spec) | |
| Lichess puzzle database (`lichess_db_puzzle.csv`) | monthly export | CC0-1.0 | Confirmed (lichess-org/database `web/index.html.tpl`) | Puzzle subset also ships to the browser as data (CC0 allows it) |
| Lichess open database (games) | monthly export | CC0-1.0 | Confirmed (same page) | Only for the fallback theory reference |
| Lichess opening explorer API | — | Service; OAuth2 token required | Confirmed (lichess-org/api spec) | Needs a Lichess account (Sam's decision) |
| `lila` accuracy algorithm (ported, not copied verbatim) | `898ad2cd` | AGPL-3.0 | Confirmed | A port of AGPL code is a derivative; compatible with our AGPL default. Cite the source in code |
| Glicko-2 reference vectors from `glicko2` (npm, mmai/glicko2js) | 1.2.2 | MIT | Confirmed | Test data only |

## Ships to the browser (distribution)

| Component | Version | License | Status | Notes |
| --- | --- | --- | --- | --- |
| React, React DOM | 19.x | MIT | Confirmed (npm) | |
| Vite (build tool) | 8.x | MIT | Confirmed (npm) | Build only; its runtime helpers are MIT |
| vite-plugin-pwa / Workbox | 2.x / 7.x | MIT | Confirmed (npm) | |
| **@lichess-org/chessground** | 10.5.x | **GPL-3.0-or-later** | Confirmed (npm) | The old `chessground` package (9.2.1) is deprecated; use the scoped package. GPL → source of the whole PWA must be offered |
| chess.js | 1.4.x | BSD-2-Clause | Confirmed (npm) | |
| ts-fsrs | 6.0.x | MIT | Confirmed (npm) | |
| Dexie | 4.4.x | Apache-2.0 | Confirmed (npm) | |
| TypeScript (build) | 7.x | Apache-2.0 | Confirmed (npm) | Build only |
| Phase P only: Stockfish WASM (`stockfish` npm, nmrugg/stockfish.js) | 18.0.x or 19.0.x | **GPL-3.0** | Confirmed (npm) | Loaded from a CDN in the artifact prototype; still distribution |
| Phase 8: onnxruntime-web | 1.31.x | MIT | Confirmed (npm) | |
| Phase 8: Stockfish lite WASM | TBD | **GPL-3.0** | Unverified | |
| Phase 8: Maia3-5M weights in ONNX/int8 (`maia3-web`, `chessoracle-maia`, OpenChessCoach) | TBD | **AGPL-3.0** (repos); upstream weight license Unverified | Partly confirmed | Converted weights inherit the upstream weight license; verify before shipping |
| Device test page (`web/device-test`) | — | ours | — | No third-party code |

## Obligations checklist (engineering view, not legal advice)

1. Publish the full source (web + server) under AGPL-3.0 and link it from Settings → About, because the
   browser bundle includes GPL chessground (and later GPL Stockfish WASM and AGPL Maia weights) and the
   server runs AGPL Maia-3 for remote users.
2. Keep each upstream license text in `/licenses/` and in the PWA's About screen.
3. Re-check the Maia-3 weight license on Hugging Face before Phase 4, and before Phase 8 for browser weights.
