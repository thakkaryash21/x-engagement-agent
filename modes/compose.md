# Mode: `compose` — original tweets

last_updated: 2026-06-13 (added §2 calibration pass against voice guide's Twitter/X examples)
status: hand-authored procedure for 01-spec.md §4.5 / AGENTS.md §4.3
entry point: AGENTS.md §4.3 links here for the full procedure

`compose` drafts original tweets — posts to the persona's own timeline, not replies. It never sends (AGENTS.md §1, principle 3) and does not take `--tagging` (that toggle is `scroll`-only, per `guidelines/tagging-playbook.md`). Browsing is for context only (the persona's own recent timeline, read to avoid repeating a point already made and to ground "what's actually happening" for build-update tweets) — mimicry rules (§3) still apply to any browsing done.

Writes to:
- `data/data/tweets.csv` (one row per draft, `status=drafted`)
- `data/drafts/<tweet_id>.md` (the human review queue, template in §3 below)
- `data/data/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)

---

## 0. Setup

Session Bootstrap (AGENTS.md §4.0) has already run: persona, voice guide, anti_ai_bible, style doc, territory/goals/red lines loaded; Cold-Start Guard (§5.1) passed.

From `data/config/limits.yaml`, hold for this session: `max_drafts_per_session`, `session_time_limit_minutes` (same caps `scroll` uses — drafts across `scroll` and `compose` sessions are counted separately per session, since each is its own session).

## 1. Topic and hook selection (`guidelines/compose-playbook.md`)

Topic = the persona's `## Territory` crossed with `data/learnings/content-playbook.md`'s `## What's working` section (once `review` has populated it; otherwise territory alone — pick whatever the persona has something genuinely current to say about).

Pick exactly one `content_type` (build-update, take, question, thread, quip) and a `hook_type` (free text) **before writing** — both get recorded in `data/data/tweets.csv`.

**An empty session is a valid outcome.** If nothing in-territory feels genuine right now, end the session with zero drafts rather than drafting something just to fill the cap.

## 2. Draft (Anti-AI gate)

**Calibration pass (before writing)**: re-read the "Key traits from actual tweets" examples in the voice guide's Twitter/X section (`voice_guide` path) that match the chosen `content_type` (observational wit, product criticism with specificity, dry industry commentary, etc.). These calibrate **register** — sentence length, directness, lowercase-casual vs. complete-sentence framing, how much is stated vs. implied — not content. Do not reuse a past tweet's topic, wording, or specific framing; the goal is matching the *shape* of a Shubham tweet for this `content_type`, not recycling one. Once `data/learnings/content-playbook.md` has `## What's working` entries, treat those the same way — as rules about what kind of content lands, never as text to lift.

Same pipeline as `modes/scroll.md` §2.6: persona voice guide → personal style doc (`## Confirmed` hard, `## Tentative` light) → framing/engagement pass (`data/style/<persona>-twitter-style.md` → `## Framing patterns (from Likes)`, weighted below the style doc — if the draft reads flat or report-like, rewrite its framing, not its idea) → Anti-AI Bible final pass (hard gate — any tell found, including ones introduced by the framing pass, means rewrite from scratch, not patch).

Apply `guidelines/format-playbooks/original-tweet.md`: the tweet must stand alone (no surrounding context to lean on), length/structure follows the voice guide for the chosen `content_type`, and never thread-bait or generic engagement-bait phrasing (hard skip per the anti-engagement-bait rule, AGENTS.md §6).

### Threads (`content_type=thread`)

Only when the thought genuinely needs more than one tweet (voice guide: "no threads unless the thought genuinely needs one"). A thread's `draft_text` is the full set of tweet bodies, **in posting order, separated by a line containing exactly `===`** — this is the one place `===` is used; the draft file's own `---` dividers (§3) still mark the overall draft/alt boundaries. Each `===`-separated segment is what gets typed into one tweet in the thread (`modes/send.md` posts each segment as a reply to the previous one — see that file's thread note).

If a genuinely different angle exists, draft one **Alt** using the same pipeline (not for threads — don't manufacture an alternate thread).

## 3. Record and queue

Generate `tweet_id` as `YYYYMMDD-HHMM-<4char>`. Append a row to `data/data/tweets.csv`:

| Column | Value at draft time |
|---|---|
| `tweet_id`, `drafted_at`, `persona` | new ID, now, active persona |
| `topic` | the matched territory item (§1) |
| `content_type`, `hook_type` | from §1 |
| `draft_text` | the drafted tweet (or `===`-separated thread segments) |
| `final_text`, `user_edited`, `edit_summary` | empty — filled by `send` |
| `status` | `drafted` |
| `sent_at`, `sent_day_of_week`, `sent_hour_local` | empty — filled by `send` |
| `review_due`, `reviewed_at` | empty — filled by `send` / `review` |

Then write `data/drafts/<tweet_id>.md`:

```markdown
# Draft <tweet_id>
**Content type**: <content_type>        **Hook**: <hook_type>

---
<draft text — exactly what would be typed; thread segments separated by `===`>
---

Alt (different angle, optional):
<one alternate — non-thread drafts only>
```

This is the spec §6.1 template with the Target/Author/Tweet/Archetype/Tagging lines omitted (no target tweet exists for an original tweet, per `guidelines/format-playbooks/original-tweet.md`).

## 4. Session stop conditions

Same as `modes/scroll.md` §4: stop when `len(tweets.csv rows with drafted_at in this session) >= max_drafts_per_session`, or elapsed session time `>= session_time_limit_minutes`, whichever first.

---

## Exit criteria

Per 01-spec.md §11 Phase 6: `--tagging` (already wired in `modes/scroll.md` §2.4/§2.5 and `guidelines/tagging-playbook.md`) and `compose` are used in anger for a week without incident. An "incident" here means anything logged to `data/data/incidents.csv` (AGENTS.md §6) — not a draft the founder simply discards, which is normal queue hygiene.


