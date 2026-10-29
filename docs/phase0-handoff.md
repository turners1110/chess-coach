# Phase 0 handoff (for the next session)

The first Phase 0 session could not reach the hosts below. Network access was then widened, but only new
sessions pick it up. Everything else is done and recorded in `docs/phase0-report.md` (status: PARTIAL).

## 0. Check access first

```bash
for u in https://api.chess.com/pub/player/turners1110 https://huggingface.co/api/models/UofTCSSLab/Maia3-23M \
  https://database.lichess.org/ "https://tablebase.lichess.org/standard?fen=4k3/6KP/8/8/8/8/7p/8_w_-_-_0_1" \
  https://explorer.lichess.org/masters https://docs.oracle.com/; do
  printf "%s %s\n" "$(curl -s -o /dev/null -w '%{http_code}' -m 15 "$u")" "$u"; done
```

## 1. Rebuild the tools (the container is fresh)

```bash
# Stockfish 18 (nets come from GitHub's media host; tests.stockfishchess.org may be blocked)
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch sf_18 https://github.com/official-stockfish/Stockfish ~/sf18
cd ~/sf18/src
curl -sSo nn-c288c895ea92.nnue https://media.githubusercontent.com/media/official-stockfish/networks/master/nn-c288c895ea92.nnue
curl -sSo nn-37f18f62d772.nnue https://raw.githubusercontent.com/official-stockfish/networks/master/nn-37f18f62d772.nnue
sha256sum *.nnue   # must match docs/phase0-report.md §4
make -j"$(nproc)" profile-build ARCH=x86-64-avx512 COMP=gcc   # or x86-64-bmi2 if no AVX-512
# Python env (torch from PyPI is large; allow ~20 min)
python3.12 -m venv ~/venv && ~/venv/bin/pip install chess numpy torch pytest huggingface-hub
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/CSSLab/maia3 ~/maia3 && git -C ~/maia3 checkout 1e13597c42d4858b7cfd7cfdae01e297263364b2
~/venv/bin/pip install -e ~/maia3
```

## 2. Remaining Appendix B work, in order (serial chess.com requests only, §7.2)

1. **B1/B2 chess.com** — UA from `coach.toml [sync] user_agent`. Fetch `/games/archives`, then every month
   serially with ETag. Count games by `time_class` (all time and last 90 days). Re-fetch 3 old months and compare
   ETag + body hash. Request once without UA and record the status. Check that the current month contains no
   unfinished game (every game has a result tag and end_time). Write `out/games.pgn` (rated rapid+blitz).
2. **B5 pipeline**: `STOCKFISH=~/sf18/src/stockfish ~/venv/bin/python server/phase0/pipeline_bench.py --pgn out/rapid_sample.pgn --me turners1110 --out out/pipeline.jsonl`
   (20 recent rapid games; also a blitz sample). Report single-core s/game and throughput with `engine.workers`.
3. **B5 accuracy**: `~/venv/bin/python server/phase0/accuracy_bench.py --moves out/pipeline.jsonl --out out/accuracy.jsonl`
   (500 positions vs 50M nodes; several CPU-hours). If the pipeline misses 60 s/game, repeat with lower
   `first_nodes` (e.g. 300k) and report the accuracy trade-off.
4. **B6 Maia**: download `UofTCSSLab/Maia3-23M` and `-5M` (pin the HF revision, record SHA-256 and the weight
   license from the model card), then `server/phase0/maia_bench.py --checkpoint ...` on the real games.
5. **Golden fixtures**: game accuracy for 3 real games via `server/phase0/lila_accuracy.py`, saved to
   `server/tests/fixtures/accuracy_golden.json`.
6. **B8 puzzles**: download `lichess_db_puzzle.csv.zst`, record its SHA-256 and row count, build a 500-puzzle pack
   (`Popularity ≥ 80`, `NbPlays ≥ 500`, themes matching Sam's flagged motifs).
7. **B9 explorer**: test `explorer.lichess.org/lichess` with and without a token (spec says OAuth2). Size the fallback:
   stream part of one monthly Lichess dump and time the 1400–2000 filter.
8. **B10 tablebase**: time 50 API lookups (serial). Download the Syzygy 3-4-5 set if a host allows it and record its size.
9. **Backfill estimate** = total analyzable games × measured s/game ÷ workers (on the target host).
10. Confirm the Oracle free-tier limits on docs.oracle.com.
11. Finish `docs/phase0-report.md` (GO / NO-GO). Then stop and wait for Sam's go-ahead. **Do not start Phase 1.**

## 3. Waiting on Sam

- Device tests on the iPhone and the iPad Pro using `web/device-test/` served over HTTPS (GitHub Pages if the
  repo is public, or Cloudflare Pages). For the push test, a VAPID key pair is needed: generate a new one and
  replace the public key in `index.html`; keep the private key out of git.
- Hosting decision (free Oracle 2-OCPU vs paid options in the report).
- Stockfish 18 vs 19 (edit E3), and whether to create a Lichess account for the explorer token.
