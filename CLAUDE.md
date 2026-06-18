# CLAUDE.md - X Engagement Agent Development Guide

last_updated: 2026-06-18
file_map: [docs/file-map.md](docs/file-map.md)
status: development/onboarding guide for changing this repository

This file is for humans and agents doing development work on this repo: adding modes, changing dashboard file IO, refining public playbooks, or updating documentation. Read this file, [AGENTS.md](AGENTS.md), and [docs/file-map.md](docs/file-map.md) before changing behavior.

`AGENTS.md` is the runtime behavior contract an agent follows while running a mode. This file explains how to maintain the system.

---

## 1. What This Repo Is

This is a local, file-backed X/Twitter engagement agent for founder-led marketing. It uses the operator's browser session to learn a persona, find relevant conversations, draft replies and original posts, queue drafts for human review, and capture post-send learnings.

The public repo should be reusable. Real personas, real company facts, real drafts, metrics, profiles, local examples, and private writing guides live under ignored `data/`. Public files define the reusable operating system and sanitized starter templates.

---

## 2. Non-Negotiables

1. **Browser-only integration.** No X API or scraper dependency. Browser-touching modes interact with rendered pages like a human.
2. **Files are the system.** CSV, Markdown, YAML, and draft files are the database. The dashboard is an editor/view over those files, not a second store.
3. **Human-gated sending.** The agent drafts and queues. A human explicitly approves every post in `send` mode.
4. **Private data stays local.** Persona-specific examples, real handles, company facts, style learnings, metrics, and drafts belong in ignored `data/`.
5. **Markdown structure matters.** Markdown files are database state too. Preserve headings, metadata, and draft separators unless a documented migration updates all readers and writers.
6. **One fact, one home.** Do not duplicate the same rule across persona files, style docs, public playbooks, and learnings. Pick the owning file and reference it.
7. **No fact invention.** Company/product/persona claims in drafts must trace to `data/company-facts.md` or another persona-approved local source. Unknowns are marked `[VERIFY: ...]`.

---

## 3. File Ownership

Use [docs/file-map.md](docs/file-map.md) as the canonical routing guide. It defines what belongs in:

- public runtime files (`AGENTS.md`, `modes/*.md`, `guidelines/*.md`)
- committed config (`config/*.yaml`)
- ignored runtime data (`data/**`)
- CSV database files (`data/csv/*.csv`)
- draft Markdown templates (`data/drafts/*.md`)
- public examples (`example/data/**`)
- dashboard file IO (`dashboard/file_store.py`)

If ownership changes, update `docs/file-map.md` in the same change.

---

## 4. Operating Model

`AGENTS.md` routes five modes:

| Mode | Procedure | Purpose |
|---|---|---|
| `learn` | `modes/learn.md` | Study the active persona and write style/profile learning state. |
| `scroll` | `modes/scroll.md` | Browse X, select candidates, and queue replies, thread replies, or quotes. |
| `compose` | `modes/compose.md` | Queue original posts from persona territory and learned content patterns. |
| `send` | `modes/send.md` | Present queued drafts to the human, post only after approval, and capture edits. |
| `review` | `modes/review.md` | Capture delayed performance metrics and update learnings. |

Every mode starts from the session bootstrap in `AGENTS.md` and then follows its mode file. Keep summaries in `AGENTS.md` aligned with mode procedures.

---

## 5. Dashboard Model

The dashboard is a local FastAPI backend plus Vite React frontend:

- Backend entry: `dashboard/server.py`
- File IO layer: `dashboard/file_store.py`
- Frontend source: `src/`
- Built frontend: `dashboard/frontend/dist/`

The dashboard edits the same files the modes read:

- drafts under `data/drafts/`
- CSV rows under `data/csv/`
- Markdown knowledge files under `data/personas/`, `data/style/`, `data/learnings/`, `data/writing/`, and `guidelines/`
- runtime config under `config/`

Do not add a parallel persistence layer unless the repo design is intentionally changed and documented.

---

## 6. Extension Rules

- Keep public playbooks persona-neutral. Move persona-specific calibration to `data/personas/`, `data/style/`, or `data/learnings/`.
- Keep `config/` non-sensitive. Runtime defaults go there; private company/persona facts do not.
- Keep `example/data/` sanitized and structurally aligned with `data/`.
- Preserve CSV headers unless every mode, dashboard reader/writer, example CSV, and `docs/file-map.md` are updated together.
- Preserve draft `---` separators unless the dashboard parser and mode docs are migrated together.
- When a learning contradicts an existing rule, rewrite the owning rule in place and record the correction. Do not leave stale and corrected rules competing.
- Update `last_updated:` when materially changing Markdown files that have that field.

---

## 7. Verification Before Publishing

Before publishing or committing cleanup work, run the publish-safety checks:

```powershell
.\scripts\check-sensitive-data.ps1
git ls-files data/* docs/superpowers/*
git status --short --ignored
```

Expected result: no tracked private data, local-only folders remain ignored, and no private/source-specific references appear in public files.
