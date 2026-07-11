# Format Playbook — Reply

last_updated: 2026-07-10
status: hand-seeded

A reply joins an existing conversation. It is read by people scrolling that thread — primarily the original author and whoever else is already in the replies, not the persona's own followers (that's `quote.md`).

This format's only unique rule is the audience: a reply is read **in place** by the thread's participants, not by the persona's own followers (that is `quote.md`). Everything else defers to an owning file.

## Rules

- Optimize for adding to the discussion **in place** — the reply should make sense to someone reading the thread top to bottom, without needing to know anything about the persona.
- Don't restate the original tweet. Assume the reader just read it.
- Pick the archetype before writing (`reply-playbook.md` owns the archetypes and their output shapes) — a quip reads very differently from a value-add.
- Early-reply visibility and freshness/`reply_rank` are owned by `target-posts.md` (Freshness / stage) — favor target tweets that are still early.

## What breaks this format

- Replies that are really just a standalone tweet that happens to be posted under someone else's — if it doesn't engage with what the target tweet actually said, it should probably be a `quote` or an original tweet instead.
- Replies that assume the persona's own followers are the audience (that's `quote.md`'s job).


