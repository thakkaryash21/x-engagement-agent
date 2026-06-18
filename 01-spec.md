# Twitter Agent — Technical Specification

last_updated: 2026-06-12
status: updated after Yash's review rounds — Shubham-first, Codex-primary, human-mimicry, layered metrics, guardrails confirmed, dashboard added (§10)
requirements: [00-requirements.md](00-requirements.md)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Codex CLI agent (runtime)                                  │
│  entry: AGENTS.md + mode prompt                             │
│                                                             │
│  reads:  data/   guidelines/   config/app.yaml              │
│  writes: data/data/*.csv   data/drafts/   data/learnings/   │
└───────────────┬─────────────────────────────────────────────┘
                │ Codex control-chrome plugin
┌───────────────▼─────────────────────────────────────────────┐
│  User's already-open Chrome, real profile, logged into X    │
└─────────────────────────────────────────────────────────────┘
```

Three principles:

1. **The browser is the only integration.** No X API, no third-party scrapers. Everything the agent knows about Twitter it learns by looking at rendered pages, exactly as a human would.
2. **Files are the whole system.** `data/` is the private runtime state; `example/data/` is the public starter template. CSVs are the database, Markdown is the intelligence, and the draft queue is a folder. The dashboard (§10) is a local view/edit layer over these same files.
3. **The agent never sends autonomously.** It drafts; the human gates every send in `send` mode.

### 1.1 Browser control: real Chrome, not Playwright

The agent attaches to the user's already-open Chrome through Codex's `control-chrome` plugin. It does not launch a separate automation browser, does not require a remote-debugging port, and does not use headless mode.

- The active persona's `chrome_profile` in `data/personas/<name>.md` tells the user which Chrome profile/account should be open.
- Pre-flight checks confirm an X/Twitter tab is open and logged in as the expected persona. If not, the session stops and asks the user to open the right browser state.
- **Human-mimicry rules** (hard requirements, codified in AGENTS.md): burst-pause scrolling, character-by-character typing, one focused tab, human-paced navigation, and no clipboard paste or JavaScript value injection.
- If X shows a challenge, unusual-activity interstitial, logged-out state, or major UI breakage, stop immediately and log the incident in `data/data/incidents.csv`.

### 1.2 Why Codex CLI shapes the layout

Codex CLI is the **primary runtime**, chosen for its browser-use ecosystem. Codex reads `AGENTS.md` at the working root the way Claude Code reads `CLAUDE.md`. The agent folder is therefore self-contained: a Codex session started in `twitter-agent/` with a one-word mode prompt ("scroll", "review") has everything it needs. Nothing in the design is Codex-specific beyond that file's name — the same tree, data, and learnings work unchanged under Claude Code, which can be used interchangeably whenever it drives the browser well enough.

---

## 2. Directory Layout

```
.
  AGENTS.md                     Runtime behavior contract and mode router
  README.md                     Public project overview and quick start
  config/app.yaml               Non-sensitive app wiring: data_root, agent command, dashboard port
  data/                         PRIVATE, gitignored runtime state
    personas/<name>.md          Real persona definitions
    company-facts.md            Verified company/product facts
    config/limits.yaml          Draft caps, pacing bounds, send caps
    config/metrics.yaml         Metrics to capture and optimize for
    data/*.csv                  CSV database
    drafts/                     Human review queue and archives
    learnings/                  Review-mode learning files
    style/                      Learned persona style docs
    writing/                    Private writing and voice guides
  example/data/                 Public starter templates and schema-only CSVs
  guidelines/                   Targeting, profile, tagging, compose, and format playbooks
  modes/                        learn, scroll, compose, send, review procedures
  dashboard/                    Local web UI over the same files
  docs/                         Public architecture and operator docs
  scripts/                      Bootstrap and sensitive-reference checks
```

`data/` is ignored by git. `example/data/` mirrors its shape so a new user can initialize a private workspace without exposing real drafts, profiles, metrics, or voice data.

---

## 3. Persona Definition

Actual persona files live in `data/personas/*.md`, which is private runtime state. Public templates live in `example/data/personas/`.

Schema:

```markdown
# Persona: Founder Name
handle: @yourhandle
chrome_profile: Default
voice_guide: ../writing/voice-guides/founder-voice-guide.md
anti_ai_bible: ../writing/anti-ai-writing-guide.md
style_doc: ../style/founder-twitter-style.md
company_facts: ../company-facts.md

---

## Territory

- Topics this persona can credibly engage on

## Goals

1. Build a relevant network
2. Earn distribution for useful ideas
3. Learn which messages resonate

## Red lines

- No fabricated personal anecdotes
- No unverified company claims; use `[VERIFY: ...]` unless a claim is in `company_facts`
- No engagement bait outside the persona's actual voice
```

The `scroll`, `compose`, and `send` modes all begin by loading the active persona plus its voice guide, learned style doc, company facts, and Anti-AI guide. Persona is selected by `AGENTS.md` or a `--persona` mode override.

---

## 4. Target Intelligence

### 4.1 `guidelines/target-posts.md` — what to look for

Hand-seeded, then maintained by `review` mode. Defines, per persona:

- **Topic filters**: tweets inside the persona's territory.
- **Format signals**: questions, hot takes, build-in-public updates, technical threads, launch posts — each mapped to whether the persona has a credible angle.
- **Freshness/stage**: prefer tweets <4h old with <30 replies (early replies earn disproportionate visibility); skip tweets where the reply section is already saturated with the same take.
- **Skip signals**: rage bait, ambiguous context, threads requiring claims we can't verify, anything touching red lines.

### 4.2 `guidelines/reply-playbook.md` — reply archetypes

Each archetype gets: definition, when it fits, 2–3 real examples (harvested by learn mode from the user's own history), and known failure modes.

Initial archetype set:
1. **Value-add** — concrete experience, data, or resource that extends the tweet
2. **Sharp question** — the question others wish they'd asked
3. **Contrarian-with-receipts** — respectful disagreement backed by specifics
4. **Quip** — humor in the persona's register (style doc defines the register)
5. **Amplify + extend** — agree, then add the missing half
6. **Plug** — Cruitical-relevant only when organically on-topic; never cold
7. **Tag-in** (toggle mode only, §4.4)

The drafting step picks the archetype *before* writing, and records it in the CSV — this is what lets the review loop learn "which reply types work on which tweet types."

### 4.3 `guidelines/profile-rubric.md` — author categorization

When the agent considers engaging, it studies the author and writes/updates a row in `profiles.csv`. The rubric scores the four decision questions from the requirements:

| Axis | Values |
|---|---|
| category | founder / VC / engineer / researcher / anon-builder / journalist / recruiter / other |
| follower_tier | nano <1k / small 1–10k / mid 10–100k / large 100k–1M / mega >1M |
| role_clout | 1–5 (positional authority: known company, known fund, known project) |
| audience_activity | 1–5 (do their tweets get real replies, or is it a ghost town?) |
| geography | best-effort from bio/content |
| relevance | 1–5 (overlap with persona territory + Cruitical) |
| credibility | 1–5 (track record, verifiable claims, not a clout-farmer) |
| relationship | none / they-follow / we-follow / mutual / real-life connection |

**Engage decision** = territory match (4.1) AND no red-line AND a simple gate on the rubric: `relevance ≥ 3 AND credibility ≥ 3 AND (audience_activity ≥ 3 OR relationship ≠ none)`. The gate thresholds live in the rubric file so `review` mode can tune them with evidence.

### 4.4 `guidelines/tagging-playbook.md` — the tagging toggle

Active only when `scroll` runs with `--tagging`. Explores whether a reply/quote is *better* composed by tagging a relevant high-profile user, connection, or follower: pulling them into the discussion, a shoutout/plug, or a humorous quip. Rules:

- The tag must add value for *readers* (a genuinely relevant person/thread), never pure reach-grabbing.
- **Guardrail is surfacing, not an allowlist**: any draft that tags someone is prominently called out in the dashboard review card — "this draft tags @handle (category, follower tier, relationship: never interacted)" — so the human makes the call per draft with full context. The agent never needs pre-approval to *propose* a tag, only to send one (which is true of everything).
- Learn mode seeds this playbook from the user's own historical tagging tweets — the requirements note the user's history shows how value-adding, engagement-driving tag-tweets are composed.
- Tagged drafts are flagged `tagged_users` in the CSV and marked prominently in the draft file, since they carry higher social risk and deserve closer human review.

### 4.5 Engagement formats — each type is its own discipline

Every draftable item has exactly one **format**, recorded in the CSV, and each format has its own playbook file under `guidelines/format-playbooks/` with clear, format-specific instructions. The agent never treats these interchangeably:

- **Reply** — joins an existing conversation; read by people scrolling that thread. Optimize for adding to the discussion in place. Rules in `reply-playbook.md` (§4.2).
- **Thread reply** — a reply to a tweet that is itself part of a thread. **Hard rule: before drafting, expand and read the full thread** (parents and, if long, at least the first 20 tweets), so the reply engages the thread's actual argument, not just the leaf tweet. The draft file must note which thread position was replied to.
- **Quote tweet** — amplifies the original to the persona's own followers; it must stand alone for readers who never open the quoted tweet, and it spends the persona's own credibility on someone else's content. Different reach mechanics from replies; the format playbook covers standalone-readability, when a quote beats a reply (you have a take bigger than the thread) and when it's worse (your point only makes sense inside the conversation).
- **Original tweet** (`compose` mode) — selection logic lives in `compose-playbook.md`: topic comes from the persona's territory crossed with what `content-playbook.md` says is working; `content_type` (build-update, take, question, thread, quip) and `hook_type` are chosen explicitly before writing and recorded in `tweets.csv` so the review loop can attribute performance.

Adding a new format later (e.g. long-form posts) means adding a playbook file and a `format` value — no core-logic change.

---

## 5. Data Layer — CSV Schemas

All CSVs are UTF-8, header row, append-mostly (status/metric columns get updated in place). IDs are `YYYYMMDD-HHMM-<4char>`.

**Single-session assumption**: exactly one agent session runs at a time (operator-enforced; this is a single-user tool on one machine). No file locking is needed. If that assumption ever changes, revisit this section.

### 5.1 `replies.csv` and `tweets.csv`

`replies.csv`:

```
reply_id, drafted_at, persona, format(reply|thread_reply|quote),
target_tweet_url, target_tweet_summary, thread_position,
target_author_handle, target_author_category, target_follower_tier,
tweet_topic, tweet_format, reply_archetype, tagging_mode, tagged_users,
draft_text, final_text, user_edited, edit_summary,
status, sent_at, sent_day_of_week, sent_hour_local,
persona_follower_count_at_send, target_tweet_views_at_draft, reply_rank,
review_due, reviewed_at
```

- `persona_follower_count_at_send`: normalizes performance against account growth over time.
- `target_tweet_views_at_draft`: how big the stage was when we stepped onto it.
- `reply_rank`: roughly how many replies preceded ours (tests the early-reply hypothesis directly).

- `status`: drafted → approved | edited | discarded → sent
- `user_edited` + `edit_summary`: captured by `send` mode; the delta between `draft_text` and `final_text` is a learning signal exactly like cru-write's Step 8a.
- `review_due` = `sent_at + 5 days`.

`tweets.csv` (original posts) is the same minus target columns, plus:

```
tweet_id, drafted_at, persona, topic, content_type, hook_type,
draft_text, final_text, user_edited, edit_summary,
status, sent_at, sent_day_of_week, sent_hour_local, review_due, reviewed_at
```

`content_type` (e.g. build-update, take, question, thread, quip) and `sent_hour_local` are the join keys for the timing playbook.

### 5.2 `metrics.csv` and the layered metrics model

Metric capture is **layered, not hard-coded to one source**. Two layers:

- **Layer 1 — public UI metrics.** Visible on the tweet detail page for *any* tweet, ours or anyone else's: views, likes, replies, reposts, quotes, bookmarks. Always captured for every reviewed item, and also usable when studying other people's tweets (e.g. calibrating `audience_activity` in the profile rubric).
- **Layer 2 — analytics panel metrics.** Available only for the persona's own posts when X exposes the analytics view: precise impressions, detail expands, profile visits, link clicks, new follows. Captured *on top of* Layer 1 whenever available.

Capture rule: take everything each layer offers; record which layer each value came from; absent values are written `n/a:<reason>` (e.g. `n/a:panel-unavailable`), never guessed. Analyses must never compare a Layer-2 metric on one item against a Layer-1 proxy on another as if equivalent.

`data/config/metrics.yaml` makes the whole thing configurable — which metrics to capture per format, and which to *optimize* for (the review loop's objective), so targets can be narrowed once real data shows what matters:

```yaml
capture:
  layer1: [views, likes, replies, reposts, quotes, bookmarks]
  layer2: [impressions, detail_expands, profile_visits, link_clicks, new_follows]
optimize:                      # per format; tune as understanding sharpens
  reply:    [profile_visits, new_follows, likes]
  quote:    [impressions, new_follows]
  tweet:    [impressions, engagement_rate, new_follows]
```

One row per capture (re-captures allowed; latest wins for analysis):

```
item_id, item_type(tweet|reply|thread_reply|quote), captured_at, days_since_sent,
views_l1, likes_l1, replies_l1, reposts_l1, quotes_l1, bookmarks_l1,
panel_available, impressions_l2, detail_expands_l2, profile_visits_l2,
link_clicks_l2, new_follows_l2, engagement_rate,
author_liked, author_replied, author_reposted,
follower_count_at_capture, notable_engagers, target_tweet_views_at_capture, notes
```

**Confound columns** (the last group) exist so the learning loop separates signal from luck:

- `author_liked` / `author_replied` / `author_reposted`: an author repost can 50x a reply's impressions — without this flag, the loop would credit the archetype for what was really the author's reach. Outliers with `author_reposted=true` are excluded from playbook math (the *fact that the author engaged* is itself the success signal there).
- `follower_count_at_capture` (+ `persona_follower_count_at_send` in the draft CSVs): normalize across account growth.
- `notable_engagers`: handles of any high-clout accounts that engaged — a reply that earned one VC follow can matter more than one that earned 50 anonymous likes, and the optimization config (§ metrics.yaml) should be able to weight that.
- `target_tweet_views_at_capture` vs. `_at_draft`: did the conversation grow after we joined, and what share of its audience did we capture?

`item_id` joins back to `reply_id`/`tweet_id` in the draft CSVs. `engagement_rate` = (likes+replies+reposts+bookmarks)/views (Layer 1, so it's computable for every item), computed, not scraped.

### 5.3 `profiles.csv`

```
handle, display_name, first_seen, last_updated, category, follower_count,
follower_tier, role_clout, audience_activity, geography, relevance,
credibility, relationship, bio_summary, notes,
times_engaged, engagement_outcomes
```

`engagement_outcomes` is a short free-text ledger ("2 replies, 1 got author-like, 1 follow-back") — the raw material for `engagement-targets.md`.

---

## 6. Draft Queue & Send Mode

### 6.1 Drafting (inside `scroll` / `compose`)

For each selected tweet:

1. **Duplicate check**: look up the target tweet URL and author in `replies.csv`. Skip if any non-discarded row exists for this tweet, or if the persona already replied to this author in the same thread. Also skip if the author was engaged in the last `min_hours_between_same_author` (limits.yaml) — repeated replies to the same account in quick succession read as stalking, not engagement.
2. Load persona + voice guide + style doc + relevant learnings files. **Cold-start guard**: if the persona's style doc is missing or too thin to be meaningful (no `## Confirmed` rules), abort the session with "run `learn` first" — never draft from the generic voice guide alone.
3. Determine the format (§4.5) — reply, thread reply (read the full thread first), or quote — and pick the reply archetype (§4.2), considering tagging if toggled.
4. Write the reply applying, in order: persona voice guide → personal style doc → Anti-AI Bible final pass. The Bible pass is a hard gate: any tell found means rewrite, not patch.
5. Append the row to the CSV (`status=drafted`) and write the draft file:

```markdown
# Draft <reply_id>
**Target**: <url>
**Author**: @handle — founder, mid-tier, relevance 4, credibility 4
**Tweet**: <quoted text of the target tweet>
**Archetype**: value-add        **Tagging**: none

---
<draft text — exactly what would be typed into the reply box>
---

Alt (different angle, optional):
<one alternate>
```

Session stops when `max_drafts_per_session` or `session_time_limit` from `limits.yaml` is hit — whichever first.

### 6.2 `limits.yaml` (defaults — tune after week one)

```yaml
max_drafts_per_session: 10
session_time_limit_minutes: 45
max_sends_per_day: 8          # human-approved sends, enforced in send mode
min_seconds_between_actions: 2
max_seconds_between_actions: 8
min_minutes_between_sends: 10
min_hours_between_same_author: 24   # duplicate-engagement guard (§6.1 step 1)
draft_staleness_hours: 12           # stale-draft flag threshold (§6.3)
```

### 6.3 `send` mode

Walks `data/drafts/` one file at a time, oldest first. For each draft, **before** presenting it:

- **Existence check**: navigate to the target tweet. If it's deleted, the account is gone/protected, or the reply box is absent → auto-discard, stamp `status=discarded` with reason `target_gone`, move the file to `drafts/discarded/`, continue.
- **Staleness check**: if the draft is older than `draft_staleness_hours` (limits.yaml, default 12) or the conversation has visibly moved past the draft's point (e.g. the author already answered the question the draft asks), flag it as stale in the presentation — the user decides whether it's still worth sending, but the agent must say why it may not be.

Then shows the draft + target context; the user says **send**, **edit** (provides new text), or **discard**. On send, the agent navigates to the tweet in Chrome, types the final text **character by character** per the §1.1 mimicry rules (never pasted), posts, fills `sent_at`/`final_text`/`user_edited`/`edit_summary`/`review_due` in the CSV, and moves the file to `drafts/sent/`. Respects `max_sends_per_day` and `min_minutes_between_sends`.

User edits are diffed against the draft and the pattern is appended to the relevant learnings file immediately (don't wait 5 days for what the human already told you).

---

## 7. Learning Mode (cold start)

Run once before first use, re-runnable to refresh. First run is against **Shubham's account and history**. Browses, via the same Chrome session (mimicry rules apply here too — learning sessions look like Shubham re-reading his own profile):

1. **Own tweets + replies** (profile → Posts, Replies tabs; scroll through **all** current tweets and replies, as far back as X serves them — across multiple sessions if needed): extract voice — vocabulary, casing, punctuation habits, sentence length distribution, humor register, formatting (line breaks, lists, emoji policy), how openers/closers work, recurring opinions and worldview. Output → `data/style/<persona>-twitter-style.md`. This document plus the repo voice guide are the two cornerstones for all drafting.
2. **Engagement patterns**: for each historical reply, classify the target tweet type, the reply archetype used, the author type, and the inferred **incentive** (genuine connection / topical engagement / prominent-user engagement / overly-relevant thought / value-add / connection-building attempt / other). Output → seed entries in `guidelines/reply-playbook.md` (real examples per archetype) and `learnings/engagement-targets.md`.
3. **Interaction graph**: every account the persona has interacted with — replied to, quoted, tagged, liked, followed — gets visited and run through the full profile rubric (§4.3): category, follower tier, role/clout, audience activity, geography, relevance, credibility, relationship. Output → seed rows in `profiles.csv` and the taxonomy section of `guidelines/profile-rubric.md`. This is what gives the engage/skip gate a real-network baseline instead of cold thresholds.
4. **What performed**: where visible counts exist on own historical posts, note which replies performed well, were unique, added value, and fit the brand of content + knowledge + communication + worldview + humour and wit. Output → seed entries in `learnings/content-playbook.md`.
5. **Tagging history**: collect the user's tweets that tag other users and worked; distill into `guidelines/tagging-playbook.md`.

The style doc gets a `## Confirmed` section (patterns seen ≥3 times) and a `## Tentative` section (seen once or twice); drafting weights Confirmed rules hard and Tentative rules lightly.

---

## 8. Review Mode — the 5-Day Feedback Loop

Triggered manually or by a Windows Task Scheduler entry running the Codex CLI daily with the `review` prompt.

1. **Find due items**: CSV rows with `status=sent`, `review_due ≤ today`, `reviewed_at` empty.
2. **Capture (layered, per §5.2)**: for each item, open the tweet detail page and record all Layer-1 public metrics; then, if the analytics panel is available for it (own posts), open it and record Layer-2 on top. Respect `data/config/metrics.yaml` for what to capture. Stamp `reviewed_at`.
3. **Analyze** (only when ≥5 newly reviewed items, so learnings rest on batches, not single data points): join metrics to draft metadata and look for patterns across:
   - reply archetype × target tweet format → `engagement-targets.md` ("which posts to reply to")
   - content_type/topic × engagement_rate → `content-playbook.md` ("what works for this persona")
   - sent_day_of_week + sent_hour_local × impressions, per content_type → `timing-playbook.md` ("best time per tweet type")
   - target author rubric scores × outcomes → tune the engage-gate thresholds in `profile-rubric.md`
   - user_edited drafts × performance → did the human's edits outperform? fold the edit patterns into the style doc.
4. **Write learnings** with the entry format below.
5. **Promote to style guide**: rules about *voice/phrasing* (not targeting/timing) that reach high confidence get appended to `data/style/<persona>-twitter-style.md`, so all future content follows them — mirroring cru-write's promote-and-remove rule.

### 8.1 Learning entry format and the correction rule

Every learning entry:

```markdown
### L-2026-06-17-03 — quips on launch posts underperform
**Evidence**: replies r-0612-...-a1, r-0613-...-c4, r-0615-...-b2 (avg ER 0.4% vs 2.1% playbook baseline)
**Rule**: on launch posts, prefer value-add or sharp-question over quip.
**Confidence**: medium (n=3)
**Supersedes**: none
```

**Correction (the in-place update rule)**: when new evidence contradicts an existing entry or a stated fact in any guide, the old text is **rewritten in place** — the rule is replaced, the entry's Evidence/Confidence updated, and `Supersedes:` records the old rule ID with one line on why it died. Contradicted content is never left standing with a correction appended after it; the guides must always read true top to bottom with zero wasted context.

Confidence ladder: `tentative (n<3)` → `medium (3–6)` → `high (≥7 consistent)`. Only `high` rules get promoted into the style doc / used to tighten the engage gate.

---

## 9. Safety & Failure Handling

- **Human gate on every send** — the agent has no path to post without `send`-mode approval.
- **Stop-on-anomaly**: any captcha, suspicious-login warning, or logged-out state ends the session and logs to `incidents.csv`. Two incidents in 7 days → agent refuses to run until the user clears the lockout (via the dashboard, §10). Confirmed by operator 2026-06-12. UI breakage (an expected element not found, likely an X redesign) is logged with type `ui_breakage` and does **not** count toward the security-incident counter — it halts the current action and surfaces to the user instead.
- **Voice outranks metrics (anti-engagement-bait rule)**: the learning loop may never promote, and the agent may never draft, content that violates the persona's voice or red lines — no matter how well that pattern performs. The gate is voice-first, metrics second; a high-engagement off-voice outlier is logged as an observation, never as a rule.
- **Volume discipline**: all caps in `limits.yaml`; defaults are deliberately conservative.
- **No fact invention**: Cruitical claims must trace to this KB (`data/company-facts.md` etc.); unknowns are flagged in the draft file, never guessed — same rule as the rest of this repo.
- **ToS risk** is accepted explicitly by the operator (see requirements doc, Open Question 5) — the design minimizes footprint (real browser, human pacing, low volume, human sends) but cannot eliminate it.

---

## 10. Dashboard — the single user interface

A local web app (localhost only, no auth needed beyond the machine itself) that fronts the entire system. **Files stay the source of truth** — the dashboard reads and writes the same CSVs, YAML, and Markdown the agent uses; it is a view/edit layer, never a second database. Anything the dashboard can change, the agent picks up on its next session start.

### 10.1 Surfaces

**Insights** — visual layer over all collected data:
- performance over time, sliceable by format, archetype, topic, target author category, post day/hour
- the three playbooks rendered with their evidence links (click a learning entry → see the underlying drafts and metric rows)
- profile intelligence table (sortable/filterable on every rubric axis), incident history, draft-queue funnel (drafted → sent → reviewed) and edit-rate trends

**Drafts** — the review queue as cards: target tweet context, the draft, alternates, archetype/format chips, staleness flags, and — prominently, top of card — a **tagging callout** when the draft tags anyone: who, their category/follower tier, and the relationship ("never interacted"). Actions per card: **send**, **edit then send**, **discard**. Edits made here are the same edit-signal capture as §6.3.

**Config** — forms over every config surface, so raw files never need to be opened by hand:
- `limits.yaml` and `metrics.yaml` as typed form fields (capture and optimize lists as toggles/weights)
- persona files (territory, goals, red lines as editable lists)
- guideline playbooks and the style doc as rendered, editable Markdown
- lockout clearing and incident acknowledgment live here too

**Run** — agent control: pick mode (learn / scroll / compose / send / review), persona, and toggles (`--tagging`); launch; watch live status (current action, drafts produced, session limits remaining); stop button. A locked-out agent shows the lockout reason and the clear control.

### 10.2 How UI actions reach the agent

Two patterns, both file-based to keep the no-second-database principle:

- **Config and draft decisions** are direct file writes (update YAML/Markdown, set `status=approved/discarded` in the CSV + move draft files). The agent reads state at session start and during `send` mode.
- **Launching/stopping the agent** shells out to the Codex CLI with the mode prompt, streaming its output into the Run view. Approving a draft in the UI and clicking send triggers a `send` session scoped to that draft.

Implementation stack is deliberately not fixed here (plan-level decision); the constraints are: local-only, zero cloud dependencies, reads/writes the canonical files, no daemon required when idle.

## 11. Build Phases

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 1. Skeleton | Folder tree, AGENTS.md behavior contract, CSV headers, limits.yaml, Chrome-attach procedure documented and tested manually | Codex session can attach to real Chrome and read the X timeline |
| 2. Learning mode | `learn` end-to-end on @shubvastav → style doc + seeded playbooks + interaction graph in profiles.csv | Shubham reads the style doc and confirms "this is how I write" |
| 3. Scroll + drafts | `scroll` produces queue drafts within limits; Anti-AI gate working | 10-draft session where founder would send ≥5 drafts unedited |
| 4. Send mode | Review/edit/send flow, edit-delta capture | First real sends; edits logged |
| 5. Review loop | `review` captures analytics, writes learning entries, correction rule works | First batch of ≥5 reviews produces playbook updates founder agrees with |
| 6. Tagging + compose | `--tagging` toggle, original-tweet `compose` mode | Used in anger for a week without incident |
| 7. Dashboard | Local web UI per §10: insights, draft cards with tagging callouts, config forms, run control | Founders operate the system for a full week without opening a raw YAML/CSV/Markdown file |

Phase 3's exit criterion is the real quality bar: if fewer than half the drafts are send-ready, fix the style doc and playbooks before building anything further. Phases 4–6 use the CLI flows directly; the dashboard (phase 7) then becomes the only interface for daily use.




