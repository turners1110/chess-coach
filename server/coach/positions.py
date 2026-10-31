"""Canonical position identity (spec §8.6)."""

from __future__ import annotations

import chess
import chess.polyglot


def fen_norm(board: chess.Board) -> str:
    """Placement, side to move, castling rights, and the en passant square only when an en passant capture
    is legal. Halfmove and fullmove counters are dropped."""
    return " ".join(board.fen(en_passant="legal").split(" ")[:4])


def position_key(board: chess.Board) -> tuple[str, int]:
    """(fen_norm, signed 64-bit Zobrist). The hash is computed from the normalized position, because
    python-chess's Polyglot hash includes pseudo-legal en passant squares. The string decides equality."""
    norm = fen_norm(board)
    z = chess.polyglot.zobrist_hash(chess.Board(norm + " 0 1"))
    return norm, z - 2**64 if z >= 2**63 else z
