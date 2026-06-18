# Format Playbook — Reply

last_updated: 2026-06-12
status: hand-seeded (01-spec.md §4.5)

A reply joins an existing conversation. It is read by people scrolling that thread — primarily the original author and whoever else is already in the replies, not the persona's own followers (that's `quote.md`).

## Rules

- Optimize for adding to the discussion **in place** — the reply should make sense to someone reading the thread top to bottom, without needing to know anything about the persona.
- Don't restate the original tweet. Assume the reader just read it.
- Pick the archetype (`reply-playbook.md`) before writing, and let the archetype shape length and tone — a quip reads very differently from a value-add.
- `reply_rank` (recorded in `data/data/replies.csv`) matters: an early reply (low rank) earns more visibility, so favor target tweets that are still early per `target-posts.md`.

## What breaks this format

- Replies that are really just a standalone tweet that happens to be posted under someone else's — if it doesn't engage with what the target tweet actually said, it should probably be a `quote` or an original tweet instead.
- Replies that assume the persona's own followers are the audience (that's `quote.md`'s job).


