# Compose Playbook — original tweets

last_updated: 2026-07-10
status: hand-seeded — `review` mode tunes topic/hook choices from `data/learnings/content-playbook.md` and `data/learnings/timing-playbook.md`

`compose` mode drafts original tweets (not replies). This file defines how a topic and a hook get selected before writing — both are chosen explicitly and recorded in `data/csv/tweets.csv` (`content_type`, `hook_type`) so the review loop can attribute performance to them.

---

## Topic selection

Topic = the persona's `## Territory` (`data/personas/<active>.md`) crossed with whatever `data/learnings/content-playbook.md` says is currently working for this persona. Until `review` mode has produced entries there (requires ≥5 reviewed sends), default to territory alone, picking whichever topic area the persona has something genuinely current to say about — a real build-in-public update, a real reaction to something seen during `scroll`, a real opinion.

No topic is selected "because it's due" — if nothing in-territory feels genuine right now, `compose` may end the session with zero drafts. An empty session is a valid outcome.

## `content_type` values

| content_type | Description |
|---|---|
| build-update | What's actually happening in the persona's company/project/work — concrete, specific, and source-backed |
| take | An opinion or observation, territory-matched |
| question | A genuine question to the persona's audience — not engagement-bait phrasing |
| thread | Only when the thought genuinely needs more than one tweet (voice guide: "no threads unless the thought genuinely needs one") |
| quip | Short, dry, observational humor in the persona's register |

## `hook_type`

The opening line/sentence pattern — recorded so `review` mode can correlate hook style with impressions. Examples to start from (voice guide, Twitter/X section): observational wit, product/industry criticism with specificity, dry one-liner, direct statement of a build update. `hook_type` is free text; `review` mode may converge it into a fixed set once patterns repeat ≥3 times.

## Drafting pipeline

This file owns only topic and hook selection (above). The drafting pipeline itself — the ordered passes and the Anti-AI hard gate — is owned by `modes/scroll.md` §2.6 and applied for original tweets per `modes/compose.md` §2. The output row (`data/csv/tweets.csv`, `status=drafted`) and draft file follow that procedure. Do not restate the pipeline here.

---

## What's working (from `review` mode)

<!-- review mode: once >=5 reviewed sends exist, summarize which content_type/topic
     combinations correlate with the optimize targets in config/metrics.yaml for the
     `tweet` format. Per the correction rule, rewrite in place when
     contradicted. -->


