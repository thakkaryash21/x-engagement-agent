# CLAUDE.md - X Engagement Agent Development Guide

last_updated: 2026-07-11
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

Use [docs/file-map.md](docs/file-map.md) as the canonical routing guide for file ownership, data boundaries, CSV headers, Markdown database templates, examples, and dashboard file IO. Do not duplicate that structure here. If ownership changes, update `docs/file-map.md` in the same change.

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

Drafting is governed by a shared writing pipeline: the persona voice guide + Twitter style doc, the shared framing-technique library (`data/writing/framing-structure.md`, one owner for both personas), archetype output shapes and an anti-sameness gate (`guidelines/reply-playbook.md`, `modes/scroll.md` §2.6), the Anti-AI Bible, and the context-enrichment step (§6) that supplies current, specific subject context. `scroll` §2.4b, `learn`'s `context_seed` pass, and `review` all have context touchpoints.

---

## 5. Dashboard Model

The dashboard is a local FastAPI backend plus Vite React frontend:

- Backend entry: `dashboard/server.py`
- File IO layer: `dashboard/file_store.py` — a thin composition root over focused service modules: `paths.py`, `config_store.py` / `config_document.py` (comment-preserving config field editor), `draft_file.py` (owns the draft `---` template), `tables.py` (owns the CSV schemas + `status` enum), `draft_queue.py`, `insights.py`, `incidents.py`, `run_launcher.py`.
- Context subsystem: `dashboard/context_store.py` + `dashboard/context_memory.py`, invoked by the modes through `dashboard/context_cli.py` (see §6).
- Frontend source: `src/`
- Built frontend: `dashboard/frontend/dist/`

The dashboard edits the same files the modes read:

- drafts under `data/drafts/`
- CSV rows under `data/csv/`
- Markdown knowledge files under `data/personas/`, `data/style/`, `data/learnings/`, `data/writing/`, and `guidelines/`
- runtime config under `config/`

Do not add a parallel persistence layer unless the repo design is intentionally changed and documented.

---

## 6. Context Enrichment Subsystem

`scroll`, `learn`, and `review` gather current, resolved context about the *subject* of a tweet (not just the author), so drafts are specific and current instead of a generic caveat. It is browser-only toward X (rendered pages, never an API) and adds off-X web background via Codex's native `--search`.

- **Acquisition intelligence (single owner):** `guidelines/context-enrichment.md` — the context-type taxonomy, source-selection matrix, query playbook, four adapters, and gap router. Mode docs reference it; they never restate it.
- **Draft-time step:** `modes/scroll.md` §2.4b (gap-gated + archetype-aware): gap analysis → source selection → query construction → gather → grade sufficiency → distill → write-back → brief → draft. Bounded by `max_context_lookups_per_session` (`config/limits.yaml`).
- **One-tab exception:** `AGENTS.md` §3.4 permits one scoped, serial research tab (open→read→close) for on-X subject research.
- **Two-scope memory (world + self):** external subject knowledge (`scope=world`) plus the persona's own documented experience (`scope=self`), retrieved at draft time (archetype decides the blend). `learn` seeds both from the persona's history (its `context_seed` pass); `review` grows them from sent replies. Every fact traces to captured evidence — nothing is fabricated (enforces the persona no-invention red line).
- **Storage (files are the system):** under gitignored `data/context/` — Layer-1 dossiers (`subjects/<slug>.md`, `self/<persona>/<slug>.md`, human-editable), Layer-2 per-draft briefs (`briefs/<reply_id>.md`), immutable `evidence/`, flat `chunks/`, promotion-counter state `sightings.json`, and a derived, rebuildable vector `index/`. Layer-3 analytics: `csv/context-provenance.csv` (schema in `dashboard/tables.py`; its `gap_type`/`source_types` vocabularies are owned by `guidelines/context-enrichment.md` §5.1).
- **Code seam:** `dashboard/context_store.py` (`ContextStore` — the swappable LanceDB + fastembed substrate: `add`/`search`/`search_lexical`/`reindex`, retrieval primitives only, no ranking policy) beneath `dashboard/context_memory.py` (`ContextMemory` — the stable policy: write-back / dedup / promotion / reflect / retrieval blend / style-exemplars). Retrieval tunables (blend weights, recency half-life, dedup/promotion thresholds) are code-owned defaults in `ContextMemory`; the session caps (`max_context_lookups_per_session`, `context_research_time_budget_minutes`) are enforced by the modes, not the CLI. The modes call it through the CLI **`python -m dashboard.context_cli`** (subcommands `search` / `write-back` / `reflect` / `style-exemplars` / `reindex`) — no running-server dependency.
- **Enable:** web search is on for **all** runs via two mechanisms — (1) `~/.codex/config.toml → [tools] web_search = true` makes the native `web_search` tool available to **every** `codex` invocation, including **manual** `codex '<mode> ...'` runs (this is the one that matters, since manual runs bypass the launcher); (2) `config/app.yaml → agent_web_search: true` additionally makes the dashboard launcher append `--search`. Note: on-X *topic* research (adapter b, `x_search`) is browser-only and needs no flag — it is gap-gated agent behavior, so verify it actually fires via a `scroll` provenance row (`source_types`, `n_lookups`), not by config alone.
- **Deferred (documented, not executable yet):** genuine `reflect()` *synthesis* and the `review` voice-authenticity ensemble — see [docs/roadmap.md](docs/roadmap.md). `reflect()` itself runs today (invoked by `learn` §6.3 and `review` §6) but emits an honestly-labeled interim *consolidation* — a labeled join of the source chunks, not a distilled abstraction; the ensemble is fully unwired (no scorers, no thresholds, no output). A session runs the interim consolidation but neither the deferred synthesis nor the ensemble.

Design/research notes for this subsystem live locally under `tasks/` (gitignored) and are not needed to run or maintain it — this section, `guidelines/context-enrichment.md`, and `docs/roadmap.md` are the committed record.

---

## 7. Extension Rules

- Keep public playbooks persona-neutral. Move persona-specific calibration to `data/personas/`, `data/style/`, or `data/learnings/`.
- Keep `config/` non-sensitive. Runtime defaults go there; private company/persona facts do not.
- Keep `example/data/` sanitized and structurally aligned with `data/`.
- Preserve CSV headers unless every mode, dashboard reader/writer, example CSV, and `docs/file-map.md` are updated together.
- Preserve draft `---` separators unless the dashboard parser and mode docs are migrated together.
- When a learning contradicts an existing rule, rewrite the owning rule in place and record the correction. Do not leave stale and corrected rules competing.
- Update `last_updated:` when materially changing Markdown files that have that field.

---

## 8. Verification Before Publishing

Before publishing or committing cleanup work, run the publish-safety checks:

```powershell
.\scripts\check-sensitive-data.ps1
git ls-files data/* docs/superpowers/*
git status --short --ignored
```

Expected result: no tracked private data, local-only folders remain ignored, and no private/source-specific references appear in public files.
