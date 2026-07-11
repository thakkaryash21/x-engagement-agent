# Mode: `learn` — cold-start procedure

last_updated: 2026-07-10
status: hand-authored procedure for AGENTS.md §4.1
entry point: AGENTS.md §4.1 links here for the full procedure

`learn` is a read-only mode: it never drafts and never sends. It browses the active persona's own profile and network — Posts, Replies, and Likes tabs, plus interactions (mimicry rules, AGENTS.md §3, apply — a learn session looks like the persona re-reading their own profile) — and writes/extends:

- `data/style/<persona>-twitter-style.md` (the primary output — cornerstone #2 for drafting; includes voice patterns from Posts/Replies and framing/engagement patterns from Likes, §1.5)
- `guidelines/reply-playbook.md` (real examples per archetype)
- `guidelines/profile-rubric.md` (seeded taxonomy)
- `guidelines/tagging-playbook.md` (seeded tagging examples)
- `data/learnings/content-playbook.md` (what performed, seed entries)
- `data/learnings/engagement-targets.md` (historical patterns + incentive classification)
- `data/csv/profiles.csv` (interaction-graph rows)
- `data/csv/incidents.csv` (if an anomaly halts the session, AGENTS.md §6)

`learn` is re-runnable to refresh any of the above. Re-running extends and corrects per the correction rule — it never duplicates.

`learn` does **not** write historical observations into `data/csv/replies.csv`, `data/csv/tweets.csv`, or `data/csv/metrics.csv`. Those files belong to draft/send/review workflows unless a documented schema migration explicitly adds a raw learning-evidence table. In this procedure, historical evidence is distilled into the files listed above, with profile rows in `profiles.csv` and progress rows in `learn-progress.csv`.

---

## 0. Resume check

`data/csv/learn-progress.csv` tracks progress per persona and section, because a full pass over all current tweets and replies, as far back as X serves them, can exceed one `session_time_limit_minutes` window.

Use these section names:

- `posts`
- `replies`
- `likes`
- `interaction_graph`
- `tagging_history`
- `synthesis`

Use these statuses:

- `in_progress`: actively being browsed or intentionally resumable.
- `seeded`: enough evidence exists for the agent to operate, but the section was sampled or bounded rather than exhaustive.
- `complete`: X stopped serving more items, or every required account/item in that section was visited under the selected scope.

Do not mark a sampled interaction graph as `complete`. If the pass prioritized high-signal accounts rather than every surfaced account, mark it `seeded` and record the priority rule in `notes`.

At the start of `learn`, read this CSV for the active persona:

- No row, or all sections `complete` and the user asked for a refresh → start (or restart) at section 1, new `session_count`.
- Any section `in_progress` → resume there, from `last_processed_item_url` / `last_processed_at`, continuing in the same `direction`.

Update the row after every scroll burst (not just at session end) — if the session is interrupted by an incident (AGENTS.md §6) or hits `session_time_limit_minutes`, progress is not lost.

### 0.1 Scope level

Before browsing, choose and record the scope in the relevant progress-row `notes`:

- `full_archive`: browse Posts/Replies until X stops serving older items.
- `year_bound:<YYYY>`: browse until the start of that year or another explicit date boundary requested by the user.
- `sampled_seed`: collect enough recent and representative evidence to seed style, targeting, profiles, and tagging. Use this only when the user explicitly accepts a non-exhaustive pass.

If the user says there is enough content, stop browsing and mark the relevant in-progress sections as `seeded` unless their exhaustive completion criteria were actually met.

### 0.2 Category-focused passes

When the user asks to focus category-by-category, finish the current section before jumping to the next. A typical order is:

1. `posts`
2. `replies`
3. `likes`
4. `interaction_graph`
5. `tagging_history`
6. `synthesis`

This avoids mixing voice, target-selection, profile-scoring, and tagging evidence before each category has enough signal.

---

## 1. Own timeline — Posts and Replies tabs

Navigate to the persona's own profile (`handle` from `data/personas/<active>.md`). For both the Posts tab and the Replies tab:

1. Pick a direction on first run (newest-to-oldest is the default — it surfaces recent voice first) and record it in `learn-progress.csv`. Keep the same direction on resume.
2. Burst-pause scroll (AGENTS.md §3.2) through tweets/replies. For each item read:
   - **Voice signal** (feeds `data/style/<persona>-twitter-style.md`): vocabulary, casing, punctuation habits, sentence length distribution, humor register, formatting (line breaks, lists, emoji policy), how openers/closers work, recurring opinions and worldview.
   - **If it's a reply**: classify the target tweet's type, the `reply_archetype` used (`guidelines/reply-playbook.md` categories), the target author's type, and the inferred **incentive** — genuine connection / topical engagement / prominent-user engagement / overly-relevant thought / value-add / connection-building attempt / other (feeds `data/learnings/engagement-targets.md`).
   - **If it tags someone**: note the tweet, who was tagged, and why it reads as working (feeds `guidelines/tagging-playbook.md`).
   - **If visible counts exist** (likes/views/replies on the persona's own post): note whether this item was unique, added value, and fit the brand of content + knowledge + communication + worldview + humor (feeds `data/learnings/content-playbook.md`).
3. Stop the section when X stops serving more items (mark `complete`), the selected scope boundary is reached (mark `seeded` unless it was `full_archive`), or `session_time_limit_minutes` is hit (mark `in_progress`, record resume point).

### 1.1 Gap checks

X can crash, jump date ranges, stop rendering a range, or resume from an unexpected point. When the visible timeline appears to skip a meaningful range:

1. Stay in the same focused tab.
2. Run one focused X search using the persona handle and date bounds, for example `from:<handle> filter:replies since:YYYY-MM-DD until:YYYY-MM-DD`.
3. If the search returns no results, record that exact date range and query in `learn-progress.csv` notes and, if it affects targeting conclusions, in `data/learnings/engagement-targets.md`.
4. If the search returns results, treat the range as not covered and continue the relevant category pass from those results or the nearest useful timeline point.

Do not infer that a date range is empty just because infinite scroll skipped over it.

## 1.5 Own Likes — framing & engagement patterns

Navigate to the persona's Likes tab. This pass is about **genre, not facts**: it answers "what does an engaging tech-Twitter tweet look like, filtered through this persona's actual taste?" — not "what topics does the persona care about" (that's already covered by Posts/Replies/reposts in step 1).

1. Use `sampled_seed` scope (§0.1 above) — a representative sample of recent Likes is enough. This section is rarely worth a `full_archive` pass.
2. Burst-pause scroll (AGENTS.md §3.2) through the Likes tab. For each liked tweet, ignore the topic and **name the framing technique that makes it land** — for example: leads with a concrete/specific detail before any abstract point, sets up a contrast or tension and resolves it in one beat, ends on a dry understatement instead of a conclusion, uses a short punchy fragment as a second sentence, states an unexpected number or fact as the hook, or undercuts its own premise.
3. Do not record the liked tweet's topic, wording, or subject matter — only the structural technique. The same technique observed across unrelated topics (a product launch, a personal anecdote, an industry jab) is the signal that it's a genre pattern worth recording, not a one-off.
4. A technique observed 3+ times across Likes goes in `data/style/<persona>-twitter-style.md` under `## Framing patterns (from Likes)` → `### Confirmed`; 1-2 times goes under `### Tentative`, same promotion/correction rules as the main `## Confirmed`/`## Tentative` sections (step 4 below). These stay weighted *below* the main `## Confirmed` — they shape how a point lands, never what the persona would say or whether it fits their voice/red lines.
5. Stop the section when X stops serving more Likes, the sample feels representative (recurring techniques start repeating rather than introducing new ones), or `session_time_limit_minutes` is hit — mark `seeded` in either of the first two cases, `in_progress` in the last.

## 2. Interaction graph

From everything read in step 1 (replies, likes, follows visible on the profile), build the set of unique accounts the persona has interacted with.

The interaction graph can become much larger than one session can handle. Prioritize accounts in this order:

1. Direct reply authors and quote-post authors where the persona added text.
2. Accounts the persona tagged directly.
3. Repeatedly surfaced repost authors or accounts that shaped multiple learning rules.
4. Accounts that have an obvious real-life or relationship signal (`Follows you`, `we-follow`, `mutual`, `real-life connection`).
5. Incidental handles mentioned inside quoted tweets, link previews, or other people's text.

Visit every account in tiers 1-2 for a `complete` interaction graph. If time or user scope limits prevent this, visit the highest-signal accounts from tiers 1-4 and mark the section `seeded`, not `complete`.

For each account not already in `data/csv/profiles.csv`:

1. Visit the profile (mimicry rules apply — reading dwell, no parallel tabs).
2. Score it against every axis in `guidelines/profile-rubric.md` (Rubric axes).
3. Write the row to `data/csv/profiles.csv`, with `engagement_outcomes` as a short free-text ledger built from step 1's classification of interactions with this account (e.g. "2 replies: 1 value-add got author-like, 1 quip no response").

This is the network baseline that lets the engage/skip gate in `guidelines/profile-rubric.md` use real relationships instead of cold thresholds.

Direct navigation to an exact profile URL is allowed for this step when it avoids excessive duplicate scrolling, but keep one focused tab, use reading dwell, and do not open parallel/background tabs.

## 3. Tagging history

From step 1's tagged tweets, distill the pattern — what made each tag read as a genuine value-add, shoutout, or quip rather than reach-grabbing — into `guidelines/tagging-playbook.md`'s "Seeded examples" section.

If tagging evidence was collected during Posts/Replies rather than a separate pass, it may be synthesized directly. If tagging is sparse or unclear, add `tagging_history,seeded` rather than `complete` to `learn-progress.csv` and state what was actually observed.

## 4. Synthesize style doc

Write `data/style/<persona>-twitter-style.md`:

- **`## Confirmed`**: any voice pattern from step 1 observed **3 or more times**. Be specific — "uses lowercase for short observational tweets" not "casual tone."
- **`## Tentative`**: patterns observed 1-2 times.
- On re-run: a Tentative pattern that reaches 3 occurrences is promoted to Confirmed. A pattern contradicted by new evidence is rewritten in place per the correction rule, with a line in `## Correction log`.

This is the file the cold-start guard (AGENTS.md §5.1) checks — `scroll`/`compose`/`send` cannot run until `## Confirmed` has at least one entry.

For each Confirmed rule, include enough evidence wording to justify the threshold. This can be examples inline or a short count phrase such as "observed across Posts, Replies, and quote posts." Do not promote a rule to Confirmed only because it feels plausible.

Also write `## Framing patterns (from Likes)` from step 1.5: name each technique, with its own `### Confirmed` (3+ occurrences) / `### Tentative` (1-2) split and the same promotion/correction rules. Keep these as technique descriptions only — never the liked tweet's topic, wording, or subject matter (a technique description that names a specific person, product, or claim from a liked tweet has drifted into content, not framing — rewrite it as the abstract technique).

## 5. Synthesize remaining seed files

- `guidelines/reply-playbook.md`: under each archetype's `**Examples**`, add 2-3 real examples found in step 1, replacing the `<!-- learn mode -->` placeholder.
- `guidelines/profile-rubric.md`: under `## Seeded profile taxonomy`, note any recurring patterns across the interaction graph (e.g. relevance/credibility tendencies by category).
- `data/learnings/content-playbook.md`: under `## Entries`, add seed entries for what performed, using `Confidence: tentative` until `review` mode accumulates more evidence.
- `data/learnings/engagement-targets.md`: under `## Historical patterns (from learn mode)`, summarize the archetype/target-type/incentive classifications from step 1.

Manual human audits of drafts before sending are also learning evidence. Fold them into the same homes immediately:

- Voice and phrasing corrections go to `data/style/<persona>-twitter-style.md` under `## Tentative` or `## Confirmed`, using the same promotion/correction rules as observed history.
- Target-selection corrections go to `data/learnings/engagement-targets.md`, `guidelines/target-posts.md`, or `guidelines/profile-rubric.md`, depending on whether the failure was the tweet, the author, or the engage gate.
- Archetype and draft-shape corrections go to `guidelines/reply-playbook.md`.
- If the audit rejects drafts as off-voice, record the pattern under `data/learnings/content-playbook.md`'s off-voice observations so future agents can see what not to promote.

Do not leave high-signal human audit feedback only in chat. If the user explains why a draft is wrong, preserve the reusable rule before the next scroll session.

Metric handling in `learn`:

- Visible counts on the persona's own historical posts feed `data/learnings/content-playbook.md`.
- Visible audience activity on other accounts feeds `profiles.csv` (`audience_activity`) and `guidelines/profile-rubric.md`.
- Do not append learn-mode captures to `metrics.csv`; that file remains for review-mode captures unless a documented schema migration changes that ownership.

Evidence handling:

- Markdown learning files should contain synthesized rules and representative examples, not raw dumps.
- `profiles.csv` is the structured home for author/profile scoring.
- `learn-progress.csv` is the structured home for scope, coverage, date gaps, and resume points.
- If future learning needs per-item auditability beyond these homes, add it as an explicit schema/template migration rather than overloading draft/review CSVs.

---

## Exit criteria

The mode is successful when the founder/operator reads `data/style/<persona>-twitter-style.md` and confirms "this is how I write." If not, this is a signal to re-run `learn` (it will extend/correct) or to hand-edit the style doc directly — both are valid, and the dashboard Knowledge surface supports direct Markdown edits.


