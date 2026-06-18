# X Engagement Agent Dashboard

last_updated: 2026-06-18
status: FastAPI + Vite React local web app

A local web app for reviewing drafts, checking insights, editing Markdown knowledge files,
tuning runtime config, and launching agent mode sessions. Per `docs/file-map.md`, the
dashboard is **not a second database**. It reads and writes the same CSVs, YAML, and
Markdown files that `AGENTS.md` and the `modes/*.md` procedures use.

## Run

Install once:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm install
```

Built mode:

```
npm run build
.\.venv\Scripts\python dashboard/server.py
```

Then open http://127.0.0.1:8787. FastAPI serves the built React dashboard from
`dashboard/frontend/dist`.

Development mode:

```powershell
.\.venv\Scripts\python dashboard/server.py
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to FastAPI on port 8787.

## Surfaces

- **Drafts** — every file in `data/drafts/*.md` joined with its row in
  `data/csv/replies.csv` / `data/csv/tweets.csv`. Shows the draft text (editable),
  type/status/archetype/format chips, tagging callouts, and a staleness flag from
  `draft_staleness_hours` (`config/limits.yaml`). **Approve** sets `status=approved`
  (or `status=edited` + `user_edited=true` + `edit_summary` if the text was changed);
  **Discard** sets `status=discarded`, prepends a `**Discarded**: user (dashboard), ...`
  note, and moves the file to `data/drafts/discarded/`. Either way, `send` mode
  (`modes/send.md` §2.1) still re-verifies the target and presents the item to the human
  before anything is posted — the dashboard only records the review decision. A lockout
  banner (from `data/csv/incidents.csv`) appears if
  `lockout_triggered=true` with no `acknowledged_at`, with a button to acknowledge it.
- **Insights** — funnel counts (`drafted → approved/edited/discarded → sent → reviewed`)
  for replies and tweets, the overall edit rate on sent items, average
  `engagement_rate` by `reply_archetype` and by `content_type` (from
  `data/csv/metrics.csv`, latest capture per item), and the `profiles.csv` table.
- **Settings** — forms for `config/limits.yaml` (integer fields), `config/metrics.yaml`
  (comma-separated lists for `layer1`/`layer2`/per-format `optimize` lists), the active
  persona and `--tagging` default (`AGENTS.md` §0).
- **Knowledge** — editable Markdown workbench for `data/personas/*.md`,
  `guidelines/**/*.md`, `data/style/*.md`, `data/writing/**/*.md`, and
  `data/learnings/*.md`. Saving a Markdown file bumps its `last_updated:` line to today
  when the file has that metadata field.
- **Run** — pick a mode (`learn`/`scroll`/`compose`/`send`/`review`), an optional
  persona override, and (for `scroll`) `--tagging`, then **Launch**.

## Known limitations

- **Run tab opens a new PowerShell window rather than streaming output.** Streaming an
  interactive CLI session into the browser is intentionally out of scope for now. Launch spawns
  `powershell -NoExit -Command <agent_command> '<mode> [--persona ...] [--tagging]'`
  in a new window via `start`. `config/app.yaml` sets `agent_command`, defaulting to
  `codex`. The dashboard records the last launch in `dashboard/run-state.json` but does
  not know when or how the session ends.
- **UI breakage is not a security incident.** `data/csv/incidents.csv` and the
  auto-lockout are for the browser-automation modes (AGENTS.md §6); a dashboard error
  just shows an `{"error": ...}` JSON response or an inline message.
- Single-user, local-only — no auth. Don't expose port 8787 beyond localhost.



