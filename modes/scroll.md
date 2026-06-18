# Mode: `scroll` — browse, select, draft

last_updated: 2026-06-13 (added §2.6 calibration pass against reply-playbook examples)
status: hand-authored procedure for 01-spec.md §6.1 / AGENTS.md §4.2
entry point: AGENTS.md §4.2 links here for the full procedure

`scroll` browses the persona's timeline, selects tweets worth engaging with, and drafts replies/thread-replies/quotes into the review queue. It never sends (AGENTS.md §1, principle 3). Browses via the same mimicry rules (§3) — a scroll session looks like the persona reading their feed and occasionally stopping to reply. Pass `--tagging` to additionally explore tag-in candidates per `guidelines/tagging-playbook.md`.

Writes to:
- `data/data/replies.csv` (one row per draft, `status=drafted`)
- `data/data/profiles.csv` (one row per author studied — including authors who fail the engage gate; studying is not engaging)
- `data/drafts/<reply_id>.md` (the human review queue, template in §3 below)
- `data/data/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)

---

## 0. Setup

Session Bootstrap (AGENTS.md §4.0) has already run: persona, voice guide, anti_ai_bible, style doc, territory/goals/red lines are loaded; Cold-Start Guard (§5.1) passed; Chrome is attached.

From `data/config/limits.yaml`, hold in working memory for this session:
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

Check, in order: topic filter (does it fall in the active persona's `## Territory`?), format signal (does the table in `target-posts.md` mark this format as a credible angle?), freshness/stage (<4h old, <30 replies, reply section not saturated), and hard skip signals (rage bait, ambiguous context, unverifiable claims, red-line topics).

Any failure → skip, no further steps, no profile lookup. This filter runs before studying the author on purpose: an out-of-territory tweet from a great author is still a skip.

### 2.2 Duplicate/staleness guard (AGENTS.md §5.2)

Before doing any more work on this tweet:
- Skip if any non-discarded row in `data/data/replies.csv` already has this `target_tweet_url`.
- Skip if the persona already replied to this `target_author_handle` in the same thread (same root tweet).
- Skip if this author appears in `data/data/replies.csv` with `drafted_at` (or `sent_at`, whichever is more recent) within `min_hours_between_same_author` hours.

### 2.3 Profile check (`guidelines/profile-rubric.md`)

Look up the author's handle in `data/data/profiles.csv`.
- **Not present**: visit the profile (mimicry rules apply — reading dwell, no parallel tabs), score all eight axes (category, follower_tier, role_clout, audience_activity, geography, relevance, credibility, relationship), and write a new row with `first_seen`/`last_updated` = now, `times_engaged=0`, `engagement_outcomes` empty.
- **Present**: use the existing row. Re-score only if something material has obviously changed (e.g. a large follower-count jump); otherwise reuse stored values and just bump `last_updated`.

Apply the engage decision: `relevance >= 3 AND credibility >= 3 AND (audience_activity >= 3 OR relationship != none)`. If it fails, the profile row is still saved (studying ≠ engaging) — skip to the next candidate.

### 2.4 Format decision (01-spec.md §4.5)

- If the target tweet is part of a longer thread (has parent tweets, or is itself a reply with visible ancestors), the format is **thread_reply**: expand and read the full thread first — all parents back to the root, and at least the first 20 tweets if the thread is long (`guidelines/format-playbooks/thread-reply.md`, hard rule). Note the thread position replied to.
- Otherwise, decide between **reply** and **quote** using `guidelines/format-playbooks/reply.md` and `quote.md`: quote only if the persona has a take bigger than the thread that should reach their own followers and stands alone without the quoted tweet; otherwise reply.
- If `--tagging` is on, also consider whether a tag-in (`guidelines/tagging-playbook.md`, reply-playbook.md archetype 7) makes this reply/thread-reply/quote *better* — pulling in a relevant account adds value for readers, not just reach. Tagging never changes the format itself, only whether `tagged_users` is populated.

### 2.5 Archetype decision (`guidelines/reply-playbook.md`)

Pick exactly one archetype (value-add, sharp question, contrarian-with-receipts, quip, amplify+extend, plug, or tag-in if `--tagging` and 2.4 selected it) **before** writing, informed by the chosen format playbook. The Plug archetype's hard constraint applies: any Cruitical traction number must trace to `data/company-facts.md`, otherwise the draft uses `[VERIFY: ...]`.

Before moving to drafting, do an explicit angle check:

1. Name two possible reply angles in scratch thinking: one practical/user angle and one social/company/product angle.
2. Reject angles that require Shubham to pretend to be a domain expert, especially in deep technical research, model-training methodology, hardware, government/export-policy analysis, or finance.
3. Pick the angle only if it has a concrete actor and consequence, such as "hiring managers will trust the wrong signal," "support reps need permission boundaries," "a founder can test demand faster," or "docs become part of agent onboarding."
4. If both angles are abstract, skip the tweet.

### 2.6 Draft (Anti-AI gate)

**Calibration pass (before writing)**: re-read the 2-3 real examples listed under the archetype chosen in 2.5 (`guidelines/reply-playbook.md`). These calibrate **register**, not content — sentence length, how direct vs. understated the point lands, how much setup (if any) precedes it, and the gap between what's said and what's implied. The example's topic is almost never the candidate tweet's topic. Do not borrow its wording, structure, subject matter, or specific framing — that produces an off-topic or recycled-sounding reply. The question is "what does a Shubham reply at this register sound like," never "what did Shubham say last time."

Write the draft in this order — each pass operates on the output of the previous one:

1. **Persona voice guide** (`data/personas/<active>.md` → `voice_guide` path): vocabulary, tone, territory framing, red lines.
2. **Personal style doc** (`data/style/<persona>-twitter-style.md`): apply every `## Confirmed` rule as a hard constraint; weight `## Tentative` rules lightly.
3. **Framing/engagement pass** (`data/style/<persona>-twitter-style.md` → `## Framing patterns (from Likes)`): read the draft as a reader would — does it lead with something concrete or surprising, take a position, or land on a point, or does it just restate the target tweet in a flatter, more report-like way? If it reads flat or dry, rewrite the **framing** (not the underlying idea or contribution) using one of the Confirmed/Tentative techniques in that section — e.g. lead with the specific detail before the abstract point, set up a contrast and resolve it in one beat, close on a dry understatement instead of trailing off neutrally. This pass is weighted *below* pass 2 — never override a `## Confirmed` voice rule or a red line to make something punchier.
4. **Anti-AI Bible final pass** (`anti_ai_bible` path): scan the draft against every category in the bible. This is a **hard gate** — if any tell is found (structural, lexical, rhythm, formatting), **rewrite the draft from scratch**, not patch the flagged phrase. A patched sentence in an otherwise AI-shaped draft still reads as AI-shaped. This includes tells introduced by pass 3 — a forced "not just X but Y" contrast is still a tell even if it makes the draft more "engaging."

The calibration pass and the four numbered passes are not independent rewrites — calibration sets the target register that the numbered passes should preserve while they fix vocabulary, apply style-doc rules, sharpen the framing, and strip AI tells.

If a genuinely different second angle exists, draft one **Alt** using the same pipeline. Alts are optional — don't manufacture a weak one just to fill the template.

Run these additional Shubham-specific checks before recording:

- **Read-aloud check**: would Shubham plausibly say this sentence to another founder without needing to explain what the nouns mean? If not, rewrite.
- **Actor check**: every abstract noun should resolve to a person, team, product, or decision. If the draft says "workflow," "provider," "company," "system," "edge case," or "model" without a clear referent, rewrite.
- **Contribution check**: the reply must add a concrete observation, joke, question, or relationship-building note. A cleaned-up paraphrase of the original tweet is still a fail.
- **Forbidden phrasing check**: reject drafts containing "gets weird," "key phrase," "the real shift," "the interesting part is less," "operating system" as a metaphor, "model archaeology," "scar tissue," "frontier-lab shaped," or "becomes boring."
- **Expertise check**: if the draft sounds like a researcher/operator in a domain Shubham has not shown expertise in, skip the tweet instead of rewriting.

### 2.7 Record and queue

Generate `reply_id` as `YYYYMMDD-HHMM-<4char>`. Append a row to `data/data/replies.csv`:

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

Update the author's row in `data/data/profiles.csv`: increment `times_engaged` by 1 and append a short entry to `engagement_outcomes` (e.g. "drafted value-add reply, pending send") — this is the ledger `learn` mode and future profile checks build on.

Then write `data/drafts/<reply_id>.md` using the template in §3.

## 3. Draft file template

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

Additional lines, only when applicable, go directly under the Format/Archetype/Tagging line:

- **Thread-reply**: add `**Thread position**: <n of m>` (per `guidelines/format-playbooks/thread-reply.md`).
- **Tagging**: when `tagged_users` is non-empty, add `**Tags**: @handle (category, follower_tier, relationship: <value>)` (per `guidelines/tagging-playbook.md`) — this is the prominent callout the dashboard later surfaces.

## 4. Session stop conditions

Check after every drafted item (and between candidates that were skipped, since time still passes while scrolling):
- `len(replies.csv rows with drafted_at in this session) >= max_drafts_per_session` → stop.
- elapsed session time `>= session_time_limit_minutes` → stop.

Whichever comes first ends the session. Stopping mid-loop is normal — there is no partial-candidate state to clean up, since steps only write to disk at 2.7 (after a candidate is fully decided).

---

## Exit criteria

Per 01-spec.md §11 Phase 3: a 10-draft session where the founder would send ≥5 drafts unedited. If fewer than half the drafts are send-ready, the fix is to the style doc and playbooks (re-run `learn`, or hand-edit `data/style/<persona>-twitter-style.md` and the guideline files) — not to this procedure.


