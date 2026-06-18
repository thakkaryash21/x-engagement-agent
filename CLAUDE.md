# CLAUDE.md — Twitter Engagement Agent (Development Context)

last_updated: 2026-06-13
status: living document — keep in sync with AGENTS.md, 00-requirements.md, 01-spec.md as the system evolves

This file is for whoever (human or agent) does **development work on this Twitter agent** — adding modes, fixing wiring, extending the dashboard, refining playbooks. It is the onboarding doc: read this first to understand what exists, why, and how the pieces fit, then go to the specific file you need to change.

It is a different document from `AGENTS.md`: `AGENTS.md` is the **behavior contract an agent follows while *running* a mode** (`learn`/`scroll`/`compose`/`send`/`review`) — pacing, guards, file map, mode router. This file is the **map for *building and changing* that system**.

---

## 1. What We're Building (one paragraph)

A Codex-primary, Claude-Code-interchangeable agent that drives the founders' **real, logged-in Chrome** to browse Twitter/X as a specific persona (Shubham first, Yash second). It decides what's worth replying to, drafts replies/quotes/thread-replies/original tweets in that persona's authentic voice, queues every draft for human review, and — after a human sends — circles back days later to capture analytics and turn outcomes into written rules. The "database" is local CSVs; the "brain" is a set of Markdown guideline files the agent itself keeps rewriting as it learns. A local dashboard is the only UI a human needs — no raw file editing required for day-to-day use.

This lives inside the **standalone local workspace** (`this repository`) under `` — a sibling working folder, self-contained, not part of the numbered `0X-*` Markdown KB structure described in the repo root `CLAUDE.md`.

---

## 2. Objective — the non-negotiables

From `00-requirements.md`'s ten capability pillars, distilled to what actually constrains design decisions:

1. **The browser is the only integration.** No X API, no scrapers. Everything the agent "knows" about Twitter comes from looking at rendered pages, like a human.
2. **Files are the whole system.** CSVs under `data/data/` = database. Markdown under `guidelines/`, `data/style/`, `data/learnings/`, and `data/writing/` = intelligence. `data/drafts/` = human review queue. The dashboard is a view/edit layer over these same files — never a second database.
3. **The agent never sends.** It drafts. A human gates every send. No code path posts without a preceding human action.
4. **Full human mimicry is mandatory** (not just randomized delays): burst-pause scrolling, character-by-character typing, one focused tab, human-paced navigation. This is a ToS-risk mitigation, treated as a hard requirement everywhere.
5. **Zero AI-tells.** Every draft passes the Anti-AI Bible (`data/writing/00_anti_ai_writing_bible.md`) as a hard gate — full rewrite on any tell, never a patch.
6. **Voice and red lines outrank metrics**, always. A high-performing pattern that violates either is logged as an observation, never promoted to a rule.
7. **One fact, one home; append vs. correct.** Learnings are appended as new evidence arrives; a rule contradicted by new evidence is rewritten in place (the "correction rule," 01-spec.md §8.1/§9), never left to rot alongside its replacement.
8. **No fact invention.** Any Cruitical traction number in a draft must trace to `data/company-facts.md` (the main KB) or it's flagged `[VERIFY: ...]`.

Full pillar-by-pillar detail: `00-requirements.md`. Technical spec (directory layout origins, CSV schemas, dashboard spec): `01-spec.md`.

---

## 3. How We're Going About It — the operating model

### 3.1 Five modes, one router

`AGENTS.md` §4 is the mode router. Every session starts with the **Session Bootstrap** (§4.0: load persona config, limits/metrics config, check incident lockout, run Cold-Start Guard, attach to Chrome), then proceeds to one of:

| Mode | Procedure | What it does |
|---|---|---|
| `learn` | `modes/learn.md` | Read-only cold start: studies the persona's Posts, Replies, **Likes** (framing/genre patterns), and interaction network. Outputs the style doc + seed playbooks. Re-runnable; extends/corrects, never duplicates. |
| `scroll` | `modes/scroll.md` | Browses the timeline, filters/scores candidates, drafts replies/thread-replies/quotes into the queue. `--tagging` enables tag-in exploration. |
| `compose` | `modes/compose.md` | Drafts original tweets. Same drafting pipeline as `scroll`, no target browsing. |
| `send` | `modes/send.md` | Walks the draft queue oldest-first; existence/staleness check, human decides send/edit/discard. Edits feed back into the style doc immediately. |
| `review` | `modes/review.md` | ≥5 days after send: captures layered metrics, joins to draft metadata, writes learning entries (content/timing/engagement-target playbooks), promotes high-confidence voice rules to the style doc. |

### 3.2 Browser control

The agent attaches to the user's already-open Chrome via Codex's `control-chrome` plugin (AGENTS.md §3.1) — no separate automation browser. Per-persona `chrome_profile` (`data/personas/<name>.md`) tells the user which Chrome profile to have open.

### 3.3 The drafting pipeline — the actual "writing" step

This is the part most likely to need tuning, and the part most recently reworked. `modes/scroll.md` §2.6 / `modes/compose.md` §2, in order:

1. **Calibration pass** — re-read 2-3 real examples for the chosen archetype (`guidelines/reply-playbook.md`, for `scroll`) or the matching "Key traits from actual tweets" in the voice guide's Twitter/X section (for `compose`). Sets the target **register** (sentence length, directness, how much is stated vs. implied) — never topic or wording.
2. **Persona voice guide** (`data/personas/<name>.md` → `voice_guide`) — vocabulary, tone, territory framing, red lines.
3. **Personal style doc** (`data/style/<persona>-twitter-style.md`) — `## Confirmed` rules are hard constraints, `## Tentative` weighted lightly.
4. **Framing/engagement pass** — checks the draft against `data/style/<persona>-twitter-style.md` → `## Framing patterns (from Likes)`. If the draft reads flat/report-like, rewrites the **framing** (not the idea) using a noted technique (lead with a concrete detail, set up a contrast, close on dry understatement, etc.). Weighted below pass 3 — never overrides Confirmed voice or red lines.
5. **Anti-AI Bible final pass** (hard gate) — any tell found, including ones introduced by pass 4, means rewrite from scratch.

Plus five Shubham-specific checks before recording (read-aloud, actor, contribution, forbidden-phrasing, expertise — see `modes/scroll.md` §2.6).

**The calibration-not-copy principle applies everywhere examples are used**: `reply-playbook.md` examples, voice-guide tweet examples, and `## Framing patterns (from Likes)` are all *register/technique* references. Drafts should never inherit a past tweet's topic, wording, or specific framing — only its *shape*.

### 3.4 Learning loop

`learn` is the cold start (Posts/Replies → voice patterns; Likes → framing/engagement patterns, §1.5; interaction graph → `profiles.csv`). `review` is the ongoing loop (≥5 days post-send → metrics → learning entries → promotion to style doc when confidence is `high` (≥7 consistent observations)). Both write through the same correction rule: contradicted entries get rewritten in place with a line in `## Correction log`, never appended-around.

### 3.5 Dashboard

`dashboard/server.py` (stdlib Python, `python dashboard/server.py`, http://localhost:8787) + `dashboard/static/` (vanilla JS/HTML/CSS). View/edit layer over every file below — drafts queue (approve/edit/discard), config forms (limits/metrics/personas), a "Knowledge" tab that renders the learning/style/guideline Markdown, and agent-run launching. See `dashboard/README.md`.

---

## 4. File/Directory Structure

```
.
  00-requirements.md        Requirements and product intent
  01-spec.md                Technical spec and data model
  AGENTS.md                 Runtime behavior contract and mode router
  CLAUDE.md                 Development/onboarding guide
  README.md                 Public project overview
  config/
    app.yaml                Non-sensitive app wiring: data_root, agent command, dashboard port
  data/                     PRIVATE, gitignored runtime state
    personas/               Real persona definitions
    company-facts.md        Verified company/product facts for factual claims
    config/                 Runtime limits and metrics settings
    data/                   CSV database
    drafts/                 Human review queue and archives
    learnings/              Review-mode learnings
    style/                  Learned persona style docs
    writing/                Private writing and voice guides
  example/data/             Public starter templates and schema-only CSVs
  guidelines/               Public targeting, profile, format, and tagging playbooks
  modes/                    Mode procedures: learn, scroll, compose, send, review
  dashboard/                Local stdlib Python dashboard
  docs/                     Public docs and implementation notes
  scripts/                  Bootstrap and publish-safety helpers
```

---

## 5. Current State (snapshot — verify against the files before relying on this)

- **Shubham persona** is the only one that's been through `learn`: style doc has 15 `## Confirmed` + 11 `## Tentative` voice patterns from Posts/Replies; `## Framing patterns (from Likes)` exists as an empty section pending a Likes pass; `reply-playbook.md` has real examples seeded for most archetypes; `profiles.csv` has ~44 studied accounts.
- **Cold-Start Guard** (AGENTS.md §5.1) is satisfied for Shubham (style doc has ≥1 Confirmed entry). Not yet run for Yash.
- **Dashboard** is built and functional: Drafts/Config/Run/Knowledge tabs all wired to the files above.
- `data/drafts/discarded/` has ~28 drafts from a real `scroll` session — useful as real examples of what the pipeline currently produces (and what got discarded) when evaluating drafting-quality changes.
- 
---

## 6. Conventions When Extending This System

- **One fact, one home.** Don't duplicate a rule across `voice_guide`, `style_doc`, `reply-playbook.md`, and `data/learnings/*` — each has a distinct job (see §3.3/§3.4). If you're adding a new kind of learned signal, decide which single file owns it before writing to multiple.
- **Examples are calibration, never templates.** Any time you add an "Examples" section that future drafting passes will read, state explicitly that it calibrates register/technique, not topic/wording — the existing sections (`reply-playbook.md`, style doc's Framing-from-Likes) model this.
- **Correction rule over append.** When a rule turns out wrong, rewrite it in place and log it in `## Correction log` — don't leave the old and new versions both present.
- **Update `last_updated`** on any file you materially change, with a short note on what changed (see recent edits to `scroll.md`/`compose.md`/`learn.md` for the pattern).
- **Keep `AGENTS.md` and this file in sync with the mode files.** If you change a drafting pass, update the one-line pipeline summaries in `AGENTS.md` §4.2/§4.3 and the pipeline description in §3.3 above.
- **Voice/red-lines/no-fact-invention are non-negotiable** — any new mode, dashboard feature, or playbook change must preserve these even if it seems to hurt "engagement."



