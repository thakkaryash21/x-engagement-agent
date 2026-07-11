# Roadmap

last_updated: 2026-07-11
status: public; records capabilities that are intentionally deferred (designed, described in the prose, but not yet executable) so the mode docs can honestly point at a single home.

This file exists so the mode procedures can say "described here, not yet built" and link somewhere durable instead of overclaiming. A feature belongs in `## Deferred` when its design is on record but a `scroll`/`learn`/`review` session does **not** execute it today. When one ships, move it out of this section and update the referencing prose in the same change.

---

## Deferred

Both entries below are deferred by an explicit product decision (Plan 08 Decisions, 2026-07-11): they are **measurement/maintenance features whose value only appears once real accumulated memory and a real history of sent drafts exist.** Building them against an empty store would be premature — there is nothing yet to consolidate or to measure. They are documented in the prose as *planned / not-yet-executable* (no vaporware claims), and this is the record of why and when.

### 1. `reflect()` — real synthesis (currently interim consolidation)

- **Where it lives today:** `ContextMemory.reflect()` in `dashboard/context_memory.py`; invoked by `modes/learn.md` §6.3 (per seeding batch) and `modes/review.md` §6 (after ingest), via `python -m dashboard.context_cli reflect`.
- **What ships today (executable):** a **simple, honestly-labeled consolidation.** `reflect()` gathers the raw non-insight chunks for a scope (optionally one subject) and writes back **one** `insight` chunk whose `text` is a *labeled concatenation* of the source chunks' texts — `context_type=insight`, `source_type=reflection`, provenance = the source chunk ids. It flows through the same dedup/merge as write-back, so running it every batch refreshes the one insight instead of appending duplicates. It is a step above the janitorial dedup already done at write-back, and nothing more.
- **What is deferred (not built):** **genuine synthesis** — an `insight` whose text states an abstraction *beyond the union* of the source texts (a distilled higher-level stance or a subject's true consolidated current state, not a join of the raw lines). The current pass does not distill anything the raw chunks don't already say. The code and prose deliberately avoid calling the interim pass "synthesis"; the local text variable is named `consolidated`, and the docstring/prose label it interim consolidation.
- **Why deferred:** synthesis only earns its keep once many scattered chunks about the same subject/persona have accumulated — the raw material a real abstraction would compress. With a near-empty store the concatenation is already sufficient and a synthesis model would have nothing to compress.
- **When it gets built:** once seeding (`learn` §6) plus live `scroll`/`review` write-backs have produced a store with real per-subject and per-persona chunk density — i.e. when consolidation output starts being long/redundant enough that a distilled abstraction would materially beat the labeled join. At that point, replace the concatenation in `reflect()` with a distillation pass and update the "interim behaviour" labels in `learn.md` §6.3, `review.md` §6, and the `context_memory.py` docstring together.

### 2. `review` voice-authenticity ensemble (multi-metric)

- **Where it lives today:** `modes/review.md` §7, explicitly headed **PLANNED, not yet executable**. A current `review` session does not run it and writes nothing from it.
- **What ships today (executable):** nothing. §7 is a design on record only. No scorers, thresholds, or dashboard output are wired.
- **What is deferred (not built):** an **ensemble of complementary voice-authenticity signals reported side by side as a small dashboard, never collapsed into one number** — the divergence between signals is the finding. The three planned signals:
  - **Authorship-attribution** — does the sent text read as *this persona* vs. a generic/AI voice, scored against the style doc + the persona's own `scope=self` style exemplars (selected for stylistic diversity/coverage, not topical similarity).
  - **NLI self-consistency (aggregate)** — the batch aggregate of the same per-draft persona-consistency judgment the drafting gate applies pre-send (`modes/scroll.md` §2.6 Self-consistency check). **The concrete NLI model, the per-statement contradiction threshold, and the reject rule are not yet chosen or wired** — the same not-yet-implemented status the drafting-side check carries. When built, the rule must be: evaluate each persona statement independently and reject on *any* material contradiction (never let one strong entailment mask a contradiction via a netted `max(entailment) − max(contradiction)` score).
  - **AI-detector probe** — a weak tell-tracker followed as a *trend* only, never a target to game; the human send-gate is the backstop (AGENTS.md §1).
- **Why deferred:** an authenticity ensemble is a measurement feature that only produces a trustworthy trend once a real history of sent drafts has accumulated. With few or no sent drafts there is no signal to read and no divergence to surface.
- **When it gets built:** once enough drafts have been sent (via `send` mode) and reviewed that a per-session ensemble read has real inputs — and once the shared NLI scorer/threshold is chosen (it is the same component the drafting-side self-consistency check in `scroll.md` §2.6 also awaits, so both should be wired together). At that point, replace §7's PLANNED framing with the executable procedure and add the authenticity-dashboard write target to `review.md`'s "Writes to" list.

---

## Known follow-ups (minor)

Small engineering follow-ups surfaced by review — none block running the subsystem; fix opportunistically.

1. **Atomic reindex swap** (`dashboard/context_store.py`, `reindex`). The rebuild drops the live table then re-creates + re-adds rows; if the re-add fails after the drop, the index is gone until the next `reindex`. Prefer building/validating a temp table and renaming it over the live one so the swap is crash-safe. (Files stay authoritative — recovery is always a `reindex` away — hence minor.)
2. **Layer-3 provenance-row writer** (`data/csv/context-provenance.csv`). `scroll` §2.7 records the review-index row, but there is no CLI subcommand for it — the agent appends a schema-coupled row by hand, which can drift from `dashboard/tables.py::COLUMNS_CONTEXT_PROVENANCE`. Add a `context_cli provenance` subcommand that appends through the `tables.py` schema owner.
3. **LanceDB deprecations** (`dashboard/context_store.py`). `table_names()` and `create_fts_index(..., use_tantivy=False)` are deprecated in the installed LanceDB; migrate to `list_tables()` / the current FTS API before an upgrade breaks `reindex`/hybrid retrieval.
