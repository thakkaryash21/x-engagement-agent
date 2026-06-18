# Profile Rubric — categorizing and scoring authors

last_updated: 2026-06-13
status: hand-seeded (01-spec.md §4.3) — `learn` mode seeds real rows from the persona's interaction graph; `review` mode tunes the engage-gate thresholds below from outcomes

Whenever `scroll` considers engaging with a tweet, it looks up or creates the author's row in `data/data/profiles.csv` and scores it against this rubric. This is what answers the four requirement-level questions: *do we engage with this tweet? would it be good for engagement? how is this user relevant to us? are they credible/reputed?*

---

## Rubric axes

| Axis | Values | What it captures |
|---|---|---|
| `category` | founder / VC / engineer / researcher / anon-builder / journalist / recruiter / other | What kind of account this is |
| `follower_tier` | nano (<1k) / small (1-10k) / mid (10-100k) / large (100k-1M) / mega (>1M) | Audience size bucket |
| `role_clout` | 1-5 | Positional authority — known company, known fund, known project |
| `audience_activity` | 1-5 | Do their tweets get real replies, or is it a ghost town? |
| `geography` | best-effort from bio/content | |
| `relevance` | 1-5 | Overlap with persona territory + Cruitical |
| `credibility` | 1-5 | Track record, verifiable claims, not a clout-farmer |
| `relationship` | none / they-follow / we-follow / mutual / real-life connection | |

## Engage decision

A tweet is engagement-eligible (subject to `target-posts.md` already having passed) when:

```
relevance >= 3 AND credibility >= 3 AND (audience_activity >= 3 OR relationship != none)
```

These thresholds are deliberately simple starting points. `review` mode may tune them in place (per the correction rule, 01-spec.md §8.1) once `data/data/profiles.csv` × `data/data/metrics.csv` shows which combinations of scores actually correlate with good outcomes — e.g. "relevance 3 + credibility 3 + audience_activity 2 + relationship=they-follow" performing as well as the current gate.

### Shubham-specific overrides

The simple gate above is necessary but not sufficient for Shubham. Apply these overrides after scoring:

- **Nano/small mutuals are not automatic**. If `follower_tier` is `nano` or `small` and `audience_activity <= 2`, engage only when the author has a real relationship, F.DOT/SF builder context, or a direct Cruitical/hiring-agent overlap worth nurturing.
- **Competitors require a reason**. Hiring-space builders who could be competitors are not default targets. Engage only when the relationship is already meaningful or the reply helps Shubham's positioning without giving free validation to a low-traction post.
- **Large audience does not override missing voice fit**. A large or mega author is still a skip if the only available reply is abstract, technical cosplay, or outside Shubham's lived expertise.
- **Corporate accounts need artifact quality**. Company accounts should pass only when the product artifact is specific enough for a grounded product judgment, or when the account/founders are strategically relevant. Do not reply to generic launches for reach alone.
- **Technical credibility belongs to the author, not Shubham**. A credible researcher/engineer author does not make Shubham credible to discuss the deep technical substance. If Shubham cannot naturally shift the point to users, product, hiring, founder operations, or social consequences, skip.

## Studying vs. engaging

Every author considered gets a row in `profiles.csv`, scored against this rubric — **even if the engage gate fails**. Studying an author (reading their profile, scoring them) is not the same as engaging with them, and the resulting row still feeds `learn` mode's network model and future engage decisions for other tweets by the same author.

---

## Seeded profile taxonomy

<!-- learn mode: as the interaction graph is built (01-spec.md §7 step 3), record any
     recurring patterns here — e.g. "category=VC accounts in our network skew
     relevance 4-5 but audience_activity 2-3" — that help interpret the rubric
     consistently across future sessions. Real examples only, no invented accounts. -->

- Partial learn pass pattern: Shubham engages with founder/operator accounts where community, hiring, dev tools, or applied AI is already the topic. `@5harath` is the clearest opened profile example: mid-tier audience, founder/community/operator background, SF/ATL context, and followed by multiple accounts Shubham follows.
- High-relevance visible targets in the sampled feed were not all large accounts. The useful criterion was topical fit plus a plausible relationship or community overlap, not follower count alone.
- Startup/AI/product accounts with active replies and concrete operator context should generally score higher than generic tech commentary accounts with similar audience size.
- Large developer educator accounts can be high-relevance when the post is about dev tools, agents, recruiting quality, or writing craft. `@leerob` is the opened example: large audience, strong shared-follow graph, Cursor/Vercel context.
- VC/investor accounts should not pass on clout alone. `@dotcuriouscat` was relevant because the reposted content was specifically about founder psychology and first-round investing, not generic venture discourse.
- Organizations in Shubham's lived ecosystem, especially `@fdotinc`, should score `relationship=real-life connection` or equivalent when the post relates to an actual program/event Shubham participated in.
- Founder accounts building people/company data, recruiting tools, or customer-success agents can be highly relevant even with small audiences. `@TheChowdhary` is the opened example: YC founder, Crustdata, AI-agent data/recruiting overlap, and followed by accounts Shubham follows.
- Expanded interaction-graph pass: small follower-tier accounts should still pass when they have direct relationship/context. Examples: `@Chandrika633`, `@jananiprasad24`, `@joypbuilds`, `@g0da_s`, and `@adelwu_` all have small/nano audiences but stronger fit because they follow Shubham and sit in the SF/F.DOT/building-AI-products network.
- Mid-tier founder/operator accounts are the densest useful bucket. Examples include `@hthieblot`, `@steventey`, `@DhravyaShah`, `@marty_kausas`, `@villi`, `@yasser_elsaid_`, `@nizzyabi`, and `@thatguybg`. Score these highest when the post is about founder events, product craft, AI agents, GTM/support, hiring, or SF builder culture.
- Large and mega accounts are not automatic targets. `@paulg`, `@signulll`, `@brian_lovin`, `@stephsmithio`, and `@GergelyOrosz` are useful only when Shubham has a specific mechanism, taste judgment, or lived example to add.
- Local/SF social-context accounts can be relevant even when not Cruitical-adjacent. `@Aartiutwani`, `@jayyeh`, and similar profiles are valid when the reply contributes concrete local knowledge or founder-network surface.
- Corporate/product accounts such as `@NebulaAI` and `@thinkwithmark` should score lower on relationship and credibility than founder/operator accounts unless the post is an exact-category fit or the product artifact itself is the point.


