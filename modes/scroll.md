# Mode: `scroll` — browse, select, draft

last_updated: 2026-07-10 (deduped shared facts to owning files; rewrote §2.6 pass 3 for variety; added anti-sameness gate)
status: hand-authored procedure for AGENTS.md §4.2
entry point: AGENTS.md §4.2 links here for the full procedure

`scroll` browses the persona's timeline, selects tweets worth engaging with, and drafts replies/thread-replies/quotes into the review queue. It never sends (AGENTS.md §1, principle 3). Browses via the same mimicry rules (§3) — a scroll session looks like the persona reading their feed and occasionally stopping to reply. Pass `--tagging` to additionally explore tag-in candidates per `guidelines/tagging-playbook.md`.

Writes to:
- `data/csv/replies.csv` (one row per draft, `status=drafted`)
- `data/csv/profiles.csv` (one row per author studied — including authors who fail the engage gate; studying is not engaging)
- `data/drafts/<reply_id>.md` (the human review queue, template in §3 below)
- `data/csv/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)

---

## 0. Setup

Session Bootstrap (AGENTS.md §4.0) has already run: persona, voice guide, anti_ai_bible, style doc, territory/goals/red lines are loaded; Cold-Start Guard (§5.1) passed; Chrome is attached.

From `config/limits.yaml`, hold in working memory for this session:
- `max_drafts_per_session`, `session_time_limit_minutes` — hard stops (§4 below)
- `min_seconds_between_actions` / `max_seconds_between_actions` — pacing between every discrete action
- `min_hours_between_same_author`, `draft_staleness_hours` — duplicate/staleness guard inputs

If `--tagging` was passed, note it — it affects step 4 (format decision) and the `tagging_mode` column.

## 1. Candidate source

Browse the persona's home timeline (For You and Following tabs), burst-pause scrolling (§3.2). Each tweet that scrolls into view is a candidate, evaluated in order through steps 2-8 below before moving to the next.

### 1.1 Feed freshness guard

If the visible feed starts feeling stale, repetitive, or exhausted, refresh before continuing:

- Go back to the X home timeline in the same focused tab.
- Reload the page once, then wait for fresh timeline content to render.
- Resume burst-pause scrolling from the refreshed feed.

Use this before forcing drafts out of an old feed. The goal is fresh, high-fit candidates, not draining whatever stale posts happen to be visible.

## 2. Per-candidate loop

For each candidate tweet:

### 2.1 Target filter (`guidelines/target-posts.md`)

Check, in order: topic filter (does it fall in the active persona's `## Territory`?), format signal (does the table in `target-posts.md` mark this format as a credible angle?), freshness/stage (`guidelines/target-posts.md` → Freshness / stage owns the thresholds), and hard skip signals (rage bait, ambiguous context, unverifiable claims, red-line topics).

Any failure → skip, no further steps, no profile lookup. This filter runs before studying the author on purpose: an out-of-territory tweet from a great author is still a skip.

### 2.2 Duplicate/staleness guard (AGENTS.md §5.2)

Before doing any more work on this tweet:
- Skip if any non-discarded row in `data/csv/replies.csv` already has this `target_tweet_url`.
- Skip if the persona already replied to this `target_author_handle` in the same thread (same root tweet).
- Skip if this author appears in `data/csv/replies.csv` with `drafted_at` (or `sent_at`, whichever is more recent) within `min_hours_between_same_author` hours.

### 2.3 Profile check (`guidelines/profile-rubric.md`)

Look up the author's handle in `data/csv/profiles.csv`.
- **Not present**: visit the profile (mimicry rules apply — reading dwell, no parallel tabs), score all rubric axes (`guidelines/profile-rubric.md` → Rubric axes), and write a new row with `first_seen`/`last_updated` = now, `times_engaged=0`, `engagement_outcomes` empty.
- **Present**: use the existing row. Re-score only if something material has obviously changed (e.g. a large follower-count jump); otherwise reuse stored values and just bump `last_updated`.

Apply the engage decision from `guidelines/profile-rubric.md` (Engage decision). If it fails, the profile row is still saved (studying ≠ engaging) — skip to the next candidate.

### 2.4 Format decision

- If the target tweet is part of a longer thread (has parent tweets, or is itself a reply with visible ancestors), the format is **thread_reply**: before drafting, expand and read the full thread per the hard rule owned by `guidelines/format-playbooks/thread-reply.md`. Note the thread position replied to.
- Otherwise, decide between **reply** and **quote** using `guidelines/format-playbooks/reply.md` and `quote.md`: quote only if the persona has a take bigger than the thread that should reach their own followers and stands alone without the quoted tweet; otherwise reply.
- If `--tagging` is on, also consider whether a tag-in (`guidelines/tagging-playbook.md`, reply-playbook.md archetype 7) makes this reply/thread-reply/quote *better* — pulling in a relevant account adds value for readers, not just reach. Tagging never changes the format itself, only whether `tagged_users` is populated.

### 2.5 Archetype decision (`guidelines/reply-playbook.md`)

Pick exactly one archetype (value-add, sharp question, contrarian-with-receipts, quip, amplify+extend, plug, or tag-in if `--tagging` and 2.4 selected it) **before** writing, informed by the chosen format playbook. The Plug archetype's hard constraint is the no-fact-invention rule (AGENTS.md §6): any company/product claim that isn't source-backed uses `[VERIFY: ...]`.

Before moving to drafting, do an explicit angle check:

1. Name two possible reply angles in scratch thinking: one practical/user angle and one social/company/product angle.
2. Reject angles that require the persona to pretend to be a domain expert, especially in specialist technical research, model-training methodology, hardware, government/export-policy analysis, finance, or any topic outside the persona's documented territory.
3. Pick the angle only if it has a concrete actor and consequence, such as "hiring managers will trust the wrong signal," "support reps need permission boundaries," "a founder can test demand faster," or "docs become part of agent onboarding."
4. If both angles are abstract, skip the tweet.

### 2.6 Draft (Anti-AI gate)

**Calibration pass (before writing)**: re-read the public archetype notes in `guidelines/reply-playbook.md`, then any local persona-specific calibration under `data/style/` and `data/learnings/`. These calibrate **register**, not content — sentence length, how direct vs. understated the point lands, how much setup (if any) precedes it, and the gap between what's said and what's implied. The example's topic is almost never the candidate tweet's topic. Do not borrow its wording, structure, subject matter, handle, or specific framing. The question is "what does this persona sound like at this register," never "what did this persona say last time."

Write the draft in this order — each pass operates on the output of the previous one:

1. **Persona voice guide** (`data/personas/<active>.md` → `voice_guide` path): vocabulary, tone, territory framing, red lines.
2. **Personal style doc** (`data/style/<persona>-twitter-style.md`): apply every `## Confirmed` rule as a hard constraint; weight `## Tentative` rules lightly.
3. **Framing/variety pass** (`data/style/<persona>-twitter-style.md` → `## Framing patterns (from Likes)`): read the draft as a reader would — does it lead with something concrete or surprising, take a position, or land on a point, or does it just restate the target tweet in a flatter, more report-like way? Then — and this is the pass's real job — pick a framing that **differs from this session's prior drafts**. Do not converge every reply on the same "lead with a contrast, resolve in one beat, land a punchy clincher" mold: punchiness has one shape, and a whole session of identically-shaped replies is the failure this pass exists to prevent. When you rewrite the framing (never the underlying idea or contribution), draw from the Confirmed/Tentative techniques in that section **and** match the framing to the chosen archetype's **Output shape** in `guidelines/reply-playbook.md`, so that `quip` ≠ `value-add` ≠ `sharp question` ≠ `amplify` in the final text.

   **Forbidden tell families** (hard reject — rewrite from a different angle, do not patch). These pass lexical checks but are exactly the mold this pipeline over-produces:
   - `[stat/number] is the signal` / `is the line` / `is the tell` — declaring what a number "really" signals.
   - `X is doing a lot here` — crediting one element with hidden weight.
   - `the useful [role] is the one who can…` — defining the valuable person via a capability.
   - `now the hard part is [A, B, and C]` — a rule-of-three pivot appended after a concession.
   - a **fabricated quote as the clincher** — a made-up maxim in "quotes" used as the closing line.

   This pass is weighted *below* pass 2 — never override a `## Confirmed` voice rule or a red line to make something more varied.
4. **Anti-AI Bible final pass** (`anti_ai_bible` path): scan the draft against every category in the bible. This is a **hard gate** — if any tell is found (structural, lexical, rhythm, formatting), **rewrite the draft from scratch**, not patch the flagged phrase. A patched sentence in an otherwise AI-shaped draft still reads as AI-shaped. This includes tells introduced by pass 3 — a forced "not just X but Y" contrast, or any of the forbidden tell families above, is still a tell even if it makes the draft more "engaging."

The calibration pass and the four numbered passes are not independent rewrites — calibration sets the target register that the numbered passes should preserve while they fix vocabulary, apply style-doc rules, vary the framing, and strip AI tells.

**Design-it-twice (mandatory for `value-add` and `amplify+extend`)**: these two archetypes are the ones that collapse into the mold, so for them draft a **second, structurally different angle** through the same pipeline — different opener, different skeleton, not the same move reworded. Keep the less formulaic of the two as the draft, and record the other as the **Alt**. For the other archetypes an Alt is optional — draft one only if a genuinely different second angle exists, and don't manufacture a weak one just to fill the template.

Run these draft-quality checks before recording:

- **Anti-sameness gate (session-level)**: compare this draft's skeleton — its opener and its structural move — against every draft already recorded this session (§2.7). If the opener or the structure repeats one already used (especially the "[number] → what it signals → knowing second-order caveat" move), rewrite from a different angle before recording. This is the cross-draft locality the per-draft Anti-AI gate cannot provide: each draft can pass the bible individually while the session as a whole reads identical.

- **Read-aloud check**: would the persona plausibly say this sentence to the intended audience without needing to explain what the nouns mean? If not, rewrite.
- **Actor check**: every abstract noun should resolve to a person, team, product, or decision. If the draft says "workflow," "provider," "company," "system," "edge case," or "model" without a clear referent, rewrite.
- **Contribution check**: the reply must add a concrete observation, joke, question, or relationship-building note. A cleaned-up paraphrase of the original tweet is still a fail.
- **Forbidden phrasing check**: reject drafts containing "gets weird," "key phrase," "the real shift," "the interesting part is less," "operating system" as a metaphor, "model archaeology," "scar tissue," "frontier-lab shaped," or "becomes boring."
- **Expertise check**: if the draft sounds like an expert in a domain the persona has not shown expertise in, skip the tweet instead of rewriting.

### 2.7 Record and queue

Generate `reply_id` as `YYYYMMDD-HHMM-<4char>`. Append a row to `data/csv/replies.csv`. The table below documents what this mode writes at draft time; the CSV column set and the `status` enum are owned in code by `dashboard/tables.py` (schema source of truth, per `docs/file-map.md`).

| Column | Value at draft time |
|---|---|
| `reply_id`, `drafted_at`, `persona` | new ID, now, active persona |
| `format` | `reply` \| `thread_reply` \| `quote` (2.4) |
| `target_tweet_url`, `target_tweet_summary` | the candidate tweet's URL and a short quote/paraphrase |
| `thread_position` | for `thread_reply`, which position in the thread was replied to; otherwise empty |
| `target_author_handle`, `target_author_category`, `target_follower_tier` | from the profile row (2.3) |
| `tweet_topic` | the matched territory item (2.1) |
| `tweet_format` | the matched format signal from `target-posts.md` (question, hot take, build-in-public, etc.) |
| `reply_archetype` | from 2.5 |
| `tagging_mode` | `on` if this session ran with `--tagging`, else `off` |
| `tagged_users` | handle(s) tagged, if 2.4 selected a tag-in; otherwise empty |
| `draft_text` | the drafted reply, exactly as it would be typed |
| `final_text`, `user_edited`, `edit_summary` | empty — filled by `send` |
| `status` | `drafted` |
| `sent_at`, `sent_day_of_week`, `sent_hour_local`, `persona_follower_count_at_send` | empty — filled by `send` |
| `target_tweet_views_at_draft` | the view count visible on the target tweet right now, if shown |
| `reply_rank` | roughly how many replies already exist on the target tweet |
| `review_due`, `reviewed_at` | empty — filled by `send` / `review` |

Update the author's row in `data/csv/profiles.csv`: increment `times_engaged` by 1 and append a short entry to `engagement_outcomes` (e.g. "drafted value-add reply, pending send") — this is the ledger `learn` mode and future profile checks build on.

Then write `data/drafts/<reply_id>.md` using the template in §3.

## 3. Draft file template

The reply/thread/quote draft template is owned by the prose spec in [docs/file-map.md](../docs/file-map.md) (Draft Markdown Template) and, in code, by `dashboard/draft_file.py` (class `DraftFile`). Write the file to match that template exactly — do not restate its fields here.

Additional lines, only when applicable, go directly under the Format/Archetype/Tagging line:

- **Thread-reply**: add `**Thread position**: <n of m>` (per `guidelines/format-playbooks/thread-reply.md`).
- **Tagging**: when `tagged_users` is non-empty, add `**Tags**: @handle (category, follower_tier, relationship: <value>)` (per `guidelines/tagging-playbook.md`) — this is the prominent callout the dashboard later surfaces.

## 4. Session stop conditions

Session caps and the stop-logic are owned by AGENTS.md §3.5. For `scroll`, the two relevant caps are `max_drafts_per_session` and `session_time_limit_minutes`. Check them after every drafted item, and between candidates that were skipped too (time still passes while scrolling): count `replies.csv` rows with `drafted_at` in this session against `max_drafts_per_session`, and elapsed session time against `session_time_limit_minutes`. Stopping mid-loop is normal — there is no partial-candidate state to clean up, since steps only write to disk at 2.7 (after a candidate is fully decided).

---

## Exit criteria

A healthy scroll session produces drafts where the founder/operator would send at least half unedited. If fewer than half the drafts are send-ready, the fix is to the style doc and playbooks (re-run `learn`, or hand-edit `data/style/<persona>-twitter-style.md` and local learning files) — not to this procedure.


