# Changelog

Notable, reusable changes to the X engagement operating system. Persona/company specifics live under
gitignored `data/`; this file records the public mechanism.

## architecture-and-writing-remediation (2026-07)

A large branch that hardened the architecture, fixed drafting quality, and added a context-enrichment
memory subsystem. Highlights:

### Architecture / DRY / separation of concerns
- **Single-home the duplicated rules.** Each operating rule now has one owner and is referenced, not
  restated: engage-gate → `guidelines/profile-rubric.md`, drafting pipeline → `modes/scroll.md` §2.6,
  session caps → `AGENTS.md` §3.5, etc. `AGENTS.md` is a router, not a second copy. Collapsed several
  shallow wrapper playbooks; fixed a phantom cross-reference.
- **Dashboard deepening.** The 400-line `DashboardStore` god-object became a thin composition root over
  focused modules: `config_document.py` (comment-preserving config field editor), `draft_file.py` (the
  draft `---` template owner), `tables.py` (the CSV schema + `status` enum owner), plus
  `paths.py`/`config_store.py`/`draft_queue.py`/`insights.py`/`incidents.py`/`run_launcher.py`.

### Writing quality
- **Root-caused the "generic caveat" drafts:** the pipeline collapsed every archetype into one mold, and
  the persona guides had drifted from their canonical source. Fixes: per-archetype output shapes, a
  framing/variety pass, a session-level anti-sameness gate, an explicit forbidden-tell list, and a resync
  of the voice guides.
- **Shared framing library.** `data/writing/framing-structure.md` is the single owner of genre/framing
  techniques both personas draw from (previously duplicated per persona).
- **Grounded in the literature.** Two adversarially-verified research passes (RAG/agent-memory, and
  authentic short-form voice) informed the design; findings recorded locally under `tasks/`.

### Context-enrichment subsystem (see `CLAUDE.md` §6, `guidelines/context-enrichment.md`, `docs/roadmap.md`)
- **What it does:** `scroll` §2.4b gathers current, resolved context about a tweet's *subject* (on-X
  research in a scoped serial tab + Codex native off-X `--search`) so drafts are specific, not generic.
- **Two-scope memory (world + self):** the persona's own documented experience plus external subject
  knowledge, seeded from history by `learn` and grown by `review`; every fact traces to captured evidence
  (enforces the no-fabrication red line).
- **Storage:** gitignored `data/context/` — human-editable Layer-1 dossiers, Layer-2 per-draft briefs,
  immutable evidence, flat chunks, and a derived rebuildable vector index; Layer-3 analytics table
  `csv/context-provenance.csv`.
- **Code seam:** `ContextStore` (swappable LanceDB+fastembed substrate) under `ContextMemory` (stable
  policy). Modes invoke it via the CLI `python -m dashboard.context_cli` — no running-server dependency.
- **Deferred (documented, not executable yet):** real `reflect()` synthesis and the `review`
  voice-authenticity ensemble — see `docs/roadmap.md`.

### Process note
The subsystem was built via review-gated workflows, then an independent Codex review found the first
build was unwired and incomplete; a remediation pass (wiring/CLI bridge, the full three-layer model,
persona isolation, evidence integrity, seam fixes) followed. Lesson recorded in `tasks/lessons.md`: build
workflows need an end-to-end / spec-conformance gate and an out-of-family reviewer, not per-component
review + unit tests alone.
