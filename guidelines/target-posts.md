# Target Posts — what to look for in `scroll`

last_updated: 2026-06-13
status: hand-seeded (01-spec.md §4.1) — maintained by `review` mode (AGENTS.md §4.5)

This file defines what makes a tweet worth the persona's attention during `scroll`. It is read in step 1 of the scroll loop (AGENTS.md §4.2), before any profile or duplicate checks. A tweet that fails this filter is skipped without studying the author.

---

## Topic filters

A tweet is in-territory if it falls inside the active persona's `## Territory` list (`data/personas/<active>.md`). Out-of-territory tweets are skipped regardless of how good the format or timing looks — territory match is a precondition, not a scoring input.

## Format signals

Each signal below maps to whether the persona has a credible angle. `review` mode tunes this table from real outcomes (engagement-targets.md).

| Signal | Credible angle? | Notes |
|---|---|---|
| Question (genuine, answerable) | Yes | Prefer questions where the persona has a concrete, specific answer — not a generic take |
| Hot take / opinion | Yes, if territory-matched | Reply via contrarian-with-receipts or amplify+extend (reply-playbook.md) |
| Build-in-public update | Yes | Natural fit for amplify+extend or value-add |
| Technical thread | Yes, if thread is read in full (thread-reply.md — hard rule) | |
| Launch post | Yes, cautiously | See content-playbook.md once seeded — launch-post replies are a known area for archetype mismatch |
| Rage bait / outrage post | No | Hard skip signal below |
| Pure engagement-bait ("agree?", "thoughts?", polls) | No | Replying here looks like bait-chasing, not engagement |

## Freshness / stage

- Prefer tweets **< 4 hours old** with **< 30 replies** — early replies earn disproportionate visibility (the "early-reply hypothesis," tracked via `reply_rank` in `data/csv/replies.csv`).
- Skip tweets where the reply section is already saturated with the same take the persona would make — adding a 40th identical reply has no value for readers and no signal for us.

## Credible contribution gate

Passing topic/freshness is not enough. Before opening the profile, answer this in plain language:

> What could Shubham add here that is true, natural for him to say, and useful to a reader?

Skip the tweet if the answer depends on any of these:

- **Specialist technical knowledge Shubham does not visibly have**. Do not reply to deep RL, dataset-methodology, hardware, frontier-model internals, geopolitics, or other expert-only topics just because the author is credible. If the reply would require sounding like a researcher, skip.
- **Conjured operator experience**. If Shubham has not used the workflow, built near it, hired around it, or seen it through Cruitical/founder context, do not invent a company/process take.
- **Abstract agreement**. "This affects workflows/companies/operators" is not a contribution unless the draft can name the specific user, team, product surface, hiring loop, support process, or founder decision being affected.
- **A relationship/incentive mismatch**. Small or nano accounts pass only with real relationship/context or a high-probability relationship payoff. A mutual connection alone is not enough when the tweet has low traction and no clear network value.
- **A too-narrow audience call**. Skip posts aimed at a group Shubham is not part of (e.g. "Swiss founders") unless he has a concrete outside perspective that group would still find useful.
- **Company-account launch replies with no relationship path**. Corporate accounts are usually skips unless the artifact itself is exceptional, the founders/team are in-network, or the post is exactly in hiring/agents/product territory and has visible traction.

## Skip signals (hard skips, independent of topic match)

- Rage bait or outrage-farming content
- Ambiguous context that can't be resolved by reading the thread
- Threads requiring claims the persona can't verify (no fact invention — AGENTS.md §6)
- Anything touching a red line in `data/personas/<active>.md`
- Replies whose best draft would be "smart-sounding" rather than useful. If the idea is mostly a phrase like "the real shift," "the useful distinction," "this gets weird," or "X becomes the operating system," skip or rethink from scratch.

---

## Review-mode maintenance

`review` mode may add or reweight rows in the Format Signals table based on `data/learnings/engagement-targets.md` evidence. Per the correction rule (01-spec.md §8.1), a row that's contradicted by ≥3 consistent data points is rewritten in place, not appended around.


