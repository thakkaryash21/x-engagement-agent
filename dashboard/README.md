# Twitter Agent Dashboard

last_updated: 2026-06-12
status: Phase 7 of 01-spec.md §11 — local view/edit layer over everything above

A small, dependency-free local web app for reviewing drafts, checking insights, editing
config/guidelines, and launching agent mode sessions. Per 01-spec.md §10, the dashboard
is **not a second database** — it reads and writes the same CSVs, YAML, and Markdown
files that `AGENTS.md` and the `modes/*.md` procedures use.

## Run

```
python dashboard/server.py
```

Then open http://localhost:8787. Stdlib only — no `pip install` needed. The server binds
to `127.0.0.1` only (local single-user tool).

## Surfaces

- **Drafts** — every file in `data/drafts/*.md` joined with its row in
  `data/data/replies.csv` / `data/data/tweets.csv`. Shows the draft text (editable),
  type/status/archetype/format chips, tagging callouts, and a staleness flag from
  `draft_staleness_hours` (`data/config/limits.yaml`). **Approve** sets `status=approved`
  (or `status=edited` + `user_edited=true` + `edit_summary` if the text was changed);
  **Discard** sets `status=discarded`, prepends a `**Discarded**: user (dashboard), ...`
  note, and moves the file to `data/drafts/discarded/`. Either way, `send` mode
  (`modes/send.md` §2.1) still re-verifies the target and presents the item to the human
  before anything is posted — the dashboard only records the review decision, per
  01-spec.md §10.2. A lockout banner (from `data/data/incidents.csv`) appears if
  `lockout_triggered=true` with no `acknowledged_at`, with a button to acknowledge it.
- **Insights** — funnel counts (`drafted → approved/edited/discarded → sent → reviewed`)
  for replies and tweets, the overall edit rate on sent items, average
  `engagement_rate` by `reply_archetype` and by `content_type` (from
  `data/data/metrics.csv`, latest capture per item), and the `profiles.csv` table.
- **Config** — forms for `data/config/limits.yaml` (integer fields), `data/config/metrics.yaml`
  (comma-separated lists for `layer1`/`layer2`/per-format `optimize` lists), the active
  persona and `--tagging` default (`AGENTS.md` §0), and a file picker/editor for
  `data/personas/*.md`, `guidelines/**/*.md`, `data/style/*.md`, `data/writing/**/*.md`, and `data/learnings/*.md`. Saving a Markdown file bumps its `last_updated:` line to
  today.
- **Run** — pick a mode (`learn`/`scroll`/`compose`/`send`/`review`), an optional
  persona override, and (for `scroll`) `--tagging`, then **Launch**.

## Known limitations

- **Run tab opens a new PowerShell window rather than streaming output.** The stdlib's
  `http.server` has no pty support, so streaming an interactive CLI session into the
  browser isn't practical without a dependency. Launch instead spawns
  `powershell -NoExit -Command <agent_command> '<mode> [--persona ...] [--tagging]'`
  in a new window via `start` (`dashboard/run-config.json` sets `agent_command`,
  default `"codex"`). The dashboard records the last launch in
  `dashboard/run-state.json` but does not know when/how the session ends.
- **UI breakage is not a security incident.** `data/data/incidents.csv` and the
  auto-lockout are for the browser-automation modes (AGENTS.md §6); a dashboard error
  just shows an `{"error": ...}` JSON response or an inline message.
- Single-user, local-only — no auth. Don't expose port 8787 beyond localhost.



