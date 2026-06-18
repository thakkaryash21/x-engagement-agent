# Tagging Playbook — the `--tagging` toggle

last_updated: 2026-06-13
status: hand-seeded (01-spec.md §4.4) — `learn` mode seeds real examples from the persona's historical tagging tweets

Active only when a `scroll` session runs with `--tagging` (01-spec.md, Operating Modes table — `compose` does not take this flag). When active, the agent additionally considers whether a reply, thread-reply, or quote is *better* composed by tagging a relevant high-profile user, connection, or follower — archetype 7 ("Tag-in") in `reply-playbook.md`.

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

Tagged drafts carry higher social risk and deserve closer human review — mark this clearly in the draft file (per the template in 01-spec.md §6.1, add a `**Tags**: @handle (category, follower_tier, relationship)` line directly under the Archetype/Tagging line).

---

## Seeded examples (from `learn` mode)

<!-- learn mode: collect tweets where the persona tagged someone and it worked —
     genuine value-add, shoutout, or quip. Distill the pattern (what made the tag
     work) here. Real examples only. -->

- Cruitical launch: `@thakkaryash21` and `@trycruitical` were tagged because the post was explicitly about building and launching together. Removing either tag would make the announcement less clear.
- Introduction credit: a reposted Quivly AI thread thanked `@trycruitical` for making an introduction. The tag works because it documents a real connection, not a reach tactic.
- Direct joke/context tag: `@ycombinator` appeared in a reply where the joke depended on YC being the addressed account. Use this pattern sparingly and only when the tagged account is already central to the visible thread.
- Product-fix tag: `@nikitabier plis fix` works only because it is a tiny, informal complaint aimed at the person associated with the product/social-app context. Do not turn this into a general "tag builders for bugs" tactic.
- Event/community tag: `@fdotinc` appears in demo-festival and Canopy context where Shubham had real-life participation. This is a safe tag pattern when the tagged org is part of the event being discussed.
- Exact-category plug tag: `@quivlyai` was tagged only after the target post asked for AI agents for customer success. This is acceptable when the tagged company is precisely relevant to the stated need.
- Tool recommendation tag: `@HappenstanceAI`, `@UseFastlane`, and similar tags work when the target explicitly asks for tools or examples. The tag should name the best-fit tool/person, not a generic friend or high-reach account.
- Event-credit tag: `@FoundationCap` and `@cmutehq` were tagged because the reply praised a specific event Shubham attended. This pattern needs real attendance or direct experience.
- Investor/founder suggestion tag: tags like `@aneelr` / `@Soma_Capital` are acceptable only when the target post asks for a list or recommendation and the tagged people are exact candidates.
- High-status product/company tag: `@OpenAI pls dont acquire and let this thrive` works as a joke because OpenAI is central to the visible AI/startup context. Do not use this as a reach tactic.


