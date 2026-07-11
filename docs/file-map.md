# File Map And Data Ownership

last_updated: 2026-07-10
status: canonical routing guide for agents and maintainers

This project is file-backed. CSV files, Markdown files, YAML files, and draft files are all part of the database. Do not move, rename, or change their schemas/templates casually. If a schema or template needs to change, document the change first and update every reader/writer together.

## Public Runtime Contract

These files are committed and define reusable behavior:

- `AGENTS.md`: runtime behavior contract, active mode router, browser safety rules, and session bootstrap.
- `CLAUDE.md`: development/onboarding guide for changing the repo.
- `docs/file-map.md`: this routing guide. Update this when any file responsibility changes.
- `docs/data-boundary.md`: public/private boundary and publish checks.
- `modes/*.md`: exact operating procedures for `learn`, `scroll`, `compose`, `send`, and `review`.
- `guidelines/*.md`: reusable public playbooks and rubrics.
- `guidelines/context-enrichment.md`: persona-neutral context-acquisition intelligence (context-type taxonomy, source-selection matrix, query-construction playbook, the four adapters + gap router) driving `modes/scroll.md` §2.4b.
- `guidelines/format-playbooks/*.md`: format-specific drafting rules.
- `dashboard/README.md`: dashboard behavior and limitations.

Public playbooks should stay persona-neutral. Persona-specific examples, real handles, company facts, voice quirks, local network notes, and private lessons belong under `data/`.

## Config

These files are committed and contain non-sensitive defaults:

- `config/app.yaml`: app wiring such as `data_root`, dashboard port, and agent command.
- `config/limits.yaml`: draft/session/send limits and pacing defaults.
- `config/metrics.yaml`: metric capture and optimization defaults.

Do not put private persona/company data in `config/`.

## Private Data Root

`data/` is ignored by git. It is the private runtime database:

- `data/personas/<name>.md`: persona identity, handle, Chrome profile, voice guide path, style doc path, company facts path, territory, goals, and red lines.
- `data/company-facts.md`: verified company/product facts. Per the no-fact-invention rule (AGENTS.md §6), any factual company claim in a draft must trace here or to another local source named by the persona.
- `data/style/<persona>-twitter-style.md`: learned voice/style rules from `learn` and human edits. This is a drafting cornerstone.
- `data/writing/**/*.md`: private writing guides, voice guides, anti-AI guidance, and iteration rules.
- `data/learnings/content-playbook.md`: content patterns learned from review and human audit.
- `data/learnings/timing-playbook.md`: timing patterns learned from review.
- `data/learnings/engagement-targets.md`: target-selection and engagement-pattern learnings.
- `data/learnings/*`: persona-specific calibration, private examples, local network notes, and override files.
- `data/drafts/*.md`: active human review queue.
- `data/drafts/sent/`: sent draft archive.
- `data/drafts/discarded/`: discarded draft archive.

Markdown under `data/` is database state. Preserve headings and metadata fields unless a documented migration says otherwise.

## CSV Database

`data/csv/` is ignored by git and contains structured runtime rows:

- `replies.csv`: reply, thread-reply, and quote draft/send/review rows.
- `tweets.csv`: original post draft/send/review rows.
- `metrics.csv`: review-mode metric captures.
- `profiles.csv`: studied author/account profiles.
- `incidents.csv`: browser/account/security/UI incidents and lockout state.
- `learn-progress.csv`: resumable learn-mode progress.
- `context-provenance.csv`: Layer 3 context-enrichment review index, keyed to `reply_id` (join to `replies.csv`) — records `context_used`, `gap_type`, `n_lookups`, `source_types`, `dossier_slugs`, and `scope_blend` (world/self/both) for context→engagement joins in `review` mode.

Do not change CSV headers without updating every mode, dashboard reader/writer, example CSV, and this document.

**Executable owner:** the CSV schemas (column order) and the draft-status enum are owned in code by `dashboard/tables.py` (the `tables` definitions and `STATUS` enum). The mode column tables (`modes/scroll.md` §2.7, `modes/compose.md` §3, `modes/review.md`) describe what each mode writes at each stage, but `dashboard/tables.py` is the schema source of truth — if a header or `status` value changes, update it there and reconcile this document and every mode table with it.

## Draft Markdown Template

This section is the canonical **prose** spec for the draft file layout. In code, the parse/serialize implementation is owned by `dashboard/draft_file.py` (class `DraftFile`); the mode docs (`modes/scroll.md` §3, `modes/compose.md` §3) reference this section rather than restating the template. Keep all three in sync when the template changes.

Reply/thread/quote drafts use this structure:

```markdown
# Draft <reply_id>
**Target**: <target_tweet_url>
**Author**: @<handle> — <category>, <follower_tier>, relevance <n>, credibility <n>
**Tweet**: <quoted/paraphrased text of the target tweet>
**Format**: <reply|thread_reply|quote>        **Archetype**: <archetype>        **Tagging**: <none | @handle>

---
<draft text — exactly what would be typed into the reply box>
---

Alt (different angle, optional):
<one alternate>
```

Original-post drafts omit target/author/tweet/archetype/tagging lines and use:

```markdown
# Draft <tweet_id>
**Content type**: <content_type>        **Hook**: <hook_type>

---
<draft text — exactly what would be typed; thread segments separated by `===`>
---

Alt (different angle, optional):
<one alternate — non-thread drafts only>
```

The dashboard parses and rewrites draft bodies around the `---` separators (implemented in `dashboard/draft_file.py`). Do not change this template without updating `dashboard/draft_file.py`, the dashboard, and the mode docs together.

## Public Examples

`example/data/` mirrors the private data shape with safe starter files:

- `example/data/personas/`
- `example/data/company-facts.md`
- `example/data/csv/`
- `example/data/drafts/`
- `example/data/learnings/`
- `example/data/style/`
- `example/data/writing/`

Examples must stay sanitized. Real persona data and real company data stay under ignored `data/`.

## Routing Rules

- Need to change behavior? Start in `AGENTS.md`, then the relevant `modes/*.md`.
- Need to change a reusable public rubric? Edit `guidelines/*.md`.
- Need to change a persona's voice, examples, network context, or company-specific rules? Edit `data/personas/`, `data/style/`, or `data/learnings/`.
- Need to change factual company/product claims? Edit `data/company-facts.md`.
- Need to change dashboard file IO? Update `dashboard/file_store.py`, dashboard docs, and this file map.
- Need to change CSV headers or draft templates? Stop and document the migration before editing.
