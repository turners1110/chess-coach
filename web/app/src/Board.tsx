import { Chessground } from "@lichess-org/chessground";
import type { Api } from "@lichess-org/chessground/api";
import type { DrawShape } from "@lichess-org/chessground/draw";
import type { Key } from "@lichess-org/chessground/types";
import { useEffect, useRef } from "react";

export interface Arrow { from: string; to: string; brush: "green" | "red" | "blue" | "yellow" }

// View-only board for review (Phase 1). Arrows: green = best move, red = your move.
export function Board({ fen, orientation, lastMove, arrows = [] }: { fen: string; orientation: "white" | "black"; lastMove?: [string, string]; arrows?: Arrow[] }) {
  const el = useRef<HTMLDivElement>(null);
  const cg = useRef<Api | null>(null);
  useEffect(() => {
    if (!el.current) return;
    cg.current = Chessground(el.current, { viewOnly: true, coordinates: true, animation: { enabled: true, duration: 150 } });
    return () => cg.current?.destroy();
  }, []);
  useEffect(() => {
    const shapes: DrawShape[] = arrows.map((a) => ({ orig: a.from as Key, dest: a.to as Key, brush: a.brush }));
    cg.current?.set({ fen, orientation, lastMove: lastMove as Key[] | undefined });
    cg.current?.setAutoShapes(shapes);
  }, [fen, orientation, lastMove?.[0], lastMove?.[1], JSON.stringify(arrows)]);
  return <div className="board-wrap"><div ref={el} className="cg-wrap" /></div>;
}
