# Mode: `send` — review, edit, post

last_updated: 2026-06-18
status: hand-authored procedure for AGENTS.md §4.4
entry point: AGENTS.md §4.4 links here for the full procedure

`send` is the only mode with a code path that posts to X, and even here every post is preceded by an explicit human decision (AGENTS.md §1, principle 3). It walks `data/drafts/` oldest-first, re-verifies each target is still live, presents the draft, and acts on the human's send / edit / discard call. Browses and types via the same mimicry rules (§3) — typing on send is character-by-character (§3.3), never pasted.

Writes to:
- `data/csv/replies.csv` / `data/csv/tweets.csv` (fills in send-time columns on the matching row)
- `data/csv/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)
- `data/style/<persona>-twitter-style.md` (immediate edit-pattern capture, §4 below)
- `data/drafts/sent/` / `data/drafts/discarded/` (moves the draft file)

---

## 0. Setup

Session Bootstrap (AGENTS.md §4.0) has already run, including the Cold-Start Guard — `send` loads drafts that were produced under that guard, so it runs too.

From `config/limits.yaml`: `max_sends_per_day`, `min_minutes_between_sends`.

Before starting the walk, count today's sends: scan `data/csv/replies.csv` and `data/csv/tweets.csv` for rows with `sent_at` on today's date. This is `sends_today` — the running count against `max_sends_per_day`. Also note the most recent `sent_at` across both CSVs (if any, today) — this is the clock for `min_minutes_between_sends`.

## 1. Walk the queue

List `data/drafts/*.md`, oldest-first by the `YYYYMMDD-HHMM` prefix of the filename (the `reply_id`/`tweet_id`). Process one at a time.

## 2. Per-draft loop

### 2.1 Identify the row

The draft filename is `<id>.md` where `<id>` is a `reply_id` or `tweet_id`. Look up `<id>` in `data/csv/replies.csv` first; if not found, look it up in `data/csv/tweets.csv`. This tells you the item type (`reply` / `thread_reply` / `quote` vs `tweet`) and gives every other field (archetype, target, draft_text, etc.) for §2.4.

If the row's `status` is already `approved` or `edited` (set by the dashboard), present it the same as any other draft — the dashboard records a human review decision, but every send still needs the in-session human gate (§1, principle 3). If `status=edited`, `draft_text` already reflects the dashboard's edit and `user_edited`/`edit_summary` are already set; note this for step 4 of §3 below.

### 2.2 Existence check (replies/thread-replies/quotes only)

Navigate to `target_tweet_url`. If the tweet is deleted, the account is gone or protected, or the reply/quote box is absent:
- Set `status=discarded` on the CSV row.
- Prepend a line to the draft file — `**Discarded**: target_gone (auto, send mode, <timestamp>)` — then move it to `data/drafts/discarded/`.
- Continue to the next draft. No human decision needed for this case.

Original tweets (`tweet` rows, no `target_tweet_url`) have nothing to verify here — skip to §2.3.

### 2.3 Staleness check

- If `now - drafted_at > draft_staleness_hours` (limits.yaml), flag the draft as **stale (age)** in the presentation (§2.4).
- For replies/thread-replies/quotes only: while on the target tweet (from §2.2), check whether the conversation has visibly moved past the draft's point — e.g. the author already gave the answer the draft's sharp question asks, or the thread's topic has shifted. If so, flag as **stale (overtaken)** and say why in one sentence.

Staleness never auto-discards (that's §2.2's job for `target_gone` only) — it's surfaced so the human can decide.

### 2.4 Present to the user

Show:
- The draft file's content (target context, draft text, alt if present, archetype/format/tagging/thread-position lines).
- Any staleness flags from §2.3, with the one-sentence reason.
- If `tagged_users` is non-empty, repeat the tagging callout from the draft file prominently.
- Remaining budget: `sends_today / max_sends_per_day`, and whether `min_minutes_between_sends` has elapsed since the last send (if not, say how much longer until this draft could be sent).

### 2.5 User decision

The user says **send**, **edit**, or **discard**.

- **discard**: set `status=discarded` on the CSV row, prepend `**Discarded**: user, <timestamp>` plus any reason the user gave to the draft file, move it to `data/drafts/discarded/`. Continue to the next draft.
- **edit**: the user provides replacement text. Set this as the text to send in §3, and remember the original `draft_text` for the diff in §4.
- **send**: use `draft_text` as-is as the text to send.

Before proceeding to §3 on send/edit: if `sends_today >= max_sends_per_day`, or `min_minutes_between_sends` hasn't elapsed since the last send today, tell the user this draft cannot be sent yet and leave it in the queue (do not move the file). Otherwise continue.

## 3. Posting

1. Navigate to where this gets typed:
   - `reply` / `thread_reply`: open the reply box on `target_tweet_url`.
   - `quote`: open the quote-tweet composer from `target_tweet_url`.
   - `tweet`: open the compose box from the persona's home/profile.
2. Type the final text **character-by-character** per §3.3 — never pasted, never injected.
3. Post.

**Threads** (`tweet` rows with `content_type=thread`, `modes/compose.md` §2): the final text is `===`-separated segments, one per tweet in posting order. Post the first segment as in steps 1-3 above. For each remaining segment: open the reply box on the tweet you just posted (the persona replying to themselves), type that segment character-by-character (§3.3), and post — with normal action pacing (§3.5) between each tweet in the thread, same as any other discrete action. `final_text` for the CSV row is the full `===`-joined thread as actually posted (post-edit if any segment was edited).

4. Fill in the CSV row (`replies.csv` or `tweets.csv`, per §2.1):
   - `final_text` = the text actually sent (post-edit if edited).
   - `user_edited` = `true` if §2.5 was `edit`, else `false` — **unless** the row already had `user_edited=true` from a dashboard edit (§2.1) and §2.5 was `send`, in which case leave the existing `true` and `edit_summary` as-is (the dashboard edit is the recorded edit for this item; don't clobber it).
   - `edit_summary` = one-line description of the diff between `draft_text` and `final_text` (empty if not edited; see exception above).
   - `sent_at` = now; `sent_day_of_week` / `sent_hour_local` derived from it.
   - `persona_follower_count_at_send` = the persona's current follower count (visit the persona's own profile if not already read this session; cache for the rest of the session).
   - `review_due` = `sent_at + 5 days`.
   - `status` = `sent`.
5. Move the draft file to `data/drafts/sent/`.
6. Increment `sends_today`; update the `min_minutes_between_sends` clock to `sent_at`.

## 4. Edit-delta capture (immediate)

If `user_edited=true`, don't wait for `review` — the human just told you what was wrong. Diff `draft_text` against `final_text` and write the pattern immediately to `data/style/<persona>-twitter-style.md`:

- If the edit reflects a phrasing/voice pattern not yet in the style doc, add it under `## Tentative`.
- If a `## Tentative` pattern now has **3 occurrences** (this edit plus prior `learn`/`review`/send-mode entries describing the same pattern), promote it to `## Confirmed`, per the same promotion rule `learn` mode uses (`modes/learn.md` §4).
- If the edit **contradicts** an existing `## Confirmed` or `## Tentative` rule, rewrite that rule in place per the correction rule in `docs/file-map.md` / `modes/review.md` and add a line to `## Correction log` — never leave the contradicted rule standing with the correction appended after it.

This keeps the style doc as the single home for voice/phrasing learnings regardless of which mode surfaced them (`send`, `review`, or `learn`).

## 5. Session end

Continue the walk until `data/drafts/` is empty, or `sends_today >= max_sends_per_day` (remaining drafts stay queued — tell the user how many are left and that the cap is reached), or the user stops the session.

---

## Exit criteria

First real sends should prove the full draft → human-gated send → CSV/file bookkeeping loop end to end before `review` has anything to act on.


