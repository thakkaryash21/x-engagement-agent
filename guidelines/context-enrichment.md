# Context Enrichment — acquisition intelligence

last_updated: 2026-07-11
status: public generic playbook; persona-specific context lives under `data/`

This is the single home for the **context-acquisition intelligence** the `scroll` mode runs in its Context Brief step (`modes/scroll.md` §2.4b). It defines *what kind of context a good reply needs, where each kind lives, and how to ask for it well*. `modes/scroll.md` references this file rather than restating it — keep the taxonomy, matrix, and playbook here only.

The Context Brief exists to stop drafts from collapsing into a generic, subject-agnostic caveat. A human never replies to a tweet about a thing they don't understand by writing a hedge that fits any tweet — they glance at the thread, maybe search the thing for ten seconds, *then* reply with something specific. This playbook is that ten-second glance.

Keep this file persona-neutral: it describes *the mechanism only*. A persona's own facts, subjects, and slugs live in ignored `data/` (subject dossiers, the Self store, `data/company-facts.md`), never here.

---

## 1. The governing constraint (read before using any adapter)

AGENTS.md §1 non-negotiable #1 — *"the browser is the only integration"* — governs how the agent touches **X**: rendered pages, no X API, no scrapers. It does **not** forbid reading OFF-X background about a subject, which is exactly what a human does before replying. The hard line:

- **On X**: browser-only, always. Never an X API or scraper.
- **Off X**: web search / fetch of *background* is allowed and encouraged, but only for **off-X** sources.
- **Never** use a web-search backend to reach into x.com / twitter.com for tweets, timelines, or profile data. That path stays browser-only.

This single guardrail governs every adapter and every query below.

A reply is **voice × content**, and content draws on two wells: **World** (what's going on with the tweet's *subject* — the launch, event, discourse, jargon, person) and **Self** (the persona's own documented lived experience — projects, shipped work, opinions, prior interactions). Enrichment gathers World live and retrieves Self from memory; both flow through the same subsystem, distinguished only by a `scope` (`world` | `self`) tag. Self is **never** gathered from the open web — it is seeded from the persona's own history (`learn`) and user input, so the no-invention red line stays enforceable.

---

## 2. Context-type taxonomy — what a reply may need

A good reply rarely needs "everything about the subject" — it needs specific *kinds* of context. Name the kind, and both the source and the query style follow. Five types:

| Context-type | What it is | Typical trigger in a tweet | Best source | Query style |
|---|---|---|---|---|
| **Identity** | who/what the author + referenced people, companies, products, projects *are* | an @handle or product/company name you can't place | memory → web (bio/about) → in-tab (author's own posts/pinned/bio) | entity name + "who is / what is / founder of / what does X do" |
| **Factual** | definitions, metrics, concrete claims, jargon; whether a stated number/claim is true | a term, a statistic, a "we hit N" claim, an acronym | web (authoritative/definitional) **and** X primary-source (the announcer's own tweet with real numbers) | precise noun-phrase; for a claim, the claim + "benchmark / results / announcement" |
| **Temporal / current** | recent events, latest development, "is this still true," what shipped this week | "just", "today", "new", "v3", a dated reference | web news (recency) **and** X (real-time, `since:`) | entity + "latest / release / news" + date bound; on X use `since:` |
| **Cultural / discourse** | prevailing takes, sentiment, memes/in-jokes, controversy, the sides, community norms, the *vibe* | a hot take, a subtweet, an in-joke, a pile-on, an "everyone's saying X" | **X primary** (discourse lives in other tweets) → web (only for a summarized controversy) | X search on the subject with `min_faves:` for high-signal takes; read the replies/QTs |
| **Relational** | tie to the persona's territory + prior engagements with this author/subject | any candidate (always check) | memory (dossiers + `profiles.csv` + prior `replies.csv`) | internal lookup, not a search |

The mapping *context-type → source + query style* is the core intelligence. Gap analysis emits a small structured set: `[{context_type, entity/claim, why_needed}]`. These five names — `identity` | `factual` | `temporal` | `discourse` | `relational` (`cultural` is an accepted alias for `discourse`) — **are** the `--gap-type` vocabulary passed to `context_cli search`, and the basis for the Layer-3 `gap_type` rollup (§5.1). Keep them as the one taxonomy; do not introduce a parallel set.

### 2.1 What counts as a gap — treat your own knowledge as stale

The most common enrichment failure is **false confidence**: the model reads a tweet, *feels* it already knows the subject, emits "no gaps," and drafts from generic, stale training memory — producing a reply that is plausible but non-specific, dated, or simply wrong. This is the single biggest reason a session does zero research when it should have done some. Guard against it:

- **Your training knowledge is not a source.** It is stale (cut off before the tweet) and generic (no current specifics). It cannot tell you what a named product actually does *today*, what just shipped, whether a cited number is real, who a person currently is, or the live state of a discourse.
- **A specific or current external fact that a load-bearing part of the reply depends on is a gap by default** — a metric/number the tweet cites, what a named person/company/product *is* or *just did*, whether a claim is true, the current sentiment around a subject — **even if you feel you know it.** Feeling that you already know a specific current fact is precisely the signal to distrust.
- **The test:** *would I be filling this from training-pattern-matching, rather than from the tweet itself, from memory (`scope=world`/`self`), or from something I just verified?* If yes → it is a gap; route it (§3, §5).
- **Only a genuine no-gap skips:** a pure quip on the visible wording, or a reply whose specificity comes entirely from the persona's own documented experience (`scope=self` memory). Do **not** manufacture a no-gap by choosing a vaguer angle or a lower-research archetype to *dodge* a fact you could have verified — decide the reply the candidate deserves, then resolve its gaps. Picking the angle that avoids research is the failure this step exists to catch.

---

## 3. Source-selection matrix — where each type lives

The critical point: **X is a source of BOTH factual and cultural context, not just discourse.** A founder's own announcement tweet is the *primary source* for their metrics/claims (more authoritative than a blog rehash); X is also where sentiment/memes/controversy live. Web is best for authoritative/biographical/definitional/news. Memory is always first; in-tab is for local thread structure.

| Source | Primary-source strength | Best for context-types | Not for |
|---|---|---|---|
| **Memory (dossiers + index, adapter 0)** | reused prior findings | relational, previously-resolved identity/factual | fresh developments |
| **In-tab X navigation (adapter a)** | the actual conversation structure | local: thread/quote/linked-article meaning | anything beyond this thread |
| **On-X search (adapter b)** | primary-source claims/numbers *and* live discourse | cultural/discourse; factual-primary (the announcer's own words); temporal (real-time) | neutral definitions, biography |
| **Off-X web `--search` (adapter c)** | authoritative third-party | identity/biographical, factual-definitional, temporal-news | live sentiment, memes, in-jokes |

The router keys on **context-type**, not a coarse "discourse vs factual": a single tweet can spawn an identity gap (→ web), a factual-primary gap (→ X search of the announcer), and a cultural gap (→ X discourse) — routed independently and often in parallel.

---

## 4. Query-construction playbook — ask smart, focused questions

Vague, single, kitchen-sink queries are the failure mode. The playbook:

1. **Extract first, then query.** Before any search, pull the specific named entities, terms, and checkable claims from the tweet (+ thread). Query *those*, not the tweet's gist. Entity/claim extraction is the retrieval-precision lever.
2. **One targeted query per gap**, not one query for the whole tweet. Each `[context_type, entity]` gets its own query in its source's syntax.
3. **Decompose complex gaps.** A multi-hop gap ("is this claim, which depends on that event, still true") splits into sub-queries answered in order. Use only for genuinely multi-hop gaps — don't over-decompose.
4. **Multi-query for recall** where one phrasing is risky: issue 2–3 alternative phrasings and fuse results. Keep variants *diverse*, not near-duplicates.
5. **Hypothetical-answer retrieval (optional, gated on retrieval-miss logs).** When a memory (adapter 0) query is short/vague against a technical subject and keeps missing, have the model write a one-sentence *hypothetical answer* and retrieve on **that** — it lands closer to the stored chunks than a terse query does. **Do not enable speculatively**: turn it on only if retrieval logs show a vocabulary-mismatch miss pattern. It is a retrieval enhancer for the memory read, not a live-search step.
6. **Source-appropriate syntax (never send web phrasing to X or vice versa):**
   - **X search operators** (typed into rendered X search — web-UI syntax, not API calls): quoted `"exact phrase"` for a specific claim/meme; `from:<handle>` for a person's own primary-source post; `min_faves:N` / `min_retweets:N` to surface only high-signal takes (cut noise on hot topics); `since:YYYY-MM-DD` / `until:YYYY-MM-DD` for recency; `filter:links` for sourced tweets; `filter:replies` to read reactions; negations (`-word`) to cut a noisy sense.
   - **Web phrasing**: precise noun phrases; `site:` scoping only when a known authoritative domain helps; date words for recency; **never** `site:x.com` / `site:twitter.com`, never "find tweets about."
7. **Read-refine-or-stop loop with a graded sufficiency gate.** Issue query → read results → **grade the gathered context: good / insufficient / ambiguous** → if *good* STOP; if *insufficient/ambiguous*, **escalate the source** (memory → on-X → off-X web) or refine one query; if escalation returns noise twice, STOP and mark `[VERIFY]`. **Explicit stop conditions:** context graded *good*, OR the session enrichment budget is hit (`max_context_lookups_per_session`, `config/limits.yaml`), OR two unproductive refinements. Never loop unbounded. The *grade* — not merely "is there a gap" — decides escalate-vs-stop.
8. **Verification / no-fact-invention (AGENTS.md §6).** Prefer primary sources; cross-check a load-bearing claim across two sources or the primary; if still unresolved, the fact stays `[VERIFY: ...]` in the draft — never guessed. Freshness caveat: an old high-`min_faves` tweet can be stale — check dates.

### 4.1 Few-shot example 1 — a metrics/claim tweet (factual-primary + identity gap)

> Tweet: *"@acme just crossed 10k paying teams on the new usage-based plan. wild what removing seats did to conversion."*

- **Gap analysis:** identity gap (who is @acme, what do they sell) + factual-primary gap (is "10k paying teams" real / is it their own claim) + relational (does pricing/PLG fit persona territory?).
- **Source selection:** identity → web (adapter c); factual-primary → X (adapter b, the announcer's own words); relational → memory (adapter 0).
- **Queries issued:**
  - Web (identity): `acme.com pricing usage-based teams` and `"Acme" company what does it do founder`
  - X (factual-primary, adapter b): `from:acme 10k teams` and `from:acme "usage-based" min_faves:50 since:2026-06-01` (find the primary announcement + its engagement)
  - Memory: dossier lookup for `acme`, prior replies to the author.
- **Distill:** "@acme = PLG dev-tool; founder announced usage-based pricing switch; 10k-teams claim is their own tweet (primary), ~2 weeks old." → chunks tagged `source_type=x_search|web`, `context_type=identity|factual`, `confidence=high(primary)`.

### 4.2 Few-shot example 2 — a cultural/discourse tweet (discourse + temporal gap)

> Tweet: *"the 'agents are just for loops' discourse is back and somehow dumber this time"*

- **Gap analysis:** cultural/discourse gap (what is the debate, who's saying it now, the sides) + temporal (why is it "back" — recent trigger) + identity (is a specific person being subtweeted?).
- **Source selection:** discourse → X (adapter b, primary); temporal trigger → X recency + maybe web news; identity → in-tab (adapter a, check if it's a QT/reply).
- **Queries issued:**
  - X (discourse, adapter b): `"agents are just for loops" min_faves:100` (high-signal takes only) and `"just for loops" agents filter:replies` (read the reactions/sides)
  - X (temporal): `"agents are just for loops" since:2026-07-01` (what retriggered it this week)
  - In-tab (adapter a): expand the candidate — is it quoting a specific tweet that started this round?
  - Web (only if needed): `"agents are just for loops" debate` for a summarized recap.
- **Distill:** "recurring reductionist take about agent frameworks; re-triggered ~this week by <QT'd post>; camps = framework-maximalists vs minimalists; tone is sardonic in-group." → chunks tagged `context_type=cultural|temporal`, `source_type=x_search`, `confidence=medium`. The *specific current angle* (who retriggered it, the exact vibe) is what lets the framing pass avoid the generic caveat.

---

## 5. Adapters + gap router — the transport behind the seam

Drafting consumes a `ContextBrief` (a scratch object the mode holds for one candidate) without knowing how the context was obtained. There are **four** adapters — the *transport* the acquisition intelligence above drives. The source-selection matrix (§3) decides which adapter serves each `[context_type, entity]` gap; the query playbook (§4) decides what to ask it.

**(0) Dossier / memory lookup (cache).** The free, first adapter, always tried first and uncapped. Semantically retrieve stored chunks for this subject via the context CLI — `python -m dashboard.context_cli search --query "<gap>" --scope <world|self|both> --gap-type <type>` (the runtime bridge over the policy layer `ContextMemory`, itself over the retrieval substrate `ContextStore`) rather than guessing a `<slug>.md` filename — top-k dossier/brief chunks, recency-blended, from **both scopes** (`world` and `self`) per the archetype-gated blend. Supplies stable background instantly; never the source of a *fresh* development on a new tweet.

**(a) In-browser X navigation (immediate context).** Browser-only, on-X, cheap. Within the §3 mimicry rules: expand/read the full thread and parent tweets, open the quoted tweet if the candidate is a quote, glance at the author's last few posts for what they're reacting to, open a linked article/thread. Stays in the **single focused timeline tab** — no new tab. Resolves *local* context (this thread, this quote, this link).

**(b) On-X discourse research (active subject research).** Browser-only, on-X. When the gap is about the *current conversation/culture* around a subject, person, or term — the discourse, the takes, the jargon, who's fighting about what — **or** about a factual-**primary** claim (an announcer's own numbers) — the agent does what a human does: opens an X search for that subject in a **scoped, serial research tab**, burst-pause reads recent high-signal tweets (mimicry §3.2 applies — this reads as a person researching, not a scraper), absorbs the conversation, then **closes the tab and returns to the timeline** before drafting. This reads *rendered* X search results — no API, no scraper — so it stays compliant with the browser-only non-negotiable. It requires the scoped research-tab exception; see §6.

**(c) Off-X factual research (native `--search`).** Off-X. For who/what/recent-news *background* the on-X read can't supply: what is this product/paper/company, who is this person, what shipped this week, what a term means in plain English. Guardrail: queries target background knowledge, never `site:x.com` / `site:twitter.com`, never "find tweets about." If a result is on X, ignore it — X facts come only from (a)/(b).

**Gap routing** (the §3 matrix applied per context-type, run inside 2.4b):

| Context-type of the gap | Route to |
|---|---|
| Relational; previously-resolved identity/factual | (0) memory / dossier index |
| Local (thread/quote/linked-article structure) | (a) in-tab X navigation |
| Cultural/discourse; factual-**primary** (announcer's own claim/number); temporal-realtime | (b) on-X search (research tab) |
| Identity/biographical; factual-**definitional**; temporal-news | (c) off-X `--search` |
| Mixed (common) — one tweet spawns several context-types | route each type independently; often (b)+(c)+(0) in parallel |

**Execution order within a candidate:** dossier (0, free) → immediate (a, cheap, in-tab) → then route to (b) and/or (c) per the table, only for the residual gap, only until the brief is good enough for the chosen archetype, and only within the budget. (b) and (c) are the *expensive* adapters the budget caps.

### 5.1 Provenance vocabulary (Layer-3 `context-provenance.csv`)

The Layer-3 review index (`scroll` §2.7 writes one row per enriched draft; `review` §3.6 joins it to engagement) summarizes a draft's enrichment in **two controlled vocabularies, both owned here** and mirrored by the schema in `dashboard/tables.py`. Fill the row from these — do not invent tokens:

- **`source_types`** — the set of adapters that actually contributed, one token per adapter, 1:1 with §5: `(0)` memory/dossier → `dossier`; `(a)` in-tab X navigation → `x_navigation`; `(b)` on-X research tab → `x_search`; `(c)` off-X `--search` → `web_search`. Record the subset that fired (e.g. a dossier hit plus one web lookup → `dossier,web_search`); empty when `context_used=false`.
- **`gap_type`** — a per-draft **rollup of the §2 context-type taxonomy**, not a per-lookup value: `none` (no gap / no enrichment), a single context-type name (`identity` | `factual` | `temporal` | `discourse` | `relational`) when one kind of gap dominated the draft, or `mixed` when several context-types were resolved. This records the *gap kind*, not the *source*: a gap resolved locally in-tab is still logged by its context-type here and separately as `x_navigation` under `source_types` — there is deliberately **no** `local` gap-type.

---

## 6. On-X research and the one-tab rule

Adapter (b) opens a second X tab, which conflicts with AGENTS.md §3.4 (*"one focused tab for the entire session"*). The intent of §3.4 is anti-detection: multiple concurrent tabs with automation activity across them is a bot signature no human produces. A human researching before a reply, by contrast, *does* open a second tab, reads it, and closes it — serially, one thing at a time.

The reconciliation is a **scoped, serial research-tab exception owned by AGENTS.md §3.4**, not a relaxation of the anti-detection intent. That rule is authoritative; this file only points to it. In summary: the agent may open **exactly one** additional X tab to run a subject search, read under §3.2 burst-pause mimicry, and must **close it before returning** to the timeline tab — at most one research tab at any moment, serial (never concurrent with timeline automation), opened→read→closed within a single enrichment step, under the same pacing (§3.5) and burst-pause (§3.2) rules. Only adapter (b) uses the research tab; adapter (a) uses no extra tab. A research pass costs real wall-clock against both `session_time_limit_minutes` and the research-tab sub-budget `context_research_time_budget_minutes`, and counts as one expensive lookup against `max_context_lookups_per_session` — stop opening research tabs the instant either the lookup cap or the research-time sub-budget is hit (`config/limits.yaml`).
