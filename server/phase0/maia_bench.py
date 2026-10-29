"""Phase 0 Maia-3 benchmark: analysis throughput per game and p95 single-move latency (sparring).

Inference cost does not depend on weight values, so with --random-weights this times the exact
23M / 5M architectures from CSSLab/maia3 even when the checkpoints cannot be downloaded.
Probabilities from random weights are meaningless; only timings and shapes are reported.

Analysis scope per game (spec §11): every Sam move scored at the unlock-rating grid
(A-200 … A+400, step 100 → 7 ratings) with the full legal distribution, plus flagged opponent moves
at one rating. Optionally the anchor grid (600–2400, step 50 → 37 ratings) for Sam's moves.

Usage: python maia_bench.py --model 23m --pgn games.pgn --me turners1110 [--random-weights | --checkpoint X.pt]
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import time
import tomllib
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import chess
import chess.pgn
import torch

CONFIG = Path(__file__).resolve().parents[1] / "config" / "coach.toml"


def load_maia(model_name: str, checkpoint: str | None, threads: int):
    from maia3.dataset import get_historical_tokens, get_legal_moves_mask, tokenize_board
    from maia3.model_registry import resolve_model_spec
    from maia3.models import MAIA3Model
    from maia3.utils import get_all_possible_moves

    torch.set_num_threads(threads)
    spec = resolve_model_spec(model_name)
    cfg = SimpleNamespace(**spec.config, device="cpu")
    model = MAIA3Model(cfg)
    if checkpoint:
        sd = torch.load(checkpoint, map_location="cpu", weights_only=True)
        sd = sd.get("model_state_dict", sd)
        model.load_state_dict({k.replace("smolgen", "gab"): v for k, v in sd.items()}, strict=False)
    model.eval()
    moves = get_all_possible_moves()
    idx = {m: i for i, m in enumerate(moves)}
    n_params = sum(p.numel() for p in model.parameters())
    return SimpleNamespace(model=model, cfg=cfg, idx=idx, tok=tokenize_board, hist=get_historical_tokens,
                           mask=get_legal_moves_mask, n_params=n_params, spec=spec)


def encode(m, history: deque, board: chess.Board):
    t = m.hist(history, m.cfg, base=0.0, inc=0.0, clk_left_before=0.0, clk_ponder=0.0)
    return t, m.mask(board, m.idx)


@torch.no_grad()
def forward(m, tokens, masks, self_elos, oppo_elos):
    logits, _, _ = m.model(tokens, self_elos, oppo_elos)
    logits = logits.masked_fill(~masks, float("-inf"))
    return torch.softmax(logits, dim=-1)  # full legal-move distribution (§11.3 F)


def game_positions(m, game, me):
    my_color = chess.WHITE if game.headers.get("White", "").lower() == me.lower() else chess.BLACK
    board = game.board()
    history = deque([m.tok(board)], maxlen=m.cfg.history)
    out = []
    for move in game.mainline_moves():
        out.append((board.turn == my_color, *encode(m, history, board)))
        board.push(move)
        history.append(m.tok(board))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="23m")
    ap.add_argument("--checkpoint")
    ap.add_argument("--random-weights", action="store_true")
    ap.add_argument("--pgn", required=True)
    ap.add_argument("--me", required=True)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--games", type=int, default=None)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--anchor-grid", action="store_true")
    ap.add_argument("--opp-flag-share", type=float, default=0.2,
                    help="share of opponent moves assumed flagged (measured share replaces this once the pipeline has run)")
    a = ap.parse_args()
    if not a.checkpoint and not a.random_weights:
        sys.exit("need --checkpoint or --random-weights")
    toml = tomllib.load(open(CONFIG, "rb"))
    mc, an = toml["maia"], toml["anchor"]
    m = load_maia(a.model, a.checkpoint, a.threads)
    anchor = 1100  # placeholder rating for timing only; value does not affect cost
    unlock = list(range(anchor + mc["unlock_min_offset"], anchor + mc["unlock_max_offset"] + 1, mc["unlock_step"]))
    grid = list(range(an["search_min"], an["search_max"] + 1, an["search_step"])) if a.anchor_grid else []

    games = []
    with open(a.pgn) as f:
        while a.games is None or len(games) < a.games:
            g = chess.pgn.read_game(f)
            if g is None:
                break
            games.append(g)
    if not games:
        sys.exit("no games")

    per_game = []
    for g in games:
        pos = game_positions(m, g, a.me)
        jobs = []
        for i, (mine, tok, mask) in enumerate(pos):
            ratings = sorted(set(unlock + grid)) if mine else ([anchor] if (i % round(1 / a.opp_flag_share) == 0) else [])
            jobs += [(tok, mask, r) for r in ratings]
        t0 = time.perf_counter()
        for s in range(0, len(jobs), a.batch):
            chunk = jobs[s:s + a.batch]
            tokens = torch.stack([j[0] for j in chunk])
            masks = torch.stack([j[1] for j in chunk])
            elos = torch.tensor([j[2] for j in chunk], dtype=torch.long)
            forward(m, tokens, masks, elos, elos)
        per_game.append({"plies": len(pos), "forward_passes": len(jobs), "seconds": time.perf_counter() - t0})

    # Sparring latency: one position, batch 1, end to end (tokenize + mask + forward + sample).
    lat = []
    board = chess.Board()
    trials = toml["phase0"]["maia_latency_trials"]
    g0 = list(games[0].mainline_moves())
    for t in range(trials):
        board = games[0].board()
        for mv in g0[: (t % max(1, len(g0)))]:
            board.push(mv)
        if board.is_game_over():
            continue
        t0 = time.perf_counter()
        hist = deque([m.tok(board)], maxlen=m.cfg.history)
        tok, mask = encode(m, hist, board)
        p = forward(m, tok.unsqueeze(0), mask.unsqueeze(0), torch.tensor([anchor + mc["sparring_offset"]]), torch.tensor([anchor]))
        torch.multinomial(p[0], 1)
        lat.append(time.perf_counter() - t0)
    lat.sort()
    res = {
        "model": m.spec.name, "params": m.n_params, "weights": "random (timing only)" if a.random_weights else a.checkpoint,
        "threads": a.threads, "batch": a.batch, "anchor_grid": a.anchor_grid, "games": len(per_game),
        "mean_plies": statistics.mean(x["plies"] for x in per_game),
        "mean_forward_passes": statistics.mean(x["forward_passes"] for x in per_game),
        "mean_s_per_game": round(statistics.mean(x["seconds"] for x in per_game), 2),
        "max_s_per_game": round(max(x["seconds"] for x in per_game), 2),
        "latency_ms_p50": round(1000 * lat[len(lat) // 2], 1),
        "latency_ms_p95": round(1000 * lat[int(len(lat) * 0.95) - 1], 1),
        "latency_ms_max": round(1000 * lat[-1], 1),
        "torch": torch.__version__,
    }
    print(json.dumps(res))


if __name__ == "__main__":
    main()
