"""Canonical position identity (spec v2.2 §8.6): placement, side to move, castling, legal en passant only;
counters ignored; transpositions merge; Zobrist computed from the normalized position."""

import chess
import chess.polyglot

from coach.positions import fen_norm, position_key


def board_after(*sans, fen=chess.STARTING_FEN):
    b = chess.Board(fen)
    for s in sans:
        b.push_san(s)
    return b


def test_counters_ignored():
    a = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    b = chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 7 42")
    assert fen_norm(a) == fen_norm(b)
    assert position_key(a) == position_key(b)


def test_transpositions_merge():
    a = board_after("Nf3", "Nf6", "g3", "g6")
    b = board_after("g3", "g6", "Nf3", "Nf6")
    assert fen_norm(a) == fen_norm(b)
    assert position_key(a)[1] == position_key(b)[1]


def test_ep_square_dropped_when_no_capture_possible():
    b = board_after("e4")  # e3 is not capturable: no black pawn on d4/f4
    assert fen_norm(b).split(" ")[3] == "-"
    assert fen_norm(b) == fen_norm(chess.Board("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"))


def test_ep_square_kept_when_capture_legal():
    b = board_after("e4", "a6", "e5", "d5")  # exd6 e.p. is legal
    assert fen_norm(b).split(" ")[3] == "d6"
    plain = chess.Board(b.fen().replace(" d6 ", " - "))
    assert fen_norm(b) != fen_norm(plain)
    assert position_key(b)[1] != position_key(plain)[1]


def test_ep_square_dropped_when_capture_pseudo_legal_but_pinned():
    # White pawn e5 is pinned on the 5th rank by the rook on h5 to the king on a5: exd6 would expose the king.
    b = chess.Board("4k3/3p4/8/K3P2r/8/8/8/8 b - - 0 1")
    b.push_san("d5")
    assert b.ep_square is not None                    # pseudo-legal ep square set
    assert fen_norm(b).split(" ")[3] == "-"           # but not part of the key
    # python-chess's polyglot hash would include the pseudo-legal square; ours must not
    normalized = chess.Board(fen_norm(b) + " 0 1")
    assert position_key(b)[1] == chess.polyglot.zobrist_hash(normalized)


def test_castling_rights_matter():
    a = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w Kkq - 0 1")
    assert fen_norm(a) != fen_norm(b)


def test_side_to_move_matters():
    a = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    b = chess.Board("4k3/8/8/8/8/8/8/4K3 b - - 0 1")
    assert fen_norm(a) != fen_norm(b)


def test_key_is_signed_64_bit_for_postgres_bigint():
    _, z = position_key(board_after("d4", "d5", "c4"))
    assert -(2**63) <= z < 2**63
