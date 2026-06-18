# Profile Rubric — categorizing and scoring authors

last_updated: 2026-06-18
status: public generic rubric; persona-specific overrides live under `data/`

Whenever `scroll` considers engaging with a tweet, it looks up or creates the author's row in `data/csv/profiles.csv` and scores it against this rubric. This answers the four operating questions:

- Do we engage with this tweet?
- Would it be useful for engagement?
- How is this author relevant to the active persona?
- Is this author credible or reputable enough to engage?

This file defines the reusable public gate. Persona-specific targeting notes, strategic account lists, local network context, competitor handling, and real examples belong in ignored local files such as:

- `data/personas/<active>.md`
- `data/learnings/*profile*`
- `data/learnings/*target*`
- `data/csv/profiles.csv`

---

## Rubric axes

| Axis | Values | What it captures |
|---|---|---|
| `category` | founder / VC / engineer / researcher / anon-builder / journalist / recruiter / operator / company / other | What kind of account this is |
| `follower_tier` | nano (<1k) / small (1-10k) / mid (10-100k) / large (100k-1M) / mega (>1M) | Audience size bucket |
| `role_clout` | 1-5 | Positional authority: known company, known fund, known project, visible expertise |
| `audience_activity` | 1-5 | Do their tweets get real replies, or is it a ghost town? |
| `geography` | best-effort from bio/content | Useful local, market, or community context |
| `relevance` | 1-5 | Overlap with active persona territory, goals, and company/project context |
| `credibility` | 1-5 | Track record, verifiable claims, not a clout-farmer |
| `relationship` | none / they-follow / we-follow / mutual / real-life connection | Existing social or professional connection |

## Engage decision

A tweet is engagement-eligible, subject to `target-posts.md` already having passed, when:

```text
relevance >= 3 AND credibility >= 3 AND (audience_activity >= 3 OR relationship != none)
```

Apply persona-specific overrides after this generic gate. If a local override contradicts this file, the local override wins for that persona but should be documented under `data/learnings/`.

These thresholds are deliberately simple starting points. `review` mode may tune them in place once `data/csv/profiles.csv` x `data/csv/metrics.csv` shows which score combinations correlate with good outcomes.

## Generic overrides

- **Large audience does not override missing fit.** A large or mega account is still a skip if the only available reply is abstract, off-voice, or outside the persona's expertise.
- **Small audience does not automatically fail.** Nano/small accounts can be high-value when relevance, relationship, or community context is strong.
- **Corporate accounts need artifact quality.** Company accounts should pass only when the product artifact is specific enough for a grounded product judgment, or when the account/founders are strategically relevant.
- **Technical credibility belongs to the author.** A credible expert author does not make the persona credible to discuss deep specialist substance. If the persona cannot naturally shift the point to their own territory, skip.

## Studying vs. engaging

Every author considered gets a row in `data/csv/profiles.csv`, scored against this rubric, even if the engage gate fails. Studying an author is not the same as engaging with them; the resulting row feeds `learn` mode's network model and future engage decisions.

---

## Seeded profile taxonomy

`learn` mode and `review` mode should add real, persona-specific patterns to local data files, not this public template. Use local entries for recurring patterns such as:

- accounts that are strategically relevant despite small audiences
- account categories that underperform despite apparent relevance
- local communities where relationship strength matters more than audience size
- company/product accounts that deserve special handling
- competitor or adjacent-category accounts that need extra caution
