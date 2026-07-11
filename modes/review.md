# Mode: `review` — the 5-day feedback loop

last_updated: 2026-07-11
status: hand-authored procedure for AGENTS.md §4.5
entry point: AGENTS.md §4.5 links here for the full procedure

`review` is read-only with respect to drafting and sending — it never queues or posts anything (AGENTS.md §1). It visits tweets/replies that were sent ≥5 days ago, captures their current performance, and — once enough new data has accumulated — turns that performance into written learnings using the entry format and correction rule below. Browses via the same mimicry rules (§3): a review session looks like the persona checking how their old posts did.

Reads (in addition to the metric captures):
- `data/csv/context-provenance.csv` (Layer 3 context-enrichment index, keyed to `reply_id`) for the context→engagement join (§3.6)

Writes to:
- `data/csv/metrics.csv` (one row per capture; re-captures allowed, latest wins)
- `data/csv/replies.csv` / `data/csv/tweets.csv` (stamps `reviewed_at`)
- `data/learnings/content-playbook.md`, `data/learnings/timing-playbook.md`, `data/learnings/engagement-targets.md` (new/corrected entries; `engagement-targets.md` also receives the context→engagement findings, §3.6)
- `guidelines/profile-rubric.md` (engage-gate threshold tuning, in place)
- `data/style/<persona>-twitter-style.md` (only `high`-confidence voice/phrasing rules)
- the context memory subsystem, through the context CLI (`python -m dashboard.context_cli`, the bridge over the policy layer `ContextMemory` in `dashboard/context_memory.py`, over `ContextStore`) only — `write-back` of sent-reply world/self chunks and `reflect` after ingesting metrics (§6); never by editing chunk/index files directly
- a voice-authenticity dashboard — the ensemble read of §7 (three signals side by side, not one score). **Planned / not yet executable** (Plan 08 Decisions): §7 describes a future feature; no authenticity dashboard is implemented today, so a `review` session writes nothing here yet.
- `data/csv/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)

---

## 0. Setup

Session Bootstrap (AGENTS.md §4.0) has run. `review` does not run the Cold-Start Guard (§5.1) — it analyzes what already happened, it doesn't draft.

Read `config/metrics.yaml` for `capture.layer1` / `capture.layer2` (what to record) and `optimize` (what each format is judged on).

The `metrics.csv` column set and the `status` enum on `replies.csv`/`tweets.csv` are owned in code by `dashboard/tables.py` (schema source of truth, per `docs/file-map.md`) — this mode's captures and `status`/`reviewed_at` stamps must match it. `csv/context-provenance.csv` (Layer 3) is owned by the same schema source; `review` reads it for the join in §3.6.

The context memory subsystem is reached **only** through the context CLI (`python -m dashboard.context_cli`, the runtime bridge over the stable policy layer `ContextMemory`, which sits over the swappable substrate `ContextStore`). `review` uses the CLI's `write-back` and `reflect` subcommands in §6 and `style-exemplars` in §7. It never reads or writes the chunk/evidence/index files under `data/context/` directly — the policy layer owns distill, dedup/merge, the promotion gate, evidence preservation, the retrieval score blend, and reflection.

## 1. Find due items

Scan `data/csv/replies.csv` and `data/csv/tweets.csv` for rows where `status=sent`, `review_due <= today`, and `reviewed_at` is empty. This is the due set for this session. If empty, stop — nothing to review.

## 2. Capture (layered)

For each due item, in order:

1. Navigate to the item's tweet (its own `target_tweet_url` for replies/quotes is the *target's* URL — the item's own posted tweet is what you're capturing metrics for; for replies/quotes/thread-replies this is the persona's reply under `target_tweet_url`, for `tweet` rows it's the original post itself).
2. **Layer 1** (always): read `views, likes, replies, reposts, quotes, bookmarks` from the tweet detail page — whatever `capture.layer1` lists. Anything not visible is written `n/a:not-visible`, never guessed.
3. **Layer 2** (own posts only, when the analytics panel is available): open the analytics view and read `impressions, detail_expands, profile_visits, link_clicks, new_follows` per `capture.layer2`. Set `panel_available=true`. If the panel isn't available for this item, set `panel_available=false` and write `n/a:panel-unavailable` for every Layer-2 column.
4. **Confound columns**: note `author_liked` / `author_replied` / `author_reposted` (did the original author engage with our reply?), `follower_count_at_capture` (persona's current follower count), `notable_engagers` (handles of any high-clout accounts that engaged, if recognizable), and `target_tweet_views_at_capture` (for replies/quotes/thread-replies — how big the target tweet's stage is now, vs `target_tweet_views_at_draft`).
5. Compute `engagement_rate = (likes_l1 + replies_l1 + reposts_l1 + bookmarks_l1) / views_l1` (Layer 1, so always computable). If `views_l1` is `n/a`, write `engagement_rate=n/a:no-views`.
6. `days_since_sent = today - sent_at` (days).
7. Append a row to `data/csv/metrics.csv` with `item_id` = the `reply_id`/`tweet_id`, `item_type` = `reply | thread_reply | quote | tweet`, `captured_at` = now, and everything above. Re-captures of the same `item_id` are allowed (a later `review` run might re-check an item) — latest row wins for analysis.
8. Stamp `reviewed_at = now` on the row in `replies.csv`/`tweets.csv`.

## 3. Analyze (only when ≥5 newly reviewed items this session)

If fewer than 5 items were captured in step 2, stop here — the session has done its job (capture + `reviewed_at` stamps) but there isn't enough data for a batch-level finding. Per the confidence ladder (§4 below), single-item evidence never becomes a rule.

If ≥5, join each newly captured `metrics.csv` row back to its `replies.csv`/`tweets.csv` row and look for patterns across these five axes. **Exclude any item with `author_reposted=true` from the math in 3.1-3.4** — an author repost can multiply a reply's reach independent of the archetype/content/timing choice, so crediting it to those would be confounded; instead, log it as its own observation. The fact that the author engaged is its own signal.

### 3.1 Reply archetype × target tweet format → `engagement-targets.md`

Group by (`reply_archetype`, `tweet_format`). Compare `engagement_rate` (and the format's `optimize` metrics from `metrics.yaml`) across groups. A consistent pattern (same direction across the group's items) is a candidate entry under `## Entries (from review mode)`.

### 3.2 Content type / topic × engagement rate → `content-playbook.md`

Group by (`content_type`, `tweet_topic`/`topic`). Same comparison, using `optimize.tweet` / `optimize.reply` / `optimize.thread_reply` / `optimize.quote` depending on item type. Candidate entries under `## Entries`.

### 3.3 Sent day/hour × impressions, per content type → `timing-playbook.md`

Group by (`sent_day_of_week`, `sent_hour_local`, `content_type`/`tweet_format`). Compare `impressions_l2` where available, else `views_l1`. Note in the entry which metric was used (Layer 1 vs Layer 2 — **never compare a Layer-2 value on one item against a Layer-1 proxy on another as if equivalent**). Candidate entries under `## Entries`.

### 3.4 Target author rubric scores × outcomes → tune `profile-rubric.md`

Join `target_author_handle` to `data/csv/profiles.csv` for its rubric scores (relevance, credibility, audience_activity, relationship), and compare against `engagement_rate`/outcomes for items targeting that author. If a combination of scores below the current engage gate (owned by `guidelines/profile-rubric.md` → Engage decision) is performing as well as combinations that pass it, that's evidence the gate threshold is too strict (or too loose, in the other direction). Per the correction rule, **rewrite the gate formula in `guidelines/profile-rubric.md` in place** when evidence is `high` confidence — don't add a second, competing formula.

### 3.5 User-edited drafts × performance → fold into the style doc

For items where `user_edited=true`, compare performance against unedited items of the same `reply_archetype`/`content_type`. If edited items consistently outperform, the edit pattern (already logged to the style doc immediately at send time, per `modes/send.md` §4) gets its confidence raised here using the same promotion rule — a `## Tentative` entry reaching 3 consistent occurrences (across send-time logs and this analysis) is promoted to `## Confirmed`.

### 3.6 Context provenance × engagement → `engagement-targets.md`

Join each newly captured `metrics.csv` row to its `csv/context-provenance.csv` row by `reply_id` (and to `replies.csv` for `reply_archetype`/`tweet_format`). The Layer-3 index is what makes this a **data join, not prose-reading** — never parse a brief. A `reply_id` with no provenance row means enrichment was not done: treat it as `context_used=false`, `gap_type=none`, empty `source_types`, `scope_blend=world`.

Segment `engagement_rate` (and the format's `optimize` metrics from `metrics.yaml`) across four cuts. Each answers a distinct question about whether enrichment earns its session budget and which part of it does:

- **`context_used` (true vs false)** — do enriched drafts outperform un-enriched ones? Hold `reply_archetype`/`tweet_format` fixed across the compared groups so enrichment isn't credited with the archetype's own lift.
- **`gap_type` (none | identity | factual | temporal | discourse | relational | mixed — the §2 context-type rollup, `guidelines/context-enrichment.md` §5.1)** — which *kind* of resolved gap correlates with lift (does discourse research beat factual lookup for a given format, or the reverse).
- **`source_types` (subset of `dossier,x_navigation,x_search,web_search` — the adapter→token map in `guidelines/context-enrichment.md` §5.1)** — which adapter routes pull weight. A route that never correlates with lift is a candidate for a tighter budget.
- **`scope_blend` (world | self | both)** — does a self-anchored reply (documented lived experience) beat a world-only one? This is the content-side payoff test: if `self`/`both` consistently lifts, self-retrieval is earning its place.

Same discipline as 3.1–3.4: exclude `author_reposted=true` items from the segment math (log them as their own observation), never compare a Layer-2 value on one item against a Layer-1 proxy on another, and apply the §4 confidence ladder — a consistent same-direction pattern across the group is a candidate entry under `## Entries (from review mode)` in `data/learnings/engagement-targets.md`, written with the §4 format.

Feed the result back to the budget, always as a written entry, never silently: if enrichment (or a specific route, or self-anchoring) demonstrably lifts engagement, that's a targeting learning to keep spending on; if a route shows no lift across a consistent group, the entry's **Rule** says to tighten it (a signal for the operator to lower `max_context_lookups_per_session` in `config/limits.yaml`, or drop that route), and it supersedes any prior entry that credited it (§4 correction rule).

## 4. Write learning entries

Every new finding from 3.1-3.4 (and 3.5's promotions) is written using this format:

```markdown
### L-YYYY-MM-DD-NN — <one-line finding>
**Evidence**: <item_ids> (<metric summary> vs <baseline>)
**Rule**: <what to do differently>
**Confidence**: tentative (n<3) | medium (3-6) | high (>=7 consistent)
**Supersedes**: none | <old entry ID> — <why it died>
```

`NN` is a per-day sequence number (01, 02, ...) — check the target file for the highest existing `NN` on today's date before assigning the next one.

**Voice outranks metrics (AGENTS.md §6)**: before writing any entry, check it against the persona's voice and red lines (`data/personas/<active>.md`). A pattern that performs well but is off-voice or touches a red line is written under `content-playbook.md`'s `## Observations (off-voice outliers — never promoted to rules)` instead of `## Entries` — never as a rule, regardless of confidence.

**Correction rule**: if a new finding contradicts an existing entry (in any of the three learnings files, `profile-rubric.md`, or the style doc), **rewrite that entry in place** — update its Evidence/Rule/Confidence and set `Supersedes: <old ID> — <one-line reason>`. The contradicted text is never left standing with a correction appended after it.

**`target-posts.md` Format Signals table**: if a 3.1 finding (≥3 consistent data points) changes whether a format signal is worth replying to, update that row's "Credible angle?"/"Notes" cell in `guidelines/target-posts.md` in place, with the Notes cell pointing at the new/updated `engagement-targets.md` entry ID for the evidence — don't duplicate the evidence itself into `target-posts.md`.

## 5. Promote to style guide

Of everything written in step 4, only entries that are (a) about voice/phrasing (not targeting or timing) and (b) `high` confidence (≥7 consistent) get appended to `data/style/<persona>-twitter-style.md` under `## Confirmed` — mirroring the promote-and-remove rule. Targeting and timing rules, regardless of confidence, stay in their respective learnings files; they are read by `scroll`/`compose` via `target-posts.md`/`compose-playbook.md`/`profile-rubric.md`, not via the style doc.

## 6. Extend the context memory subsystem (both scopes + content logic)

Step 5 promotes high-confidence *voice* rules into the style docs. Symmetrically, `review` grows the *context* memory subsystem over time — through the same unified write-back the drafting and `learn` modes use (the context CLI's `write-back`, over the policy layer `ContextMemory` / `ContextStore`). **Crucial boundary — engagement is not verification.** Sending a reply documents that the persona *said* something — a legitimate **Self** observation — but it does **not** confirm any external **World** fact the reply asserted. Posting a claim, and the claim getting engagement, is evidence about the persona and the audience, never evidence that the claim is true. So the two scopes are grown from different sources here: Self from the sent text itself, World **only** from preserved evidence or a fresh re-verification — never from the mere fact the claim was posted or performed well. This runs only for items captured this session, and only from what the sent text and the reviewed sources actually evidence — **never invent** a fact or an experience (AGENTS.md §6).

For each reviewed sent item, distill and write back in both scopes plus the content dimension:

- **World** — a durable subject fact **only when this review actually re-grounded it**: it must trace to preserved evidence from the original draft-time enrichment (the immutable `evidence` record) or to a fresh re-verification performed during this review (a positioning a primary source still backs, a claim that visibly held, a subject's consolidated current state). The fact that the persona *tweeted* the claim — or that it did well — is **not** itself evidence for it: a sent assertion with no surviving evidence and no re-verification is **not** written as World memory (capture it as Self — "the persona stated X" — instead). Route each re-grounded fact as a `scope=world` finding carrying its `evidence`, so the next reply about that subject hits memory instead of re-spending a lookup. The write-back's promotion gate keeps only the *reusable* subset; a one-off detail stays out of durable memory.
- **Self** — any self-fact the sent reply publicly expressed (an opinion the persona took, a project outcome referenced, a relationship shown) → a `scope=self` finding (`source_type=persona_history`, the item's **`persona`** — required so the self chunk is isolated and routed to `self/<persona>/`; pass `--persona <persona>` on the write-back call too, `confidence` per how explicit the statement was, the sent reply text preserved as its evidence). The persona's live posting continuously grows the Self well, not just the one-time `learn` seeding — and because the chunk traces to the actual sent reply, it satisfies the documented-source rule by construction.
- **Content logic** — the "what/why content" dimension of `data/learnings/content-playbook.md` (the dimension `learn` seeds): record which well (world / self) and which context produced content that *worked* this review, sharpening the archetype + scope-blend decision the drafter makes at enrichment time. This closes the loop symmetrically with the voice-rule promotion in step 5 — outcomes teach *which well to draw from for which situation*, not just which phrasing to keep. Voice outranks metrics still holds: an off-voice pattern is an observation, never a rule.

Pass findings via the CLI — `'{"findings": [ ... ]}' | python -m dashboard.context_cli write-back --persona <persona>` (no `--reply-id`: review grows durable memory, not a per-draft brief). **`--persona <persona>` is required** — it isolates every `scope=self` finding to the reviewed item's persona and routes it to `self/<persona>/`, exactly as `learn` §6.1 does; if a session reviews items from more than one persona, split the write-back per persona rather than mixing them in one call. Each finding is a dict (`text` plus `scope` / `source_type` / `context_type` / `confidence` / `importance` / `entities` / `provenance` / `evidence`, `persona` for every `scope=self` finding, and an optional explicit `reusable` verdict). The policy layer handles distill → dedup/merge → promotion gate → store + dossier and preserves the raw evidence immutably — `review` does not touch chunk files. Re-reviewing the same item merges (bumps `last_refreshed`) rather than duplicating, because it flows through the same dedup.

**Reflection after ingest.** Once this session's metrics and write-backs are in, run `python -m dashboard.context_cli reflect --scope <world|self> --subject <slug>` **per subject** this session touched (self also passes `--persona <persona>`) — the review-side trigger for the consolidation layer, symmetric with `learn`'s per-batch reflection. Reflect **per subject, never scope-wide**: omitting `--subject` concatenates every subject into one insight that outranks the specific chunk it contains at retrieval time (and collapses to a slug-less dossier). Reflection collects the accumulated post-send observations into one refreshed `insight` chunk per scope/subject (a consolidated state for a subject that kept recurring; a gathered persona stance from many scattered opinion chunks). **Interim behaviour (planned/not-yet-executable synthesis):** today this is a *simple concatenating consolidation* — the `insight` text is a labeled join of the source chunks' texts, not a higher-level abstraction beyond them. Real synthesis is a deferred roadmap feature (`docs/roadmap.md` → Deferred); the interim pass is honestly labeled `context_type=insight` and is a step above the janitorial dedup the write-back already did, not the eventual abstraction. Run it as a batch pass at end of session, never on a hot drafting path. Reflection flows through the same dedup, so running it every `review` refreshes the one insight chunk instead of appending a duplicate each time.

## 7. Voice-authenticity ensemble (a dashboard, not one score) — PLANNED, not yet executable

> **Status (Plan 08 Decisions): deferred / not-yet-implemented (roadmap — `docs/roadmap.md` → Deferred).** This section describes a *future* feature, not a live procedure. The multi-metric authenticity ensemble is a measurement feature that only earns its keep once real sent-draft history has accumulated, and none of the three signals below is wired up today (no scorers, no thresholds, no dashboard output). A current `review` session does **not** run this step and writes nothing from it. It is documented here so the intended design is on record; treat every "compute/score/report" verb below as *what this will do once built*, not an instruction to execute now.

Beyond engagement, `review` will assess the *voice authenticity* of a session's sent drafts — but with an **ensemble of complementary signals reported as a small dashboard, never collapsed into a single number**. No single authenticity metric is trustworthy alone, and a blended score would erase the divergences between the signals, which are the actual finding. The planned signals, over the sent drafts:

- **Authorship-attribution** *(planned)* — does the sent text read as *this persona* versus a generic/AI voice? Score each sent draft against the persona's own documented voice: the style doc plus the persona's own `scope=self` exemplars from `python -m dashboard.context_cli style-exemplars --persona <persona> --k <k>` (selected for stylistic *diversity/coverage*, explicitly not topical similarity — topic-matched exemplars degrade the comparison).
- **NLI self-consistency** *(planned — no scorer/threshold implemented yet)* — how often sent drafts drift off-persona: the aggregate of the per-draft natural-language-inference persona-consistency judgment (entailment/neutral = OK, contradiction = drift) over the persona's documented self-lines. The concrete NLI model, the per-statement contradiction threshold, and the reject rule (evaluate each statement independently; reject on any material contradiction — never let one strong entailment mask a contradiction) are **not yet chosen or wired**. This is intended as the batch aggregate of the same signal the drafting gate would apply pre-send.
- **AI-detector probe** *(planned)* — a weak tell-tracker only, tracked as a *trend*, not a target to game: indistinguishability is not the goal, and the human send-gate is the backstop (AGENTS.md §1). A rising probe score is a hint to inspect the anti-AI passes, nothing more.

Once built, report the three side by side. **A divergence between them is itself the finding** — high engagement but a rising AI-detector score, or strong attribution but climbing NLI contradiction — and that divergence is what would get written to `data/learnings/` (a `content-playbook.md` observation or an `engagement-targets.md` entry) for the drafting passes to act on. Do not average them into one score. Voice outranks metrics (AGENTS.md §6): an authenticity regression is worth acting on even when engagement is up.

---

## Exit criteria

The first batch of ≥5 reviews should produce playbook updates the operator agrees with. If a written entry doesn't hold up to the operator's read of the underlying drafts/metrics, that's a signal to revisit the grouping logic in step 3, not to lower the confidence ladder's bar.


