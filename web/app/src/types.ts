// Response shapes of server/coach/api.py
export type Result = "win" | "loss" | "draw";
export interface GameRow {
  id: number; played_at: string; time_class: string; time_control: string; color: "w" | "b";
  opponent: string; opp_rating: number; my_rating: number; result: Result; termination: string | null;
  opening: string | null; eco: string | null; accuracy_me: number | null; accuracy_opp: number | null;
  analysis_status: "pending" | "done" | "failed" | "skipped"; n_plies: number;
  blunders: number; mistakes: number; inaccuracies: number; largest_swing: number | null;
}
export interface Ply { ply: number; san: string; uci: string; fen_before: string; clock_ms: number | null; time_spent_ms: number | null; mover_is_me: boolean }
export interface Score {
  ply: number; mover_is_me: boolean; best_uci: string; win_best: number; win_played: number; win_loss: number;
  eval_delta: number; final_pass: string; class: "good" | "inaccuracy" | "mistake" | "blunder"; labels: string[];
  gri: number; context_tags: string[]; best_san: string[]; refutation_san: string[];
}
export interface Moment extends Score { kind: "largest_swing" | "important" | "unpunished"; reply_ply?: number; reply_loss?: number }
export interface GameDetail { game: GameRow & { opening: string | null }; plies: Ply[]; scores: Score[]; moments: Moment[] }
export interface MetricRow {
  key: string; label: string; better: "higher" | "lower"; unit: string; explain: string;
  you: number | null; ci: [number, number] | null; your_level: number | null; goal: number | null;
  progress: number | null; grade: "A" | "B" | "C" | "D" | "F" | null;
}
export interface Hypothesis { belief: string; measure: string; value: number | null; unit: string; n?: number }
export interface ReportCard {
  time_class: string; status: "ok" | "not_enough_games"; games: number; min_games?: number; goal: number;
  reference_games?: number; metrics?: MetricRow[]; hypotheses?: Hypothesis[]; your_rating?: number; opponent_rating?: number;
}
export interface Status {
  games: { time_class: string; analysis_status: string; n: number }[]; jobs: { kind: string; status: string; n: number }[];
  last_sync: string | null; ratings: { time_class: string; rating: number; date: string }[]; goal: number;
}
