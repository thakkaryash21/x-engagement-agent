# Mode: `compose` — original tweets

last_updated: 2026-07-11
status: hand-authored procedure for AGENTS.md §4.3
entry point: AGENTS.md §4.3 links here for the full procedure

`compose` drafts original tweets — posts to the persona's own timeline, not replies. It never sends (AGENTS.md §1, principle 3) and does not take `--tagging` (that toggle is `scroll`-only, per `guidelines/tagging-playbook.md`). Browsing is for context only (the persona's own recent timeline, read to avoid repeating a point already made and to ground "what's actually happening" for build-update tweets) — mimicry rules (§3) still apply to any browsing done.

Writes to:
- `data/csv/tweets.csv` (one row per draft, `status=drafted`)
- `data/drafts/<tweet_id>.md` (the human review queue, template in §3 below)
- `data/csv/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)

---

## 0. Setup

Session Bootstrap (AGENTS.md §4.0) has already run: persona, voice guide, anti_ai_bible, style doc, territory/goals/red lines loaded; Cold-Start Guard (§5.1) passed.

From `config/limits.yaml`, hold for this session: `max_drafts_per_session`, `session_time_limit_minutes` (same caps `scroll` uses — drafts across `scroll` and `compose` sessions are counted separately per session, since each is its own session).

## 1. Topic and hook selection (`guidelines/compose-playbook.md`)

Topic = the persona's `## Territory` crossed with `data/learnings/content-playbook.md`'s `## What's working` section (once `review` has populated it; otherwise territory alone — pick whatever the persona has something genuinely current to say about).

Pick exactly one `content_type` (build-update, take, question, thread, quip) and a `hook_type` (free text) **before writing** — both get recorded in `data/csv/tweets.csv`.

**An empty session is a valid outcome — but not a default escape hatch.** Before ending a session with zero drafts, attempt at least **3 distinct angles** across the persona's territory (different `content_type`/topic pairs, e.g. a build-update, a take, and a quip). Only bail to an empty session if all attempted angles genuinely fail the drafting pipeline (nothing source-backed to say, or every draft trips the Anti-AI/anti-sameness gates) — not merely because the first idea didn't land. If there is genuine in-territory material and `tweets.csv` keeps coming back empty, that is a drafting failure to fix (style doc / voice guide / playbooks), not a signal that the territory is empty.

## 2. Draft (Anti-AI gate)

**Calibration pass (before writing)**: re-read the "Key traits from actual tweets" examples in the voice guide's Twitter/X section (`voice_guide` path) that match the chosen `content_type` (observational wit, product criticism with specificity, dry industry commentary, etc.). These calibrate **register** — sentence length, directness, casing, complete-sentence framing, how much is stated vs. implied — not content. Do not reuse a past tweet's topic, wording, or specific framing; the goal is matching the *shape* of this persona's tweet for this `content_type`, not recycling one. Once `data/learnings/content-playbook.md` has `## What's working` entries, treat those the same way — as rules about what kind of content lands, never as text to lift.

The drafting pipeline (the ordered passes and the Anti-AI hard gate) is owned by `modes/scroll.md` §2.6 — apply it verbatim here, with three compose-specific notes: (a) the calibration pass above uses the voice guide's Twitter/X examples rather than reply archetypes; (b) the anti-sameness gate (§2.6) compares each draft to this session's prior original-tweet drafts, not to reply drafts; and (c) compose runs no §2.4b Context Brief (there is no target tweet to enrich), so §2.6's two brief-dependent checks degrade as follows — **faithfulness** traces every atomic claim to `data/company-facts.md` or to retrieved memory rather than to a world brief; and **self-consistency / lived-experience** grounding comes only from an explicit Self retrieval (`python -m dashboard.context_cli search --scope self --persona <persona>`) when an original post leans on personal experience — with no Self hit, make no lived-experience claim, exactly as §2.6's context-flex rule requires. Style-exemplar retrieval (§2.6) still applies unchanged.

Apply `guidelines/format-playbooks/original-tweet.md`: the tweet must stand alone (no surrounding context to lean on), length/structure follows the voice guide for the chosen `content_type`, and never thread-bait or generic engagement-bait phrasing (hard skip per the anti-engagement-bait rule, `guidelines/target-posts.md` → Format signals / Skip signals).

### Threads (`content_type=thread`)

Only when the thought genuinely needs more than one tweet (voice guide: "no threads unless the thought genuinely needs one"). A thread's `draft_text` is the full set of tweet bodies, **in posting order, separated by a line containing exactly `===`** — this is the one place `===` is used; the draft file's own `---` dividers (§3) still mark the overall draft/alt boundaries. Each `===`-separated segment is what gets typed into one tweet in the thread (`modes/send.md` posts each segment as a reply to the previous one — see that file's thread note).

If a genuinely different angle exists, draft one **Alt** using the same pipeline (not for threads — don't manufacture an alternate thread).

## 3. Record and queue

Generate `tweet_id` as `YYYYMMDD-HHMM-<4char>`. Append a row to `data/csv/tweets.csv`. The table below documents what this mode writes; the CSV column set and the `status` enum are owned in code by `dashboard/tables.py` (schema source of truth, per `docs/file-map.md`).

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

Then write `data/drafts/<tweet_id>.md` using the original-post template owned by [docs/file-map.md](../docs/file-map.md) (Draft Markdown Template) and, in code, by `dashboard/draft_file.py` (class `DraftFile`). It is the standard draft template with the Target/Author/Tweet/Archetype/Tagging lines omitted (no target tweet exists for an original tweet); thread segments are separated by `===`. Do not restate the template fields here.

## 4. Session stop conditions

Same as `modes/scroll.md` §4 (caps and stop-logic owned by AGENTS.md §3.5): count `tweets.csv` rows with `drafted_at` in this session against `max_drafts_per_session`, and elapsed session time against `session_time_limit_minutes`.

---

## Exit criteria

`compose` is working when original-post drafts can be used for a week without incidents. An "incident" here means anything logged to `data/csv/incidents.csv` (AGENTS.md §6) — not a draft the founder simply discards, which is normal queue hygiene.


