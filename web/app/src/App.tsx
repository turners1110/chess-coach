import { Chess } from "chess.js";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiBase, AuthError, login, logout, setApiBase, token } from "./api";
import { Board, type Arrow } from "./Board";
import type { GameDetail, GameRow, Moment, ReportCard, Score, Status } from "./types";

type Route = { name: "games" } | { name: "game"; id: number } | { name: "card" } | { name: "status" };

function parseHash(): Route {
  const h = location.hash.replace(/^#\/?/, "");
  const m = h.match(/^game\/(\d+)$/);
  if (m) return { name: "game", id: +m[1] };
  if (h === "card") return { name: "card" };
  if (h === "status") return { name: "status" };
  return { name: "games" };
}

export function App() {
  const [authed, setAuthed] = useState(!!token());
  const [route, setRoute] = useState<Route>(parseHash());
  useEffect(() => {
    const f = () => setRoute(parseHash());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  const onAuthError = useCallback((e: unknown) => { if (e instanceof AuthError) setAuthed(false); }, []);
  if (!authed) return <Login onDone={() => setAuthed(true)} />;
  const tab = route.name === "game" ? "games" : route.name;
  return (
    <div className="app">
      <header className="top"><h1>Chess Coach</h1></header>
      <main>
        {route.name === "games" && <Games onAuthError={onAuthError} />}
        {route.name === "game" && <Review id={route.id} onAuthError={onAuthError} />}
        {route.name === "card" && <Card onAuthError={onAuthError} />}
        {route.name === "status" && <StatusView onAuthError={onAuthError} onLogout={() => setAuthed(false)} />}
      </main>
      <nav className="tabs" aria-label="Sections">
        {([["games", "Games"], ["card", "Report card"], ["status", "Status"]] as const).map(([k, label]) => (
          <a key={k} href={`#/${k === "games" ? "" : k}`} aria-current={tab === k ? "page" : undefined}>{label}</a>
        ))}
      </nav>
    </div>
  );
}

function useLoad<T>(path: string | null, onAuthError: (e: unknown) => void) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    setError(null);
    api<T>(path).then((d) => live && setData(d)).catch((e) => { onAuthError(e); if (live) setError(e.message); });
    return () => { live = false; };
  }, [path, n, onAuthError]);
  return { data, error, reload: () => setN((x) => x + 1) };
}

function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [server, setServer] = useState(apiBase());
  return (
    <div className="app narrow">
      <h1>Chess Coach</h1>
      <form className="panel stack" onSubmit={async (e) => {
        e.preventDefault(); setErr(null); setApiBase(server);
        try { await login(pw); onDone(); } catch (x) { setErr((x as Error).message); }
      }}>
        <label htmlFor="pw">Password</label>
        <input id="pw" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} />
        <details><summary className="small">Server address</summary>
          <label htmlFor="srv" className="small muted">Leave empty when this page comes from your home computer.</label>
          <input id="srv" type="url" placeholder="https://…" value={server} onChange={(e) => setServer(e.target.value)} />
        </details>
        {err && <p className="bad">{err}</p>}
        <button className="primary" type="submit">Sign in</button>
      </form>
    </div>
  );
}

const fmtDate = (s: string) => new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
const resultLabel = { win: "Won", loss: "Lost", draw: "Draw" } as const;

function Games({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [tc, setTc] = useState<string>("all");
  const { data, error } = useLoad<GameRow[]>(`/api/games?limit=100${tc === "all" ? "" : `&time_class=${tc}`}`, onAuthError);
  return (
    <section className="stack">
      <div className="seg" role="tablist">
        {["all", "blitz", "rapid"].map((k) => <button key={k} role="tab" aria-selected={tc === k} onClick={() => setTc(k)}>{k === "all" ? "All" : k[0].toUpperCase() + k.slice(1)}</button>)}
      </div>
      {error && <p className="bad">{error}</p>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && data.length === 0 && <p className="muted">No games yet. The first sync runs a few minutes after the server starts.</p>}
      <ul className="games">
        {data?.map((g) => (
          <li key={g.id}><a className="game panel" href={`#/game/${g.id}`}>
            <span className={`res res-${g.result}`}>{resultLabel[g.result]}</span>
            <span className="who">{g.opponent} <span className="muted">({g.opp_rating})</span></span>
            <span className="mono acc">{g.accuracy_me != null ? `${g.accuracy_me.toFixed(1)}%` : g.analysis_status === "pending" ? "Analyzing…" : ""}</span>
            <span className="small muted">{fmtDate(g.played_at)} · {g.time_class} · {g.color === "w" ? "White" : "Black"}</span>
            <span className="small mono marks">{g.analysis_status === "done" && <>
              <span className="cls-blunder">{g.blunders}??</span> <span className="cls-mistake">{g.mistakes}?</span> <span className="cls-inaccuracy">{g.inaccuracies}?!</span></>}</span>
          </a></li>
        ))}
      </ul>
    </section>
  );
}

const GLYPH: Record<Score["class"], string> = { good: "", inaccuracy: "?!", mistake: "?", blunder: "??" };
const KIND = { largest_swing: "Largest swing", important: "Also important", unpunished: "Missed punishment" } as const;

function fenAfter(fen: string, uci: string) {
  const c = new Chess(fen);
  c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] });
  return c.fen();
}

function Review({ id, onAuthError }: { id: number; onAuthError: (e: unknown) => void }) {
  const { data, error } = useLoad<GameDetail>(`/api/games/${id}`, onAuthError);
  const [cursor, setCursor] = useState<number | null>(null);   // position index: before ply `cursor`
  const [sel, setSel] = useState<Moment | null>(null);
  useEffect(() => { if (data?.moments[0]) { setSel(data.moments[0]); setCursor(data.moments[0].ply); } else if (data) setCursor(data.plies.length); }, [data]);
  const fens = useMemo(() => {
    if (!data) return [];
    const f = data.plies.map((p) => p.fen_before);
    const last = data.plies[data.plies.length - 1];
    return last ? [...f, fenAfter(last.fen_before, last.uci)] : f;
  }, [data]);
  if (error) return <p className="bad">{error}</p>;
  if (!data || cursor === null) return <p className="muted">Loading…</p>;
  const { game, plies, scores, moments } = data;
  if (game.analysis_status !== "done") return <section className="panel"><h2>Not analyzed yet</h2><p className="muted">This game is in the analysis queue.</p></section>;
  const score = scores[cursor];
  const arrows: Arrow[] = [];
  if (score && sel && sel.ply === cursor) {
    arrows.push({ from: plies[cursor].uci.slice(0, 2), to: plies[cursor].uci.slice(2, 4), brush: "red" });
    if (score.best_uci !== plies[cursor].uci) arrows.push({ from: score.best_uci.slice(0, 2), to: score.best_uci.slice(2, 4), brush: "green" });
  }
  const lastMove = cursor > 0 ? [plies[cursor - 1].uci.slice(0, 2), plies[cursor - 1].uci.slice(2, 4)] as [string, string] : undefined;
  const go = (k: number) => { setCursor(Math.max(0, Math.min(plies.length, k))); setSel(null); };
  return (
    <section className="review">
      <div className="stack">
        <Board fen={fens[cursor]} orientation={game.color === "w" ? "white" : "black"} lastMove={lastMove} arrows={arrows} />
        <div className="row nav">
          <button onClick={() => go(0)} aria-label="Start">⏮</button><button onClick={() => go(cursor - 1)} aria-label="Back">◀</button>
          <span className="mono small">{cursor === 0 ? "Start" : `${Math.ceil(cursor / 2)}${cursor % 2 ? "." : "…"} ${plies[cursor - 1].san}`}</span>
          <button onClick={() => go(cursor + 1)} aria-label="Forward">▶</button><button onClick={() => go(plies.length)} aria-label="End">⏭</button>
        </div>
        <WinGraph scores={scores} cursor={cursor} me={game.color} onPick={go} />
      </div>
      <div className="stack">
        <div className="panel">
          <h2>{resultLabel[game.result]} vs {game.opponent} ({game.opp_rating})</h2>
          <p className="small muted">{fmtDate(game.played_at)} · {game.time_class} {game.time_control} · {game.opening || game.eco}</p>
          <p className="small">Accuracy: you <b className="mono">{game.accuracy_me?.toFixed(1)}%</b>, opponent <span className="mono">{game.accuracy_opp?.toFixed(1)}%</span></p>
        </div>
        <div className="panel stack">
          <h3>Key moments</h3>
          {moments.map((m) => (
            <button key={`${m.kind}-${m.ply}`} className={`moment ${sel?.ply === m.ply ? "on" : ""}`} onClick={() => { setSel(m); setCursor(m.ply); }}>
              <span className="small muted">{KIND[m.kind]}</span>
              <span>Move {Math.floor(m.ply / 2) + 1}: {m.mover_is_me ? "you" : game.opponent} played <b>{plies[m.ply].san}</b> <span className={`cls-${m.class} mono`}>−{m.win_loss.toFixed(1)}</span></span>
            </button>
          ))}
          {sel && <MomentDetail m={sel} plies={plies} />}
        </div>
        <div className="panel"><h3>Moves</h3>
          <ol className="moves">{Array.from({ length: Math.ceil(plies.length / 2) }, (_, k) => (
            <li key={k}><span className="muted mono">{k + 1}.</span>
              {[2 * k, 2 * k + 1].filter((i) => i < plies.length).map((i) => (
                <button key={i} className={`mv ${cursor === i + 1 ? "on" : ""} cls-${scores[i].class}${scores[i].labels.includes("suppressed") ? " sup" : ""}`} onClick={() => go(i + 1)}>
                  {plies[i].san}{scores[i].labels.includes("suppressed") ? "" : GLYPH[scores[i].class]}</button>))}
            </li>))}</ol>
        </div>
      </div>
    </section>
  );
}

function MomentDetail({ m, plies }: { m: Moment; plies: GameDetail["plies"] }) {
  return (
    <dl className="kv small">
      <dt>Win% before → after</dt><dd className="mono">{m.win_best.toFixed(1)} → {m.win_played.toFixed(1)} ({m.class}{m.labels.includes("suppressed") ? ", game already decided" : ""})</dd>
      <dt>Best</dt><dd className="line">{m.best_san.join(" ")}</dd>
      <dt>After {plies[m.ply].san}</dt><dd className="line">{m.refutation_san.join(" ")}</dd>
      {m.kind === "unpunished" && <><dt>Your reply</dt><dd>{plies[m.reply_ply!].san}, which let it go (−{m.reply_loss!.toFixed(1)})</dd></>}
      {m.eval_delta > 3 && <><dt>Note</dt><dd>The engine's first and final views differed by {m.eval_delta.toFixed(1)} points; treat the label as approximate.</dd></>}
    </dl>
  );
}

function WinGraph({ scores, cursor, me, onPick }: { scores: Score[]; cursor: number; me: "w" | "b"; onPick: (k: number) => void }) {
  const W = 600, H = 120, n = scores.length;
  const pts = [50, ...scores.map((s) => (s.mover_is_me ? s.win_played : 100 - s.win_played))];
  const x = (i: number) => (i / Math.max(1, n)) * W, y = (v: number) => H - (v / 100) * H;
  const path = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  return (
    <figure className="graph" aria-label="Your winning chances through the game">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" onClick={(e) => {
        const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
        onPick(Math.round(((e.clientX - r.left) / r.width) * n));
      }}>
        <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="mid" />
        <path d={`${path}L${W},${H}L0,${H}Z`} className="area" />
        <path d={path} className="ln" />
        {scores.map((s, i) => s.mover_is_me && s.class !== "good" && !s.labels.includes("suppressed") ? <circle key={i} cx={x(i + 1)} cy={y(pts[i + 1])} r="4" className={`dot cls-${s.class}`} /> : null)}
        <line x1={x(cursor)} x2={x(cursor)} y1="0" y2={H} className="cur" />
      </svg>
      <figcaption className="small muted">Your Win% ({me === "w" ? "White" : "Black"}). Dots: your mistakes. Tap to jump.</figcaption>
    </figure>
  );
}

const fmt = (v: number | null, unit: string) => v == null ? "–" : unit === "%" || unit === "Win%" ? `${v.toFixed(1)}%` : unit === "× normal" ? `${v.toFixed(1)}×` : v.toFixed(2);

function Card({ onAuthError }: { onAuthError: (e: unknown) => void }) {
  const [tc, setTc] = useState("blitz");
  const { data, error } = useLoad<ReportCard>(`/api/reportcard?time_class=${tc}`, onAuthError);
  return (
    <section className="stack">
      <div className="seg" role="tablist">{["blitz", "rapid"].map((k) => <button key={k} role="tab" aria-selected={tc === k} onClick={() => setTc(k)}>{k === "blitz" ? "Blitz (5 min)" : "Rapid (10 min)"}</button>)}</div>
      {error && <p className="bad">{error}</p>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data?.status === "not_enough_games" && <div className="panel"><h2>Not enough analyzed games yet</h2><p className="muted">{data.games} of {data.min_games} {tc} games are analyzed. The report card appears once {data.min_games} are ready.</p></div>}
      {data?.status === "ok" && data.metrics && <>
        <div className="panel">
          <h2>Report card · {tc}</h2>
          <p className="small muted">Your last {data.games} {tc} games (average rating {data.your_rating}). Each grade shows how far you are from your current level, your opponents averaging {data.opponent_rating}, toward the {data.goal} level, measured on {data.reference_games} games between {data.goal}-rated players. F: below your current level. D: about at it. A: at {data.goal} level already.</p>
        </div>
        <div className="panel tablewrap">
          <table className="card">
            <thead><tr><th>Parameter</th><th>Grade</th><th className="num">You</th><th className="num">Your level</th><th className="num">{data.goal}</th></tr></thead>
            <tbody>{data.metrics.map((m) => (
              <tr key={m.key}>
                <td><div>{m.label}</div><div className="small muted">{m.explain}{m.better === "lower" ? " · lower is better" : ""}</div></td>
                <td><span className={`grade g-${m.grade || "none"}`}>{m.grade || "–"}</span></td>
                <td className="num"><div>{fmt(m.you, m.unit)}</div>{m.ci && <div className="small muted">{fmt(m.ci[0], m.unit)}–{fmt(m.ci[1], m.unit)}</div>}</td>
                <td className="num">{fmt(m.your_level, m.unit)}</td>
                <td className="num">{fmt(m.goal, m.unit)}</td>
              </tr>))}</tbody>
          </table>
          <p className="small muted">Small grey ranges: 90% interval from your games. No grade when your level and the {data.goal} level hardly differ on that parameter.</p>
        </div>
        {data.hypotheses && <div className="panel stack"><h3>What you believed, checked</h3>
          {data.hypotheses.map((h) => <div key={h.belief}><b>“{h.belief}”</b><div className="small">{h.measure}: <span className="mono">{h.value == null ? "not enough data" : `${h.value.toFixed(1)}${h.unit}`}</span>{h.n != null ? <span className="muted"> (n = {h.n} fast moves)</span> : null}</div></div>)}
          <p className="small muted">Raw numbers for now. The weakness reports in Phase 3 add comparisons with intervals and say whether each belief is supported.</p>
        </div>}
      </>}
    </section>
  );
}

function StatusView({ onAuthError, onLogout }: { onAuthError: (e: unknown) => void; onLogout: () => void }) {
  const { data, error, reload } = useLoad<Status>("/api/status", onAuthError);
  const [msg, setMsg] = useState<string | null>(null);
  const [server, setServer] = useState(apiBase());
  const done = (tc: string) => data?.games.filter((g) => g.time_class === tc && g.analysis_status === "done").reduce((a, g) => a + g.n, 0) ?? 0;
  const all = (tc: string) => data?.games.filter((g) => g.time_class === tc).reduce((a, g) => a + g.n, 0) ?? 0;
  const queued = data?.jobs.filter((j) => j.kind === "analyze" && (j.status === "queued" || j.status === "running")).reduce((a, j) => a + j.n, 0) ?? 0;
  return (
    <section className="stack">
      {error && <p className="bad">{error}</p>}
      {data && <div className="panel stack">
        <h2>Status</h2>
        <dl className="kv">
          <dt>Ratings</dt><dd>{data.ratings.map((r) => `${r.time_class} ${r.rating}`).join(" · ")} (goal {data.goal})</dd>
          <dt>Analyzed</dt><dd>blitz {done("blitz")} of {all("blitz")} · rapid {done("rapid")} of {all("rapid")}</dd>
          <dt>Waiting</dt><dd>{queued} games in the analysis queue</dd>
          <dt>Last sync</dt><dd>{data.last_sync ? new Date(data.last_sync).toLocaleString() : "not yet"}</dd>
        </dl>
        <div className="row">
          <button className="primary" onClick={async () => { await api("/api/sync", { method: "POST" }).catch(onAuthError); setMsg("Sync queued. New games appear within a minute."); setTimeout(reload, 60000); }}>Sync now</button>
          <button onClick={reload}>Refresh</button>
        </div>
        {msg && <p className="small">{msg}</p>}
      </div>}
      <div className="panel stack">
        <h3>Server</h3>
        <label htmlFor="srv2" className="small muted">Leave empty when this page comes from your home computer.</label>
        <input id="srv2" type="url" value={server} onChange={(e) => setServer(e.target.value)} placeholder="https://…" />
        <div className="row"><button onClick={() => { setApiBase(server); reload(); }}>Save</button>
          <button className="quiet" onClick={async () => { await logout().catch(() => {}); onLogout(); }}>Sign out</button></div>
      </div>
    </section>
  );
}
