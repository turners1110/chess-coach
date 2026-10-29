# Phase P prototype (spec §27)

One self-contained artifact page: analysis of Sam's recent games with Stockfish 18 lite (WASM, one thread,
in a Web Worker), the Phase P subset of §10 error rules, own-game puzzles and Think-First threat checks with
the §17.2 feedback ladder, §17.5 credit, the §17.6 mastery scheduler and a raw weakness summary.

- `src/app.html`: page source. Tunables are in its `CONFIG` object, mirrored in `server/config/coach.toml [prototype]`.
- `games.json`: snapshot of Sam's 25 most recent rated rapid and 25 blitz games (api.chess.com, 2026-10-29).
  The artifact sandbox blocks requests to other hosts (CSP), so the page cannot call chess.com itself;
  newer games can be pasted as PGN.
- `./fetch_vendor.sh && python3 build.py` → `dist/` (index.html, stockfish.js, stockfish.wasm, games.json),
  which is what gets published.
- Storage: the artifact `db` capability (only the owner reads and writes), else localStorage.
  Collections: `games`, `cards`, `sessions` (attempt events per session, plus Sam's "was it useful" rating), `meta/perf`.
