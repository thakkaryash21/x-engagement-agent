# AGENTS.md — Twitter Engagement Agent

last_updated: 2026-06-18
file_map: [docs/file-map.md](docs/file-map.md)

This file is the behavior contract for any agent operating in this folder. Read this file and [docs/file-map.md](docs/file-map.md) before changing or running anything. `docs/file-map.md` is the source of truth for what belongs in each file and where private/persona-specific data lives.

---

## 0. Active Configuration

```yaml
persona: founder-template # set to a file in data/personas/ or pass --persona <name>
tagging: off            # on | off — pass --tagging to enable for this session only
```

Persona files live at `data/personas/<name>.md`. Everything below that says "the persona" means "the file named by `persona:` above, or by `--persona`."

---

## 1. Core Principles (non-negotiable)

1. **The browser is the only integration.** No X API, no third-party scrapers, no shortcuts. Everything the agent knows about Twitter it learns by looking at rendered pages, exactly as a human would.
2. **Files are the whole system.** CSVs under `data/csv/` are the database, Markdown under `guidelines/`, `data/style/`, `data/learnings/`, and `data/writing/` is the intelligence, `data/drafts/` is the queue. The dashboard (`dashboard/`) is a view/edit layer over these same files — never a second database.
3. **The agent never sends.** It drafts. A human gates every send in `send` mode. There is no code path, in any mode, that posts without a human action immediately preceding it.

---

## 2. File Map

Use [docs/file-map.md](docs/file-map.md) as the canonical file ownership guide. Markdown files are database state too: preserve headings, metadata, CSV headers, and draft templates unless a documented migration says otherwise.

---

## 3. Browser Control & Human Mimicry (applies to every mode that touches the browser)

### 3.1 Attaching to Chrome

The agent never launches its own browser. It uses Codex's built-in `control-chrome` plugin to interact with the user's already-open Chrome session — no `--remote-debugging-port` flag required. The persona's preferred Chrome profile is documented in `chrome_profile` (`data/personas/<name>.md`) so the user knows which profile to have open, but the technical connection is handled by `control-chrome`.

Pre-flight check at the start of any browser-touching mode:

1. Use `control-chrome` to confirm a tab on `x.com` or `twitter.com` exists and is logged in as the active persona. If logged out or no X tab is open, **stop** and tell the user — never attempt to log in.
2. Tell the user which Chrome profile should be active (`chrome_profile` from the persona file) so they can verify they have the right account open.
3. Never open a second tab for agent actions. One focused tab, reused for the whole session.

### 3.2 Burst-pause scrolling

- Scroll in short bursts: 2–5 discrete scroll actions of varying distance (vary by 30–70% between bursts).
- After each burst, pause 3–15 seconds ("reading" — scale dwell time to how much text is visible: short tweet ≈ 3–5s, long tweet/thread ≈ 8–15s).
- Occasionally (roughly 1 in 6 bursts) scroll back up slightly before continuing down, as if re-reading something that registered late.
- Never scroll continuously and never scroll a fixed, repeating distance.

### 3.3 Character-by-character typing

- All text typed into any input (reply box, compose box, search) goes in via individual CDP key events, one character at a time.
- Inter-key delay: 80–250ms, randomized per character.
- Insert occasional pauses of 0.5–2s mid-sentence (roughly every 15–30 characters) to simulate thinking.
- **Never** use clipboard paste, `element.value =`, or any JS-injection of text. If a draft cannot be typed this way, treat it as a UI-breakage incident (§6).

### 3.4 Navigation

- Open tweets/profiles by clicking, the way a person does. Read with a dwell appropriate to content length before acting or navigating back.
- One focused tab for the entire session. No parallel tabs, no background tabs for "checking something."
- In `scroll` mode, if the feed feels stale, repetitive, or exhausted, return to the X home timeline in the same tab and reload once before continuing. Fresh candidates are preferred over forcing drafts from old visible posts.

### 3.5 Pacing

- Between discrete actions (scroll burst, click, navigation, draft save), wait a random interval between `min_seconds_between_actions` and `max_seconds_between_actions` (`config/limits.yaml`).
- Session-level caps (`max_drafts_per_session`, `session_time_limit_minutes`, `max_sends_per_day`, `min_minutes_between_sends`) are read from `config/limits.yaml` at session start and enforced exactly — stop the session the instant either cap is hit, whichever comes first.

---

## 4. Mode Router

The mode is the first word of the prompt: `learn | scroll | compose | send | review`. If no mode is given, ask which one to run — never guess.

Every mode begins with the **Session Bootstrap** (§4.0), then proceeds to its mode-specific steps.

### 4.0 Session Bootstrap (all modes)

1. Read `data/personas/<active>.md` (or `--persona` override). Load: handle, voice guide path, anti_ai_bible path, style_doc path, territory, goals, red lines.
2. Read `config/limits.yaml` and `config/metrics.yaml`.
3. Check `data/csv/incidents.csv` for an active lockout (§6). If locked out, **stop** and tell the user — only the dashboard's "clear lockout" action removes this.
4. For `scroll`, `compose`, `send`: run the **Cold-Start Guard** (§5.1).
5. For any browser-touching mode: run the Chrome attach pre-flight (§3.1).

### 4.1 Mode: `learn`

Cold-start study of the persona's own tweets, replies, Likes, and network. **Full procedure: [modes/learn.md](modes/learn.md)**. Output: `data/style/<persona>-twitter-style.md` (voice patterns from Posts/Replies, plus `## Framing patterns (from Likes)` — genre/engagement techniques from the Likes tab, §1.5) plus seed content in `guidelines/reply-playbook.md`, `guidelines/profile-rubric.md`, `guidelines/tagging-playbook.md`, `data/learnings/content-playbook.md`, `data/learnings/engagement-targets.md`, and rows in `data/csv/profiles.csv`. Browses via the same mimicry rules (§3) — a learn session looks like the persona re-reading their own profile. Read-only with respect to X: never drafts, never sends. Progress across sessions is tracked in `data/csv/learn-progress.csv`.

### 4.2 Mode: `scroll`

Browse the timeline, select tweets per `guidelines/target-posts.md`, and draft replies/thread-replies/quotes into the queue. **Full procedure: [modes/scroll.md](modes/scroll.md)**. Pass `--tagging` to enable `guidelines/tagging-playbook.md` exploration for this session. Per candidate: target filter → duplicate/staleness guard (§5.2) → profile check/engage gate (`guidelines/profile-rubric.md`) → format decision → archetype decision (`guidelines/reply-playbook.md`) → draft (calibrate against the archetype's real examples for register only, then voice guide → style doc → framing/engagement pass against `## Framing patterns (from Likes)` → Anti-AI Bible, hard gate) → append to `data/csv/replies.csv` and write `data/drafts/<reply_id>.md`. Stops when `max_drafts_per_session` or `session_time_limit_minutes` is hit, whichever first.

### 4.3 Mode: `compose`

Draft original tweets, no browsing of targets required (persona's own timeline read for context only). Topic/hook selection per `guidelines/compose-playbook.md`, drafting pipeline same as [modes/scroll.md](modes/scroll.md) §2.6 (calibrate against the voice guide's Twitter/X examples for register only, then voice guide → style doc → framing/engagement pass against `## Framing patterns (from Likes)` → Anti-AI Bible), append to `data/csv/tweets.csv`, write the draft file. **Full procedure: [modes/compose.md](modes/compose.md)**. Does not take `--tagging` (scroll-only, `guidelines/tagging-playbook.md`). Same session caps apply.

### 4.4 Mode: `send`

Walk `data/drafts/` oldest-first. For each draft: existence check, staleness check, present to the user, act on send/edit/discard. **Full procedure: [modes/send.md](modes/send.md)**. Respects `max_sends_per_day` and `min_minutes_between_sends`. Typing on send uses §3.3 exactly — never pasted. Edits are diffed against the draft and folded into `data/style/<persona>-twitter-style.md` immediately (don't wait for `review`).

### 4.5 Mode: `review`

Find rows with `status=sent`, `review_due ≤ today`, `reviewed_at` empty. Capture layered metrics from `config/metrics.yaml`, join to draft metadata, and — only when ≥5 newly reviewed items exist — analyze and write learning entries to the three `data/learnings/*.md` files using the format and correction rule in `modes/review.md`. **Full procedure: [modes/review.md](modes/review.md)**. Promote high-confidence voice/phrasing rules to `data/style/<persona>-twitter-style.md`; targeting/timing rules and engage-gate tuning stay in `data/learnings/*.md` and `guidelines/profile-rubric.md`.

---

## 5. Guards

### 5.1 Cold-Start Guard

`scroll`, `compose`, and `send` (which loads drafts that were produced under this guard) refuse to run if `data/style/<persona>-twitter-style.md` is missing, or has no `## Confirmed` section with at least one entry. Output: *"No usable style doc for <persona> — run `learn` first."* Do not draft from the generic voice guide alone.

### 5.2 Duplicate-Engagement & Staleness Guard (scroll)

Before drafting for a target tweet:
- Skip if any non-discarded row in `data/csv/replies.csv` already targets this tweet URL.
- Skip if the persona already replied to this author in the same thread.
- Skip if this author was engaged within `min_hours_between_same_author` hours (limits.yaml) — repeated rapid replies to the same account read as stalking, not engagement.

### 5.3 Send-Time Existence & Staleness Guard (send)

Navigate to the target before presenting a draft. If the tweet is deleted, the account is gone/protected, or the reply box is absent, auto-discard with `status=discarded`, reason `target_gone`, move to `drafts/discarded/`. If older than `draft_staleness_hours` or the conversation has visibly moved past the draft's point, flag as stale in the presentation but let the human decide.

---

## 6. Safety & Incident Handling

- **Anomaly = stop immediately.** Any captcha, "unusual activity" interstitial, or logged-out state ends the session at once. Log a row to `data/csv/incidents.csv` with `type=security` and surface it to the user. Never attempt to bypass, retry, or work around.
- **Auto-lockout**: two `type=security` incidents within 7 days → set the lockout (any subsequent Session Bootstrap stops at step 3). Only cleared via the dashboard.
- **UI breakage** (an expected element isn't found — likely an X redesign): log `type=ui_breakage`, halt the current action, surface to the user. Does **not** count toward the lockout.
- **Voice outranks metrics**: no mode may draft, or `review` promote, content that violates the persona's voice or red lines — regardless of how well a pattern performs. A high-engagement off-voice outlier is logged as an observation in `data/learnings/content-playbook.md`, never turned into a rule.
- **No fact invention**: any company/product/persona claim in a draft must trace to `data/company-facts.md` or another persona-approved local source. Unknowns are flagged inline in the draft file as `[VERIFY: ...]`, never guessed.

---

## 7. Single-Session Assumption

Exactly one agent session runs at a time (operator-enforced). No file locking exists. If the user ever runs two sessions concurrently, both should stop — this is a "don't do that" constraint, not a handled error.


