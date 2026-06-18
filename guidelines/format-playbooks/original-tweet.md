# Format Playbook — Original Tweet

last_updated: 2026-06-12
status: hand-seeded (01-spec.md §4.5)

An original tweet (drafted in `compose` mode) has no target tweet — it's posted to the persona's own timeline, for their own followers. Topic and hook selection live in `compose-playbook.md`; this file covers format-specific writing rules once a topic/hook is chosen.

## Rules

- Must stand alone — by definition there's no surrounding context to lean on.
- Length and structure follow the voice guide's Twitter/X section for the chosen `content_type` (`compose-playbook.md`): most observations/takes/quips are 1-3 sentences; threads only when the thought genuinely needs more than one tweet.
- `content_type` and `hook_type` are chosen explicitly before writing (per `compose-playbook.md`) and recorded in `data/data/tweets.csv` — this is the join key `review` mode uses for `data/learnings/content-playbook.md` and `data/learnings/timing-playbook.md`.

## What breaks this format

- Thread-baiting ("a thread on X (1/12)") or generic engagement-bait questions — explicitly against the voice guide and the anti-engagement-bait rule (AGENTS.md §6).
- Treating an original tweet as a delayed reply to something seen during `scroll` without making it stand alone — if the thought only makes sense in reply to something specific, it belongs in `scroll`'s queue, not `compose`'s.


