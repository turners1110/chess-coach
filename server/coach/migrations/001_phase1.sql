-- Phase 1 tables (spec §24). Every table has created_at / updated_at.
CREATE TABLE IF NOT EXISTS players (
  id bigserial PRIMARY KEY,
  chesscom_username text UNIQUE NOT NULL,
  chesscom_player_id bigint,
  settings jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS archives (
  player_id bigint NOT NULL REFERENCES players(id),
  yyyymm text NOT NULL,
  url text NOT NULL,
  etag text,
  last_fetched timestamptz,
  status text NOT NULL DEFAULT 'new',          -- new | done | partial | failed
  error text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, yyyymm)
);
CREATE TABLE IF NOT EXISTS games (
  id bigserial PRIMARY KEY,
  player_id bigint NOT NULL REFERENCES players(id),
  source text NOT NULL DEFAULT 'chesscom',
  chesscom_url text UNIQUE,
  time_class text NOT NULL,
  time_control text NOT NULL,
  rated boolean NOT NULL,
  played_at timestamptz NOT NULL,
  color char(1) NOT NULL,                     -- w | b (Sam's color)
  my_rating int, opp_rating int, opponent text,
  result text NOT NULL,                       -- win | loss | draw (for Sam)
  termination text,
  eco text, opening text,
  pgn text NOT NULL,
  n_plies int,
  parse_status text NOT NULL DEFAULT 'ok',     -- ok | failed
  parse_error text,
  analysis_status text NOT NULL DEFAULT 'pending', -- pending | skipped | done | failed
  accuracy_me real, accuracy_opp real,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS games_played ON games (player_id, time_class, played_at DESC);
CREATE TABLE IF NOT EXISTS positions (
  fen_norm text PRIMARY KEY,
  zobrist bigint NOT NULL,
  phase text,
  structure_tags text[],
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS positions_zobrist ON positions (zobrist);
CREATE TABLE IF NOT EXISTS plies (
  game_id bigint NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  ply int NOT NULL,
  fen_norm_before text NOT NULL REFERENCES positions(fen_norm),
  fen_before text NOT NULL,
  san text NOT NULL, uci text NOT NULL,
  clock_ms int, time_spent_ms int,
  mover_is_me boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (game_id, ply)
);
CREATE TABLE IF NOT EXISTS engine_evals (
  fen_norm text NOT NULL,
  pass text NOT NULL,                          -- first | played:<uci> | deep | boundary | threat
  engine_version text NOT NULL, build_hash text NOT NULL,
  nodes int NOT NULL, settings jsonb NOT NULL, cpu_model text,
  lines jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (fen_norm, pass, engine_version, build_hash, nodes)
);
CREATE TABLE IF NOT EXISTS tb_results (
  fen_norm text PRIMARY KEY, wdl int, dtz int, category text, source text NOT NULL,
  best_uci text, moves jsonb,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS move_scores (
  game_id bigint NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  ply int NOT NULL,
  mover_is_me boolean NOT NULL,
  best_uci text, win_best real, win_played real, win_loss real, first_win_loss real, eval_delta real,
  final_pass text, class text, labels text[] NOT NULL DEFAULT '{}', gap real,
  gri real, context_tags text[] NOT NULL DEFAULT '{}', best_line text[], refutation text[],
  analysis_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (game_id, ply)
);
CREATE TABLE IF NOT EXISTS ratings_history (
  player_id bigint NOT NULL REFERENCES players(id),
  time_class text NOT NULL, date date NOT NULL, rating int NOT NULL, smoothed real,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (player_id, time_class, date)
);
CREATE TABLE IF NOT EXISTS jobs (
  id bigserial PRIMARY KEY,
  kind text NOT NULL,
  key text UNIQUE NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}',
  priority int NOT NULL DEFAULT 0,
  sort_key double precision NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'queued',       -- queued | running | done | failed
  attempts int NOT NULL DEFAULT 0,
  last_error text,
  versions jsonb NOT NULL DEFAULT '{}',
  run_after timestamptz NOT NULL DEFAULT now(),
  lease_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_ready ON jobs (status, priority DESC, sort_key DESC);
CREATE TABLE IF NOT EXISTS auth_sessions (
  token_hash text PRIMARY KEY,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
