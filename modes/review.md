# Mode: `review` — the 5-day feedback loop

last_updated: 2026-07-10
status: hand-authored procedure for AGENTS.md §4.5
entry point: AGENTS.md §4.5 links here for the full procedure

`review` is read-only with respect to drafting and sending — it never queues or posts anything (AGENTS.md §1). It visits tweets/replies that were sent ≥5 days ago, captures their current performance, and — once enough new data has accumulated — turns that performance into written learnings using the entry format and correction rule below. Browses via the same mimicry rules (§3): a review session looks like the persona checking how their old posts did.

Writes to:
- `data/csv/metrics.csv` (one row per capture; re-captures allowed, latest wins)
- `data/csv/replies.csv` / `data/csv/tweets.csv` (stamps `reviewed_at`)
- `data/learnings/content-playbook.md`, `data/learnings/timing-playbook.md`, `data/learnings/engagement-targets.md` (new/corrected entries)
- `guidelines/profile-rubric.md` (engage-gate threshold tuning, in place)
- `data/style/<persona>-twitter-style.md` (only `high`-confidence voice/phrasing rules)
- `data/csv/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)

---

## 0. Setup

Session Bootstrap (AGENTS.md §4.0) has run. `review` does not run the Cold-Start Guard (§5.1) — it analyzes what already happened, it doesn't draft.

Read `config/metrics.yaml` for `capture.layer1` / `capture.layer2` (what to record) and `optimize` (what each format is judged on).

The `metrics.csv` column set and the `status` enum on `replies.csv`/`tweets.csv` are owned in code by `dashboard/tables.py` (schema source of truth, per `docs/file-map.md`) — this mode's captures and `status`/`reviewed_at` stamps must match it.

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

---

## Exit criteria

The first batch of ≥5 reviews should produce playbook updates the operator agrees with. If a written entry doesn't hold up to the operator's read of the underlying drafts/metrics, that's a signal to revisit the grouping logic in step 3, not to lower the confidence ladder's bar.


