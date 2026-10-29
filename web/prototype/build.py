"""Builds the Phase P artifact into web/prototype/dist/: index.html (chess.js and piece images inlined),
stockfish.js + stockfish.wasm (published beside the page; the worker loads them), games.json.
Run ./fetch_vendor.sh first."""

import base64
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
V, DIST = HERE / "vendor", HERE / "dist"
DIST.mkdir(exist_ok=True)
chess_js = (V / "chess.js").read_text()
chess_js = re.sub(r"^export \{[^}]*\};\s*$", "", chess_js, flags=re.M)  # inline: drop the module export
chess_js = re.sub(r"^//# sourceMappingURL=.*$", "", chess_js, flags=re.M)
pieces = {p.stem: "data:image/svg+xml;base64," + base64.b64encode(p.read_bytes()).decode() for p in sorted((V / "pieces").glob("*.svg"))}
html = (HERE / "src" / "app.html").read_text()
html = html.replace("/*__CHESS_JS__*/", "// chess.js 1.4.0 (BSD-2-Clause, github.com/jhlywa/chess.js), inlined by build.py\n" + chess_js)
html = html.replace("__PIECES_JSON__", json.dumps(pieces))
(DIST / "index.html").write_text(html)
shutil.copy(V / "stockfish.js", DIST / "stockfish.js")
shutil.copy(V / "stockfish.wasm", DIST / "stockfish.wasm")
shutil.copy(HERE / "games.json", DIST / "games.json")
print({f.name: f.stat().st_size for f in DIST.iterdir()})
