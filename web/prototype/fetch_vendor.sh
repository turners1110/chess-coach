#!/usr/bin/env bash
# Fetches the prototype's third-party files into web/prototype/vendor/ and checks their SHA-256.
# Stockfish.js 18.0.8 (nmrugg, GPL-3.0): lite single-threaded WASM build. chess.js 1.4.0 (BSD-2-Clause).
# Pieces: lichess cburnett set (Colin M.L. Burnett, GPLv2+).
set -euo pipefail
cd "$(dirname "$0")"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
mkdir -p vendor/pieces
curl -sSfo "$tmp/sf.tgz" https://registry.npmjs.org/stockfish/-/stockfish-18.0.8.tgz
curl -sSfo "$tmp/cj.tgz" https://registry.npmjs.org/chess.js/-/chess.js-1.4.0.tgz
tar xzf "$tmp/sf.tgz" -C "$tmp" package/bin/stockfish-18-lite-single.js package/bin/stockfish-18-lite-single.wasm
cp "$tmp/package/bin/stockfish-18-lite-single.js" vendor/stockfish.js
cp "$tmp/package/bin/stockfish-18-lite-single.wasm" vendor/stockfish.wasm
tar xzf "$tmp/cj.tgz" -C "$tmp" package/dist/esm/chess.js
cp "$tmp/package/dist/esm/chess.js" vendor/chess.js
for c in w b; do for p in K Q R B N P; do
  curl -sSfo "vendor/pieces/$c$p.svg" "https://raw.githubusercontent.com/lichess-org/lila/master/public/piece/cburnett/$c$p.svg"
done; done
sha256sum -c vendor.sha256
