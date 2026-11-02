# Running Chess Coach on your home computer

Everything (database, engine analysis, the app) runs on your computer in Docker. Your phone opens the app
from it. This is the Phase 1 setup; the spec's hosting section (§29) explains the alternatives.

## Easiest: let Claude Code do it

Open Cursor, open a new empty folder, start Claude Code in its terminal panel, and paste:

> Set up Chess Coach on this computer. Clone https://github.com/turners1110/chess-coach (branch
> `claude/pensive-bohr-1sc29y`) into this folder, then follow `docs/setup-home-computer.md` step by step.
> Check that Docker is installed and running first and tell me if it is not. Create `.env` with a random
> `POSTGRES_PASSWORD` and `COACH_WORKERS` set to my CPU core count minus one. Stop and tell me when I need to
> create my app password (step 3) so I can type it myself, then put the hash it prints into `.env`. Start
> everything, wait until http://localhost:8000/api/health answers, and show me the worker log for the first sync.

Claude Code asks before running each command (you can allow them one by one). The three things only you can do:

- **Install Docker Desktop** and open it once (it needs your admin password).
- **Type your app password** when the password tool asks (step 3); never paste it into the chat.
- **Create a Tailscale account**, if you want the app away from home (step 6).

The manual steps follow, in case you prefer to do it yourself.

## What you need

- A Mac, Windows PC or Linux computer that is on when you want new games analyzed. Analysis pauses
  while it is off and continues when it is back on.
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (free for personal use), or Docker
  Engine on Linux.
- About 3 GB of disk space.
- For the phone, away from home Wi-Fi: [Tailscale](https://tailscale.com) (free personal plan, an account on
  the computer and the iPhone). See step 6.

## 1. Get the code

```bash
git clone -b claude/pensive-bohr-1sc29y https://github.com/turners1110/chess-coach.git
cd chess-coach
```

(The Phase 1 code is on this branch until it is merged into `main`.)

## 2. Settings file

```bash
cp .env.example .env
```

Open `.env` and set `POSTGRES_PASSWORD` to any long random text. Set `COACH_WORKERS` to the number of
CPU cores you can spare (each core analyzes one game at a time; leave one or two cores free).

## 3. App password

```bash
docker compose build
docker compose run --rm api python -m coach.passwd
```

Type a password (8+ characters) twice. Copy the line it prints (`COACH_PASSWORD_HASH='…'`, with the
single quotes) into `.env`. Only the hash is stored; nobody can read your password back from it.

## 4. Start

```bash
docker compose up -d
```

The first build compiles Stockfish 18 for your processor, which takes 5–10 minutes. Then open
<http://localhost:8000> on the computer and sign in.

## 5. What happens next

- The worker syncs your chess.com games right away, then every 30 minutes.
- It analyzes your 100 most recent blitz and 100 most recent rapid games first, newest first, together
  with the 1500-level reference games for the report card. Then it works through the rest of your history.
- Speed: about 107 seconds of one CPU core per game. With 3 workers that is about 35 seconds per game:
  roughly 4 hours for the first 400 games and 12 hours for everything (about 1,230 games).
- The report card appears once 30 games of a time class are analyzed. **Status** in the app shows progress.

After the first sync the worker also collects the 1500-level reference games (about 200, one serial crawl of
chess.com) and queues them for analysis.

## 6. Open it on your iPhone

**At home only (simplest):** find the computer's local address (for example `192.168.1.20`) and open
`http://192.168.1.20:8000` in Safari. This works for game review, but iOS only installs it as a full app
and keeps it offline over HTTPS.

**Anywhere, with HTTPS (recommended):**

1. Install Tailscale on the computer and on the iPhone and sign in to both with the same account.
2. On the computer, run `tailscale serve --bg 8000`. It prints an address like
   `https://my-computer.tail1234.ts.net`.
3. Open that address in Safari on the iPhone, sign in, then **Share → Add to Home Screen**.

The address is private to your Tailscale devices; nothing is exposed to the internet.

## Everyday use

- **Update to a new version:** `git pull` (or download the ZIP again), then `docker compose up -d --build`.
- **Stop:** `docker compose down` (your data stays). **Logs:** `docker compose logs -f worker`.
- **Backup:** `docker compose exec db pg_dump -U coach coach > coach-backup.sql`.
- **Re-download one month from chess.com:** in the app, or `curl -X POST "http://localhost:8000/api/sync?resync=202510" -H "Authorization: Bearer …"`.

## Troubleshooting

- **"Rosetta installation failed" (Apple Silicon Mac, Docker Desktop).** Chess Coach does not need Rosetta:
  all its images run natively on Apple Silicon. Either install Rosetta in Terminal with
  `softwareupdate --install-rosetta --agree-to-license`, or open Docker Desktop → Settings → General, untick
  "Use Rosetta for x86_64/amd64 emulation on Apple Silicon", then Apply & restart. Check with
  `docker run --rm hello-world`.
- **`docker: command not found` or "Cannot connect to the Docker daemon".** Docker Desktop is not running:
  open it and wait until it says it is running.
- **Port 8000 already in use.** Set `COACH_PORT=8001` in `.env` and use that port instead.
