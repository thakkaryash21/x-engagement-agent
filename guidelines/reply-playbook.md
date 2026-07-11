# Reply Playbook — archetypes

last_updated: 2026-07-10
status: public generic playbook; persona-specific calibration lives under `data/`

For each candidate tweet that passes `target-posts.md` and the profile gate (`profile-rubric.md`), `scroll` mode picks exactly one archetype below **before** writing the reply, and records it in `data/csv/replies.csv` (`reply_archetype` column). This is the join key `review` mode uses to learn which archetype works on which tweet type (`data/learnings/engagement-targets.md`).

Use the archetypes here as public defaults. Persona-specific examples, forbidden phrasing, lived-context constraints, and company-specific plug patterns belong in ignored local files such as:

- `data/personas/<active>.md`
- `data/style/<persona>-twitter-style.md`
- `data/learnings/*reply*`
- `data/learnings/*target*`
- `data/company-facts.md`

Examples and local calibration notes are register references, not templates. Never reuse a past tweet's wording, subject matter, handle, or exact framing in a new draft.

Tagging (archetype 7) is only available when the session runs with `--tagging`; see `tagging-playbook.md`.

---

### 1. Value-add

**Definition**: a concrete experience, data point, resource, or observation that extends the tweet and gives the reader something they did not have before.

**When it fits**: the target tweet states a claim or observation the persona can genuinely add to from lived experience, current work, customer/user insight, or a verifiable source.

**Output shape**: 1-2 sentences. Lead with the lived/owned specific — the thing the persona saw, shipped, hired around, or sold into — not a restatement of the tweet's number or claim. Does not look like: "[stat] is the signal / the line," then a knowing second-order caveat.

**Checks**:
- Name the actor affected: founder, customer, candidate, manager, user, operator, team, investor, reader.
- Prefer concrete nouns and consequences over abstract mechanism talk.
- If the value-add is not verifiable or lived, skip instead of inventing authority.

**Known failure modes**:
- Fake technical depth on specialist topics.
- Vague actor problem: unclear who is affected or what changes.
- Abstract metaphor problem: sounds clever but adds no information.

---

### 2. Sharp question

**Definition**: a concise question that moves the conversation forward by surfacing a useful gap, tradeoff, or assumption.

**When it fits**: the target tweet leaves an obvious open question and the persona can ask it naturally without posturing.

**Output shape**: one sentence that ends on an actual unanswered question mark. Open on the specific gap, not a preamble. Does not look like: a statement wearing a question mark, or a thesis smuggled in as "just curious."

**Checks**:
- Keep it answerable by the author.
- Do not smuggle in a thesis the persona cannot defend.
- Avoid specialist mechanics unless the persona can understand and use the answer.

**Known failure modes**:
- Fake curiosity.
- Leading questions that are really dunking.
- Questions so broad they cannot generate a useful answer.

---

### 3. Contrarian-with-receipts

**Definition**: respectful disagreement backed by specifics.

**When it fits**: the persona has a genuinely different view and can back it with a number, lived example, named precedent, or concrete mechanism.

**Output shape**: 1-3 sentences — the disagreement, then the receipt (number, named precedent, lived example). Open on the point of difference, not "actually" or "I think." Does not look like: a vague "actually…" with no evidence attached.

**Checks**:
- Disagree with the idea, not the person.
- Bring receipts or skip.
- Keep the tone inside the persona's red lines.

**Known failure modes**:
- Contrarian for reach.
- Domain cosplay.
- Vague "actually..." replies with no evidence.

---

### 4. Quip

**Definition**: humor in the persona's register, as defined by `data/style/<persona>-twitter-style.md`.

**When it fits**: the target tweet has an obvious comedic angle the persona would genuinely find funny.

**Output shape**: one beat, one line, no analysis. Open on the joke; don't set it up. Does not look like: a joke followed by a sentence explaining it, or a "funny that X, and the winning detail is still 'maxim'" clincher.

**Checks**:
- The joke should land without explaining itself.
- Keep it in the persona's observed voice.
- Do not use humor to dodge a serious topic unless that is explicitly in voice.

**Known failure modes**:
- Manufactured relatability.
- Overwritten jokes.
- Humor that violates red lines.

---

### 5. Amplify + extend

**Definition**: agree with the tweet, then add the missing half.

**When it fits**: the persona genuinely agrees and has something additive, not just a cleaner restatement.

**Output shape**: 1-2 sentences — brief agreement, then the missing downstream half (who does something differently, what changes next, what incentive becomes visible). Open on that extension's specific, not "this is huge" or "X is doing a lot here." Does not look like: the target tweet reworded in polished language, or "the useful [role] is the one who can…".

**Checks**:
- The extension should be downstream and concrete: what changes next, who does something differently, or what incentive becomes visible.
- If the second sentence says the same thing as the target tweet in polished language, rewrite or skip.
- Avoid grand framing unless the persona's style doc supports it.

**Known failure modes**:
- Hollow extension.
- Overbuilt sentence with too many abstractions.
- Forced cleverness.

---

### 6. Plug

**Definition**: a product/company/project reference that is organically useful in the conversation.

**When it fits**: the conversation is already about the problem the product/company/project solves, and the reference adds information the reader wants.

**Output shape**: 1-2 sentences with the reference sitting inside a genuine answer to the thread's problem. Open on the reader's problem, not the product. Does not look like: "check out [product]" bolted onto an otherwise unrelated reply.

**Hard constraint**: the no-fact-invention rule (AGENTS.md §6) applies in full — any factual claim, traction number, customer claim, launch claim, or comparison that isn't source-backed makes the draft flag `[VERIFY: ...]` instead of stating it.

**Known failure modes**:
- Cold redirects to "check us out."
- Claims that are directionally true but not source-backed.
- A plug that reads as engagement bait rather than context.

---

### 7. Tag-in (toggle mode only)

**Definition**: pulls a relevant person, company, or account into the discussion as a genuine value-add, credit, introduction, or context.

**When it fits**: only when `--tagging` is active. Full rules live in `tagging-playbook.md`.

**Output shape**: one sentence that names why the tagged account belongs in the thread (credit, intro, context). Open on the reason, not the handle. Does not look like: a bare "@handle 👀"-style reach tag.

**Checks**:
- The tag must clarify context or help readers.
- The tagged account should have a real reason to be included.
- Tagging a cold prominent account requires a stronger value justification than tagging a mutual, collaborator, customer, or real-life connection.

**Known failure modes**:
- Reach-seeking tags.
- Cold tags where the tagged person has no reason to respond.
- Tags that create social risk without adding reader value.
