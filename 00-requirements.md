# Twitter Agent — Consolidated Requirements

last_updated: 2026-06-12
status: reviewed by Yash 2026-06-12 — decisions folded in (see Resolved Decisions)
companion: [01-spec.md](01-spec.md)

This document takes the raw requirements brain-dump for the Twitter browsing/engagement agent and reorganizes it into a cohesive set of capabilities. Nothing here is invented; every item traces back to a stated requirement. Where the original ask was ambiguous, the ambiguity is flagged in the Open Questions section rather than silently resolved.

---

## What This Thing Is, In One Paragraph

A Codex-powered computer-use agent that drives the user's real, default Chrome browser (logged-in profile, normal fingerprint — explicitly not Playwright or a bundled automation browser) to scroll Twitter/X as a specific persona. It decides which tweets are worth engaging with, drafts replies (and original tweets) in the persona's authentic voice, queues them as drafts for human review and one-tap sending, then circles back 5 days after each send to scrape the tweet's analytics and convert performance into written learnings. Its database is local CSV files; its brain is Markdown guideline files that it continuously rewrites as it learns.

---

## The Ten Capability Pillars

The raw requirements decompose into ten pillars. Each pillar is independently specifiable and testable.

### 1. Persona & Identity Layer — "who is it scrolling for"

- The agent always operates as a configured persona (Yash or Shubham to start; modular so more can be added).
- A persona bundles: the X handle, the voice guide (from `data/writing/`), the learned personal-style document, topical territory (what this person credibly talks about), goals (what engagement is *for* — distribution, network, hiring, fundraising visibility), and red lines (topics/never-dos).
- Persona definitions are modular guideline files, swappable without touching the agent's core logic.

### 2. Browser Control Layer — how it touches Twitter

- Controls the **default Chrome browser with the user's real profile** — existing login, cookies, history, fingerprint. Not Playwright's Chromium, not a fresh profile, no headless mode.
- **Full human mimicry is a hard requirement**, not just randomized delays. The agent must follow exactly how a human views Twitter:
  - **Burst-pause scrolling**: scroll a little, stop and read, scroll again. Variable burst sizes, variable dwell times, occasional scroll-backs up the timeline.
  - **Character-by-character typing**: replies and tweets are typed into the compose box one keystroke at a time with human inter-key variance and occasional mid-sentence pauses. Never pasted, never injected in one go.
  - **Human navigation**: open tweets and profiles the way a person does (click through, read, go back), one focused tab, no parallel automation.
- Built for the **Codex CLI as the primary agent runtime** (chosen for its browser-use ecosystem), with the architecture kept runtime-agnostic so Claude Code can drive the same system interchangeably.

### 3. Target Intelligence — "what posts to look for" and "who is worth engaging"

Two sub-systems:

**Tweet selection.** Modular guidelines defining the kinds of posts to look for per persona: topics, formats, recency, conversation stage (early replies beat late ones), and signals that a reply there would earn engagement.

**Profile intelligence.** A studied, categorized model of users/accounts along these axes:
- category (founder, VC, engineer, researcher, anon shitposter, journalist, recruiter…)
- following strength / follower count tier
- role and "clout"
- how active their audience is (do their replies get seen?)
- geography
- relevance to us and to Cruitical
- credibility/reputation

This profile model drives the four engagement questions the requirements name explicitly: *do we engage with this tweet? would it be good for engagement? how is this user relevant to us? are they credible/reputed?*

### 4. Content Generation — replies and original tweets

- Two cornerstones, always combined: (a) the writing guides in this repo, reached via the **CRU Write** skill (`data/writing/` — Anti-AI Bible, voice guides, voice router, iteration learnings), and (b) the **learned personal-style document** built by Learning Mode from the user's own historical tweets and replies.
- Modular guidelines define the *kinds of replies* to drop per tweet type (value-add, question, contrarian take, humorous quip, supportive amplification, plug, etc.).
- **Each engagement format is a first-class concept with its own clear, specific instructions**: plain replies, replies into threads (full thread must be read before drafting), quote tweets (must stand alone for the persona's own followers), and original tweets. No format is treated as a variant of another.
- **Zero AI-tells is a hard requirement.** Drafts must read like tech Twitter actually reads — formatting, casing, length, rhythm. Every draft passes the Anti-AI Bible before it reaches the queue.
- **Tagging toggle**: an optional mode where the agent also considers composing replies/quotes that tag a relevant high-profile user, connection, or follower — as a pull-in to the discussion, a shoutout/plug, or a humorous quip. The user's own tweet history (via Learning Mode) is the reference for how tagging is done well.

### 5. Draft Queue & Human Review — nothing posts itself

- The agent **only drafts**. Every reply/tweet lands in a reviewable draft queue.
- Queue limits set by the user: max draft count per session and/or a session time limit.
- The user reviews each draft and can: send as-is, edit then send, or discard.
- Sending happens through the same browser-control layer on the user's explicit approval.
- Edits the user makes before sending are themselves a learning signal (what the agent got wrong).

### 6. Memory & Data Layer — CSVs as database, Markdown as brain

- **CSV files** are the database: every drafted tweet, every drafted reply, every profile studied, every metrics capture is a row. Local, inspectable, diffable in git.
- Single-session operation: exactly one agent session at a time (operator-enforced), so no locking machinery.
- The data layer must prevent **duplicate engagement** (never re-draft a tweet already engaged; never pile onto the same author in quick succession) and handle **draft staleness** (targets verified to still exist at send time; old drafts flagged).
- **Markdown files** are the learnings: content playbook, timing playbook, engagement-target playbook, profile taxonomy, and the personal style guide.
- One fact, one home: facts live in exactly one learning file; learnings reference data, never duplicate it.

### 7. Performance Feedback Loop — the 5-day review

- Every sent tweet/reply gets a review date 5 days after sending.
- **Metric capture is layered, never hard-coded to one source**:
  - Layer 1 — public UI metrics (views, likes, replies, reposts, quotes, bookmarks): visible on any tweet's detail page, ours or anyone else's. Always captured; also usable when studying other people's tweets.
  - Layer 2 — the analytics panel (precise impressions, detail expands, profile visits, link clicks, new follows): available for the persona's own posts; captured on top of Layer 1 whenever present.
- Which metrics are captured and, separately, which are **optimized for** is configurable per format, so once the objectives are well understood from real data, they can be narrowed without code changes.
- Metrics are appended to the metrics CSV and joined back to the draft's metadata (topic, reply type, target author category, post time, whether it was user-edited).
- From accumulated reviews, the agent self-improves on the three stated learning goals:
  1. what kinds of posts it should be replying to
  2. what kind of content works on Twitter given the persona
  3. the best time to post for each type of tweet

### 8. Learning Mode — cold start from the user's own history

A distinct mode that browses the user's own tweets, replies, and likes to learn. It scrolls through **all** of the persona's current replies and tweets, and additionally visits **the people the persona has interacted with**, applying the full profile-intelligence principles from pillar 3 to each of them — so the agent starts with both a voice model and a populated picture of the persona's actual network. It learns:
- voice and writing style (becomes the personal style document — the second cornerstone of pillar 4)
- types of tweets the user engages with, and reply styles used
- types of users engaged with, liked, followed — each interacted-with account gets categorized through the pillar-3 profile rubric (category, follower tier, clout, audience activity, geography, relevance, credibility) and stored, so the engage/skip intelligence is seeded from real history
- the inferred *incentive* behind each interaction: genuine connection, topical engagement, prominent-user engagement, relevant thought to surface, value-add, connection-building attempt, etc.
- which past replies performed well, were unique, added value, and fit the brand of content + knowledge + communication + worldview + humour and wit
- how the user has historically used tagging to compose value-adding, engagement-driving tweets (feeds the tagging toggle)

### 9. Self-Improving Style Guide Maintenance — append vs. correct

- All learnings from the feedback cycle are **appended** to the style/learning guides so future drafts follow them.
- **Correction rule**: if a previously written "fact" or rule is later contradicted by evidence, it is **rewritten in place** — replaced, not appended-around — so the guides never carry stale context. (Same philosophy already used by `cru-write` Step 8c and the iteration-learnings promotion rule.)

### 10. Dashboard — the only interface the user should need

A local web UI that sits on top of the file system (files remain the source of truth; the dashboard is a view/edit layer, not a second database):

- **Data insight**: visualizes everything collected — performance by format/archetype/topic/time, profile intelligence, learning entries, incident history.
- **Configuration**: every config surface (limits, metrics/optimization targets, personas, guideline playbooks) is editable through UI forms. The user should never have to touch raw YAML, Markdown, or CSV files directly.
- **Agent control**: launching any agent mode (with persona and toggles like `--tagging`) and monitoring its live status happens from the UI.
- **Action confirmation**: the draft queue is reviewed in the UI — send / edit / discard per draft. Drafts that tag someone carry a prominent callout naming exactly who would be tagged (this is the chosen guardrail for tagging prominent accounts — clear surfacing, not an allowlist). Lockout clearing and incident acknowledgment also happen here.

---

## Operating Modes (derived from the pillars)

| Mode | What it does | Pillars exercised |
|---|---|---|
| `learn` | Cold-start study of the user's own tweets/replies/likes → style doc + engagement-pattern docs | 2, 8 |
| `scroll` | Browse timeline/targets, select tweets, draft replies into the queue. `--tagging` flag enables tagging exploration | 1–6 |
| `compose` | Draft original tweets (not replies) into the queue | 1, 4, 5, 6 |
| `send` | Walk the user through the draft queue; send/edit/discard | 2, 5 |
| `review` | Visit analytics for items ≥5 days old, capture metrics, extract learnings, update guides | 2, 6, 7, 9 |
| `dashboard` | Local web UI: data visualization, all configuration, agent launching, draft approval | 10 (fronts all others) |

---

## Explicit Non-Goals

- No autonomous posting. Human approval gates every send.
- No Playwright/automation-browser fingerprint. Real Chrome, real profile only.
- No external database, no API keys, no Twitter API. Local CSVs + Markdown + the browser.
- No engagement-bait that violates the persona's voice or red lines, even if metrics say it would work.

---

## Resolved Decisions (Yash, 2026-06-12)

1. **First persona: Shubham (@shubvastav).** Persona switching must stay easy (it is — one config line), but everything launches on Shubham's account, and Learning Mode runs against Shubham's history and network first.
2. **Location: sibling working folder** under `` in this repo. Confirmed.
3. **Runtime: Codex CLI primary**, chosen for its browser-use ecosystem. The architecture stays runtime-agnostic so Claude Code can drive the same system when capable; Codex is the primary LM agent.
4. **ToS posture: maximal human mimicry.** Burst-pause scrolling (scroll a bit, stop, scroll again), character-by-character typing (never paste), and navigation that follows exactly how a human views Twitter. Codified as hard behavioral requirements in pillar 2 and spec §1.1.
5. **Dashboard as the sole user interface** (pillar 10): data insight, all configuration, agent launching, and action confirmation through a local web UI; no raw file interaction required.
6. **Tagging guardrail: surfacing, not an allowlist.** Drafts that tag someone are clearly called out in the UI with exactly who is being tagged; the human decides per draft.
7. **Anti-engagement-bait rule confirmed**: voice and red lines always outrank metrics; the learning loop may never promote a pattern that violates them, however well it performs.
8. **Cold-start guard confirmed**: `scroll`/`compose` refuse to run without a usable persona style doc from `learn`.
9. **Confound metrics confirmed and extended**: the metrics named in the original requirements are not exhaustive — the system should track whatever context helps separate what's working from what isn't (author engagement with our reply, follower count snapshots, reply position, stage size, notable engagers, etc.).
10. **Auto-lockout confirmed**: two account-security incidents within 7 days suspends the agent until manually cleared (via the dashboard).

## Remaining Open Questions

1. **Daily volume.** No numbers were given for reply caps. Conservative defaults in spec `limits.yaml` — tune after week one.
2. **Residual account risk.** Mimicry plus low volume plus human-gated sends minimizes the footprint, but automation on X remains against its ToS; operating on @shubvastav assumes acceptance of that residual risk.


