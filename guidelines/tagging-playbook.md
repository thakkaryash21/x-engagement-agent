# Tagging Playbook — the `--tagging` toggle

last_updated: 2026-07-11
status: hand-seeded — `learn` mode seeds real examples from the persona's historical tagging tweets into local data

Active only when a `scroll` session runs with `--tagging` (`compose` does not take this flag). When active, the agent additionally considers whether a reply, thread-reply, or quote is *better* composed by tagging a relevant high-profile user, connection, or follower — archetype 7 ("Tag-in") in `reply-playbook.md`.

---

## What counts as a good tag

- The tagged person is genuinely relevant to the point being made — pulling them into a discussion they'd plausibly want to see, a deserved shoutout/plug, or a humorous quip that involves them in a way they'd be fine with.
- The tag adds value **for readers**, not just reach. If removing the @handle would make the tweet read identically, the tag is decorative — don't use it.
- Consistent with `relationship` in `data/csv/profiles.csv`: tagging someone with `relationship=none` is higher-risk and should have a stronger value justification than tagging a `mutual` or `real-life connection`.

## What this is NOT

- Not pure reach-grabbing. "Tag a big account so they notice me" is the failure mode this playbook exists to prevent.
- Not a substitute for relevance. A tag doesn't rescue an otherwise weak reply.

## Guardrail: surfacing, not an allowlist

The agent never needs pre-approval to **propose** a tag — only to **send** one, same as everything else (AGENTS.md §1, principle 3). The guardrail is that any draft containing a tag is flagged in the draft file and in `data/csv/replies.csv`/`tweets.csv` (`tagged_users` column), and the dashboard's draft card shows a prominent callout: *"this draft tags @handle (category, follower tier, relationship: <value>)"*. The human makes the call per draft with full context — there is no pre-approved list of taggable accounts.

## Drafting note

Tagged drafts carry higher social risk and deserve closer human review — mark this clearly in the draft file by adding a `**Tags**: @handle (category, follower_tier, relationship)` line directly under the Archetype/Tagging line.

---

## Seeded patterns (from `learn` mode)

<!-- learn mode: collect tweets where the persona tagged someone and it worked —
     genuine value-add, shoutout, or quip. Distill the pattern (what made the tag
     work) here. Real examples only. -->

- Launch tags work when the tagged people or company are central to the announcement. Removing the tag should make the post less clear.
- Introduction-credit tags work when they document a real connection or handoff, not as a reach tactic.
- Direct joke/context tags work only when the tagged account is already central to the visible thread.
- Product-fix tags work only when the complaint is tiny, informal, and aimed at the person or team associated with the product context.
- Event/community tags work when the persona had real-life participation and the tagged organization is part of the event being discussed.
- Exact-category plug tags are acceptable when the tagged company/person is precisely relevant to a stated need.
- Tool recommendation tags work when the target explicitly asks for tools or examples. The tag should name the best-fit tool/person, not a generic friend or high-reach account.
- Event-credit tags need real attendance or direct experience.
- Investor/founder suggestion tags are acceptable only when the target post asks for a list or recommendation and the tagged people are exact candidates.
- High-status product/company tags can work as jokes only when the tagged account is central to the visible context. Do not use this as a reach tactic.
- Cofounder/company milestone tags work when the post is already about the shared work, launch artifact, demo, or progress update. The tag should identify who was actually involved.
- Product-context tags work when the tagged tool/company is the visible object of the joke or observation. Do not tag a tool just to borrow its audience.
- Community/event tags work when the persona was actually present or directly part of the group being discussed. Pair them with concrete event/place context.
- Multi-account credit blocks belong only in owned launch or event follow-ups where every tagged person had a visible role. Name the contribution or company; do not turn a normal reply into a tag roster.
- Cofounder credit tags work best as a natural aside tied to a visible artifact, such as crediting who chose a launch detail. The tag documents shared work rather than borrowing reach.
- Multi-account tags belong in owned event recaps when each handle identifies a co-judge, organizer, example company, or collaborator visible in the post.
- A company tag in a hiring CTA is justified when the company is the actual hiring vehicle and the post names exact roles; it is not a generic distribution tag.


