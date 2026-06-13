# YouTube Focus Mode

A Manifest V3 browser extension (Chrome/Edge) that hides YouTube distractions **and** tracks how long you actually watch. The extension is the front end; an optional local FastAPI + SQLite backend stores watch-time history and serves stats back to the popup.

```
React Chrome Extension  ──▶  FastAPI  ──▶  SQLite (Postgres-ready)
```

## Features

**Hide distractions** (works fully offline, no backend needed). Each toggles independently from the popup's **Focus** tab; all default to **on**:

- Recommendations sidebar (watch-page related videos)
- Homepage feed
- Shorts (shelves + nav entry)
- Comments
- End-screen suggestions

Settings are stored in `chrome.storage.sync` and apply **live** — no page reload needed.

**Watch-time analytics** (requires the backend running). The popup's **Stats** tab shows today / this week / all-time watch time, a 7-day bar chart, your top videos and channels, and **time per topic category** (assigned by Claude). Only *active* viewing counts — the tab must be visible and a video actually playing.

## How it works

### Hiding distractions
- **Popup** (`src/popup`, React) writes feature toggles to `chrome.storage.sync`.
- **Content script** (`src/content/content.js`) mirrors those settings onto `<html>` as classes (e.g. `yfm-hide-shorts`) and updates them on `chrome.storage.onChanged`.
- **`src/content/content.css`** holds the actual hide rules, each gated on one of those classes. It's loaded directly by the manifest at `document_start` (not bundled through JS), so it applies early with minimal flicker.

### Watch-time analytics
- **`src/content/tracker.js`** samples playback every 5s, counting time only when the tab is visible and a video is playing, and batches seconds per video.
- A content script can't POST to `localhost` (page CSP/CORS), so it forwards batches to the **background service worker** (`src/background/background.js`) via `chrome.runtime.sendMessage`.
- The **service worker** POSTs them to `POST /api/events`. If the backend is offline it keeps a small in-memory retry buffer.
- The **Stats tab** (`src/popup/Stats.jsx`) reads `GET /api/stats/summary` directly and degrades gracefully when the API is down.
- `src/common/config.js` holds the single `API_BASE` constant.

## Build

```bash
npm install
npm run build      # production build -> dist/
npm run dev        # watch mode for development
```

The build produces `dist/` containing `manifest.json`, `content.js`, `content.css`, `icons/`, and `popup/` (`index.html` + `popup.js`).

## Load into the browser

1. Go to `chrome://extensions` (or `edge://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `dist/` folder.
4. Open YouTube — distractions are hidden by default. Use the toolbar popup to toggle each one.

## Backend / Analytics (optional)

The backend is a FastAPI app with SQLAlchemy over SQLite (`backend/focus.db`, created on first run). Hiding distractions works without it; it's only needed for the Stats tab.

**One-click start** (auto-creates the venv, installs deps, loads `.env`, opens the docs, restarts on crash):

```bash
scripts\start.bat            # Windows (double-click or run in a terminal)
./scripts/start.sh           # Linux / macOS
npm run backend              # any OS, via npm
```

Add `--prod` (e.g. `scripts\start.bat --prod` or `npm run backend:prod`) for production mode — uvicorn workers, no hot reload, no auto-browser. Other flags: `--port`, `--host`, `--no-browser`, `--no-restart`, `--reinstall` (see `python scripts/auto_start.py --help`).

<details><summary>Manual start (equivalent steps)</summary>

```bash
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
</details>

Either way, visit `http://localhost:8000/docs` for the Swagger UI. Endpoints:

- `GET  /` — welcome / endpoint index
- `GET  /health`
- `GET  /stats` — simple live snapshot (`videos_watched`, `watch_time`, `today`)
- `POST /api/events` — ingest a batch of `{video_id, title, channel?, seconds, occurred_at?}`
- `GET  /api/stats/summary?days=7` — totals, per-day series, top videos & channels, and time per category
- `POST /api/categorize` — categorize uncategorized videos via Claude (no-op if no API key)

### AI video categorization (Claude)

The Stats tab's **By category** section shows time-per-topic. Categories are assigned by Claude (**Haiku 4.5**) via the Anthropic SDK:

- Set an API key before starting the server: copy `backend/.env.example` to `.env` and fill `ANTHROPIC_API_KEY`, or `export ANTHROPIC_API_KEY=...` in your shell.
- In the popup's Stats tab, click **Categorize** — it POSTs to `/api/categorize`, which sends the titles of so-far-uncategorized videos to Claude in one batched call and stores the results in the `video_categories` table.
- Without a key, `/api/categorize` returns `configured: false` and does nothing; all other features keep working. Watched videos simply show as **Uncategorized** until categorized.

Categorization logic and the fixed taxonomy live in [`backend/app/categorize.py`](backend/app/categorize.py).

**Switching to PostgreSQL** later is just a connection string — set `DATABASE_URL=postgresql+psycopg://user:pass@host/db`; the SQLite-only `connect_args` is already gated on the URL scheme in `backend/app/database.py`. No model or query changes needed.

> The API currently allows all CORS origins because there's no auth (single local user). Tighten `allow_origins` to the extension origin before exposing it beyond localhost.

## Maintenance notes

- YouTube changes its DOM/class names over time. If a section stops hiding, update the selectors in [`src/content/content.css`](src/content/content.css). If watch time stops recording, check the channel/title selectors in [`src/content/tracker.js`](src/content/tracker.js).

## Roadmap (not yet implemented)

- Auth & multi-user accounts (then narrow CORS)
- PostgreSQL + Alembic migrations
- A full-page dashboard with richer charts
- Daily limits / scheduled blocking, focus timer (Pomodoro)

The `FEATURES` array in [`src/common/settings.js`](src/common/settings.js) is the single source of truth for hide features and is designed to extend.
