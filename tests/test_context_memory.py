"""Plan 07 §5.4/§5.5/§5.5.1/§5.7 — ContextMemory: the stable policy layer.

Tests the policy that must survive a substrate swap: the
score = a·relevance + b·recency + c·importance blend, dedup/merge on write,
the promotion gate, reflection, evidence preservation, and diversity-selected
style exemplars. Runs against a temp data/context dir with the FakeEmbedder;
never touches the real data/.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from pathlib import Path
from typing import Sequence

import pytest

from dashboard.context_memory import ContextMemory
from dashboard.context_store import ContextStore

NOW = dt.datetime(2026, 7, 10, 12, 0, 0)


class SemanticEmbedder:
    """A synonym-aware embedder for the hybrid-retrieval test.

    Unlike the bag-of-words FakeEmbedder, this maps synonyms onto a shared topic
    axis, so dense similarity is decoupled from literal token identity — exactly
    the regime where a semantic embedder misses an exact error code and the
    lexical path must rescue it (Plan 08 fix 8). Literal codes/handles are
    out-of-vocabulary and contribute nothing to the dense vector.
    """

    AXES = {
        "incident": {"downtime", "outage", "incident"},
        "billing": {"billing", "pricing", "invoice"},
        "postmortem": {"postmortem", "retro", "retrospective"},
        "resolved": {"resolved", "fixed", "closed"},
    }

    def __init__(self) -> None:
        self._axes = list(self.AXES)
        self._lookup = {w: i for i, ax in enumerate(self._axes) for w in self.AXES[ax]}

    @property
    def dim(self) -> int:
        return len(self._axes)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
                idx = self._lookup.get(tok)
                if idx is not None:
                    vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec))
            if norm:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out


@pytest.fixture
def store(tmp_path: Path, fake_embedder) -> ContextStore:
    return ContextStore(tmp_path / "data" / "context", embedder=fake_embedder)


@pytest.fixture
def memory(store: ContextStore) -> ContextMemory:
    return ContextMemory(store, now=NOW)


def _finding(**over):
    base = {
        "text": "a fact",
        "scope": "world",
        "source_type": "web_search",
        "context_type": "factual",
        "confidence": "high",
        "importance": 0.7,
        "entities": ["acme"],
        "created_at": NOW.isoformat(),
        "provenance": "https://acme.com",
        # Real captured raw source: fix 5 requires this before a fact can promote.
        # Tests that exercise the no-evidence path override with ``evidence=None``.
        "evidence": "RAW captured source backing this fact",
    }
    base.update(over)
    return base


# --- §5.4 score blend ---------------------------------------------------------

def test_importance_beats_recency_at_similar_relevance(store: ContextStore, memory: ContextMemory):
    """A durable high-importance chunk outranks a fresher low-importance one."""
    old = (NOW - dt.timedelta(days=40)).isoformat()
    # Both share the query tokens -> similar relevance; they differ in
    # importance (0.9 vs 0.1) and recency (40 days old vs brand new).
    store.add(
        "rebuilt onboarding and conversion doubled",
        {"scope": "world", "context_type": "insight", "confidence": "high",
         "importance": 0.9, "entities": ["onboarding"], "created_at": old,
         "last_refreshed": old, "chunk_id": "durable"},
    )
    store.add(
        "onboarding conversion dipped slightly today",
        {"scope": "world", "context_type": "temporal", "confidence": "low",
         "importance": 0.1, "entities": ["onboarding"], "created_at": NOW.isoformat(),
         "last_refreshed": NOW.isoformat(), "chunk_id": "fresh"},
    )

    ranked = memory.retrieve_content("onboarding conversion", scope="world", k=8)
    assert ranked[0]["chunk_id"] == "durable"
    # And the durable chunk really is older but still wins on the blend.
    assert ranked[0]["recency"] < ranked[1]["recency"]
    assert ranked[0]["score"] > ranked[1]["score"]


def test_missing_timestamp_is_stale_not_freshest(store: ContextStore, memory: ContextMemory):
    """Plan 08 fix 16: a chunk with a missing/invalid timestamp must be treated as
    STALE, never as the freshest — it cannot outrank a properly dated peer."""
    store.add("launch update alpha dated", {"scope": "world", "context_type": "temporal",
              "importance": 0.5, "entities": ["launch"], "created_at": NOW.isoformat(),
              "last_refreshed": NOW.isoformat(), "chunk_id": "dated"})
    store.add("launch update alpha undated", {"scope": "world", "context_type": "temporal",
              "importance": 0.5, "entities": ["launch"], "created_at": "",
              "last_refreshed": "", "chunk_id": "undated"})
    ranked = memory.retrieve_content("launch update alpha", scope="world", k=8)
    by_id = {r["chunk_id"]: r for r in ranked}
    assert by_id["undated"]["recency"] == 0.0        # missing => stale, not 1.0
    assert by_id["dated"]["recency"] > by_id["undated"]["recency"]
    assert ranked[0]["chunk_id"] == "dated"


def test_recency_wins_when_importance_equal(store: ContextStore, memory: ContextMemory):
    old = (NOW - dt.timedelta(days=60)).isoformat()
    store.add("launch update alpha", {"scope": "world", "context_type": "temporal",
              "importance": 0.5, "entities": ["launch"], "created_at": old,
              "last_refreshed": old, "chunk_id": "stale"})
    store.add("launch update alpha", {"scope": "world", "context_type": "temporal",
              "importance": 0.5, "entities": ["launch"], "created_at": NOW.isoformat(),
              "last_refreshed": NOW.isoformat(), "chunk_id": "fresh"})
    ranked = memory.retrieve_content("launch update alpha", scope="world", k=8)
    assert ranked[0]["chunk_id"] == "fresh"


# --- §5.5 stage 2 dedup/merge -------------------------------------------------

def test_dedup_merge_on_write(store: ContextStore, memory: ContextMemory):
    result = memory.write_back([
        _finding(text="acme switched to usage based pricing", entities=["acme"],
                 confidence="medium", reusable=True),
        _finding(text="acme switched to usage based pricing", entities=["acme"],
                 confidence="high", reusable=True),
    ])
    assert len(result["promoted"]) == 1
    assert len(result["merged"]) == 1

    hits = store.search("acme usage based pricing", k=10)
    unique_ids = {h["chunk_id"] for h in hits}
    assert len(unique_ids) == 1  # not two copies of the same fact
    # merge kept the higher-confidence text and only one chunk file exists.
    assert len(list(store.chunks_dir.glob("*.md"))) == 1
    assert hits[0]["confidence"] == "high"


# --- §5.5 stage 3 promotion gate ---------------------------------------------

def test_promotion_gate_reusable_persists_oneoff_does_not(store: ContextStore, memory: ContextMemory):
    result = memory.write_back([
        _finding(text="acme is a plg dev tools company", entities=["acme"],
                 context_type="identity", reusable=True),
        _finding(text="the tweet had a typo in the third word", entities=["typo"],
                 context_type="factual", reusable=False),
    ])
    assert len(result["promoted"]) == 1
    assert len(result["brief_only"]) == 1

    # Only the reusable chunk entered the retrievable store.
    assert len(list(store.chunks_dir.glob("*.md"))) == 1
    assert store.search("acme dev tools", k=10)
    oneoff_hits = store.search("typo third word", k=10)
    assert all("typo" not in (h.get("entities") or []) for h in oneoff_hits)


def test_promotion_gate_requires_sighting_without_explicit_flag(store: ContextStore, memory: ContextMemory):
    """Plan 08 fix 10: with no explicit reusable verdict, do NOT promote on first
    sight — a durable identity fact promotes only once its subject is sighted
    enough times; low-importance ephemeral material never promotes."""
    first = memory.write_back([
        _finding(text="acme founder background", context_type="identity",
                 importance=0.8, subject_slug="acme"),
    ])
    assert first["promoted"] == []          # first sighting stays ephemeral
    assert len(first["brief_only"]) == 1

    second = memory.write_back([
        _finding(text="acme founder background detail two", context_type="identity",
                 importance=0.8, subject_slug="acme"),
    ])
    assert len(second["promoted"]) == 1     # second sighting of the subject promotes

    # Low-importance ephemeral material never promotes, however often it is seen.
    last = None
    for _ in range(3):
        last = memory.write_back([
            _finding(text="passing meme about loops", context_type="temporal",
                     importance=0.2, entities=["loops"], subject_slug="loops"),
        ])
    assert last["promoted"] == []
    assert len(last["brief_only"]) == 1


# --- §5.7 evidence preservation ----------------------------------------------

def test_write_back_preserves_evidence(store: ContextStore, memory: ContextMemory):
    result = memory.write_back([
        _finding(text="distilled claim", evidence="RAW captured page text here",
                 reusable=True),
    ])
    assert len(result["evidence"]) == 1
    evidence_id = result["evidence"][0]
    evidence_path = memory.evidence_dir / f"{evidence_id}.md"
    assert evidence_path.is_file()
    raw = evidence_path.read_text(encoding="utf-8")
    assert "RAW captured page text here" in raw
    assert "captured_at:" in raw
    # The stored chunk links back to its evidence record.
    hits = store.search("distilled claim", k=5)
    assert hits[0]["evidence_id"] == evidence_id
    # Content-addressed id: re-deriving from the raw bytes reproduces the id.
    from dashboard.context_memory import _content_address, _valid_evidence_id
    assert _valid_evidence_id(evidence_id)
    assert evidence_id == _content_address("RAW captured page text here")


def test_no_evidence_finding_cannot_promote(store: ContextStore, memory: ContextMemory):
    """Fix 5: a finding with no captured raw source is NOT promotable, even with
    an explicit reusable verdict — its distilled text can't be its own evidence."""
    result = memory.write_back([
        _finding(text="acme raised a 50m series b last week", evidence=None,
                 provenance="", reusable=True),
    ])
    # Stays brief-only; nothing durable, no fabricated evidence record.
    assert result["promoted"] == []
    assert result["merged"] == []
    assert len(result["brief_only"]) == 1
    assert result["evidence"] == []
    assert list(store.chunks_dir.glob("*.md")) == []
    assert list(memory.evidence_dir.glob("*.md")) == []
    # And the distilled paraphrase never entered the retrievable store.
    assert store.search("acme series b", k=10) == []


def test_evidence_reference_to_existing_record_promotes(store: ContextStore, memory: ContextMemory):
    """A re-verification finding with no fresh raw text may cite an EXISTING,
    valid evidence record and promote; a dangling reference may not."""
    # Seed a real evidence record via a first captured finding.
    first = memory.write_back([
        _finding(text="acme ships developer tools", evidence="RAW: acme about page",
                 subject_slug="acme", context_type="identity", reusable=True),
    ])
    evidence_id = first["evidence"][0]

    # A later finding with no raw source but a valid existing evidence reference.
    ok = memory.write_back([
        _finding(text="acme still ships developer tools", evidence=None,
                 evidence_id=evidence_id, entities=["other"],
                 subject_slug="acme", context_type="identity", reusable=True),
    ])
    assert len(ok["promoted"]) + len(ok["merged"]) == 1
    assert ok["evidence"] == [evidence_id]

    # A dangling reference (no such file) is treated as no evidence -> brief-only.
    dangling = memory.write_back([
        _finding(text="unbacked claim", evidence=None,
                 evidence_id="ev_000000000000000000000000", reusable=True),
    ])
    assert dangling["promoted"] == []
    assert len(dangling["brief_only"]) == 1


# --- §5.1 Layer-1 dossiers / §5.2 Layer-2 briefs -----------------------------

def test_write_back_materializes_world_dossier(store: ContextStore, memory: ContextMemory):
    result = memory.write_back([
        _finding(text="acme is a plg dev tools company", entities=["acme"],
                 context_type="identity", subject_slug="acme", reusable=True),
    ])
    assert result["dossiers"], "a promoted chunk must create its Layer-1 dossier"
    dossier = memory.subjects_dir / "acme.md"
    assert dossier.is_file()
    body = dossier.read_text(encoding="utf-8")
    assert "plg dev tools" in body
    assert "<!-- chunk:" in body  # section-indexed by chunk id


def test_write_back_self_dossier_scoped_by_persona(store: ContextStore, memory: ContextMemory):
    memory.write_back([
        _finding(text="we rebuilt onboarding and conversion doubled", scope="self",
                 persona="shubham", subject_slug="onboarding-rebuild",
                 context_type="relational", source_type="persona_history", reusable=True),
    ])
    assert (memory.self_dir / "shubham" / "onboarding-rebuild.md").is_file()
    # world subjects dir must not hold the self dossier.
    assert not (memory.subjects_dir / "onboarding-rebuild.md").exists()


def test_dossier_merge_updates_section_in_place(store: ContextStore, memory: ContextMemory):
    memory.write_back([
        _finding(text="acme switched to usage based pricing", entities=["acme"],
                 subject_slug="acme", confidence="medium", reusable=True),
    ])
    memory.write_back([
        _finding(text="acme switched to usage based pricing", entities=["acme"],
                 subject_slug="acme", confidence="high", reusable=True),
    ])
    body = (memory.subjects_dir / "acme.md").read_text(encoding="utf-8")
    # merged into one chunk section, not appended twice.
    assert body.count("<!-- chunk:") == 1


def test_write_back_writes_layer2_brief_with_reply_id(store: ContextStore, memory: ContextMemory):
    result = memory.write_back(
        [
            _finding(text="acme is a plg dev tools company", subject_slug="acme",
                     context_type="identity", reusable=True),
            _finding(text="one-off detail for this tweet only", reusable=False),
        ],
        reply_id="r-123",
        gaps=[{"context_type": "identity", "entity": "acme", "why_needed": "place the handle"}],
        queries=["acme.com what does it do"],
        shaped_draft="led with acme's PLG positioning instead of a generic caveat",
    )
    assert result["brief"], "reply_id must produce a Layer-2 brief"
    brief = memory.briefs_dir / "r-123.md"
    assert brief.is_file()
    text = brief.read_text(encoding="utf-8")
    assert "reply_id: r-123" in text
    assert "acme" in text
    assert "promoted" in text and "brief_only" in text  # promotion decisions recorded
    assert "generic caveat" in text  # shaped-draft line


def test_write_back_without_reply_id_writes_no_brief(store: ContextStore, memory: ContextMemory):
    result = memory.write_back([_finding(subject_slug="acme", reusable=True)])
    assert result["brief"] == []
    assert list(memory.briefs_dir.glob("*.md")) == []


# --- §5.5.1 reflection --------------------------------------------------------

def test_reflect_synthesizes_insight_chunk(store: ContextStore, memory: ContextMemory):
    for i in range(3):
        store.add(
            f"acme detail number {i} shipped feature",
            {"scope": "world", "context_type": "factual", "importance": 0.6,
             "entities": ["acme"], "subject_slug": "acme",
             "created_at": NOW.isoformat(), "last_refreshed": NOW.isoformat(),
             "chunk_id": f"raw{i}"},
        )
    insight = memory.reflect("world", subject="acme")
    assert insight is not None
    assert insight["context_type"] == "insight"
    assert insight["source_type"] == "reflection"
    assert insight["importance"] >= 0.8
    assert "raw0" in insight["provenance"]

    # It is retrievable and does not itself get re-consolidated.
    def _insight_count() -> int:
        return sum(
            1 for h in store.search("", k=200, filters={"scope": "world"})
            if h.get("context_type") == "insight"
        )

    assert _insight_count() == 1
    again = memory.reflect("world", subject="acme")
    assert "insight" not in (again["provenance"] if again else "")
    # Repeated reflect dedups/merges into the one insight — no unbounded growth.
    assert _insight_count() == 1


# --- §5.4 style exemplars (diversity, NOT topical) ---------------------------

def test_style_exemplars_selected_for_register_not_topic(store: ContextStore, memory: ContextMemory):
    """Plan 08 fix 14: exemplars are chosen for stylistic spread (length/register),
    NOT for spanning different topics. All chunks here share ONE subject, so any
    diversity that shows up is purely stylistic — a terse one-liner vs a long
    formal sentence — proving the selector is register-driven, not topic-driven."""
    texts = {
        "terse": "shipped it.",
        "longform": ("We spent the entire quarter methodically rebuilding the onboarding "
                     "funnel and the resulting conversion improvement exceeded every single "
                     "projection that we had modeled going into the work."),
        "question": "why does developer onboarding still feel so clunky?",
        "midstatement": "we rebuilt onboarding and conversion roughly doubled overall.",
    }
    for cid, text in texts.items():
        store.add(text, {"scope": "self", "persona": "p", "subject_slug": "onboarding",
                         "context_type": "relational", "importance": 0.5,
                         "created_at": NOW.isoformat(), "last_refreshed": NOW.isoformat(),
                         "chunk_id": cid})

    exemplars = memory.style_exemplars("p", k=2)
    ids = {e["chunk_id"] for e in exemplars}
    # The most stylistically distant pair — the terse quip and the long sentence —
    # even though every chunk is about the SAME topic (onboarding).
    assert ids == {"terse", "longform"}
    lengths = [len(e["text"]) for e in exemplars]
    assert max(lengths) - min(lengths) > 80  # a real register/length spread


def test_style_exemplars_filter_by_persona(store: ContextStore, memory: ContextMemory):
    store.add("persona a tweet", {"scope": "self", "persona": "a", "subject_slug": "x",
              "importance": 0.5, "created_at": NOW.isoformat(),
              "last_refreshed": NOW.isoformat(), "chunk_id": "a1"})
    store.add("persona b tweet", {"scope": "self", "persona": "b", "subject_slug": "y",
              "importance": 0.5, "created_at": NOW.isoformat(),
              "last_refreshed": NOW.isoformat(), "chunk_id": "b1"})
    exemplars = memory.style_exemplars("a", k=5)
    assert [e["chunk_id"] for e in exemplars] == ["a1"]


# --- Plan 08 fix 4: persona isolation on content-read AND dedup ---------------

def test_retrieve_content_self_isolated_by_persona(store: ContextStore, memory: ContextMemory):
    """scope=self content retrieval only ever returns the asked-for persona's own
    memory — never another persona's self chunk on a shared entity."""
    for persona, cid in (("alice", "alice1"), ("bob", "bob1")):
        store.add(
            f"{persona} rebuilt onboarding and doubled conversion",
            {"scope": "self", "persona": persona, "subject_slug": "onboarding",
             "context_type": "relational", "importance": 0.6, "entities": ["onboarding"],
             "created_at": NOW.isoformat(), "last_refreshed": NOW.isoformat(),
             "chunk_id": cid},
        )
    alice_hits = memory.retrieve_content("onboarding conversion", scope="self",
                                         persona="alice", k=8)
    assert alice_hits
    assert {h["chunk_id"] for h in alice_hits} == {"alice1"}
    assert all(h["persona"] == "alice" for h in alice_hits)

    bob_hits = memory.retrieve_content("onboarding conversion", scope="self",
                                       persona="bob", k=8)
    assert {h["chunk_id"] for h in bob_hits} == {"bob1"}


def test_self_dedup_isolated_by_persona(store: ContextStore, memory: ContextMemory):
    """Two personas writing the identical self-fact must NOT merge into one shared
    chunk/dossier — each persona keeps its own copy (dedup identity is per-persona)."""
    shared = dict(text="we rebuilt onboarding and conversion doubled", scope="self",
                  subject_slug="onboarding", context_type="relational",
                  source_type="persona_history", entities=["onboarding"], reusable=True)
    memory.write_back([_finding(persona="alice", **shared)])
    result = memory.write_back([_finding(persona="bob", **shared)])

    # Bob's identical self-fact promotes fresh instead of merging into alice's.
    assert len(result["promoted"]) == 1
    assert result["merged"] == []
    assert len(list(store.chunks_dir.glob("*.md"))) == 2
    # Each persona owns a separate self dossier; neither leaks into the other.
    assert (memory.self_dir / "alice" / "onboarding.md").is_file()
    assert (memory.self_dir / "bob" / "onboarding.md").is_file()

    # By contrast, the SAME persona re-writing the fact DOES merge (isolation is
    # per-persona, not a blanket dedup disable).
    again = memory.write_back([_finding(persona="alice", **shared)])
    assert len(again["merged"]) == 1
    assert len(list(store.chunks_dir.glob("*.md"))) == 2


# --- Plan 08 fix 8: hybrid (dense + lexical) retrieval ------------------------

def test_hybrid_retrieval_exact_token_beats_semantic_distractor(tmp_path: Path):
    """An exact error-code match must beat a topically-closer semantic distractor.

    With a semantic embedder the distractor (same topic, no code) is the nearest
    DENSE neighbor; only the fused lexical path surfaces the chunk that actually
    holds the literal ``ERR-4021`` the query asked for."""
    store = ContextStore(tmp_path / "data" / "context", embedder=SemanticEmbedder())
    memory = ContextMemory(store, now=NOW)

    store.add(
        "resolved ERR-4021 in billing",
        {"scope": "world", "context_type": "factual", "importance": 0.5,
         "entities": ["err-4021"], "subject_slug": "incident",
         "created_at": NOW.isoformat(), "last_refreshed": NOW.isoformat(),
         "chunk_id": "target"},
    )
    store.add(
        "the outage postmortem retrospective",
        {"scope": "world", "context_type": "factual", "importance": 0.5,
         "entities": ["outage"], "subject_slug": "incident",
         "created_at": NOW.isoformat(), "last_refreshed": NOW.isoformat(),
         "chunk_id": "distractor"},
    )

    query = "downtime ERR-4021"
    # Dense alone favors the semantic distractor (shares the 'downtime'/'outage' axis).
    dense = store.search(query, k=8, filters={"scope": "world"})
    assert dense[0]["chunk_id"] == "distractor"
    # A pure lexical read finds the exact code only in the target.
    lexical = store.search_lexical(query, k=8, filters={"scope": "world"})
    assert [h["chunk_id"] for h in lexical] == ["target"]
    # Hybrid retrieval fuses them and the exact-token chunk wins.
    ranked = memory.retrieve_content(query, scope="world", k=8)
    assert ranked[0]["chunk_id"] == "target"


# --- Plan 08 fix 7: dedup contradiction + empty-entity ------------------------

def test_dedup_contradiction_keeps_higher_confidence_with_supersession(store: ContextStore):
    """Conflicting claims about the same subject collapse to ONE chunk: the
    higher-confidence text survives and the loser is recorded as superseded in the
    provenance chain (never silently dropped)."""
    memory = ContextMemory(store, now=NOW, dedup_threshold=0.5)
    memory.write_back([
        _finding(text="acme has 50 employees", entities=["acme"], subject_slug="acme",
                 confidence="low", reusable=True),
    ])
    result = memory.write_back([
        _finding(text="acme has 200 employees", entities=["acme"], subject_slug="acme",
                 confidence="high", reusable=True),
    ])
    assert len(result["merged"]) == 1
    assert len(list(store.chunks_dir.glob("*.md"))) == 1

    hits = store.search("acme employees headcount", k=5)
    top = hits[0]
    assert "200 employees" in top["text"]        # higher-confidence text wins
    assert "superseded" in top["provenance"]      # contradiction recorded
    assert "50 employees" in top["provenance"]    # the loser is retained, not erased


def test_dedup_no_merge_on_empty_entity_overlap(store: ContextStore):
    """Two findings with identical text and subject but NO named entities must not
    merge — without a shared entity we cannot assert they are the same fact."""
    memory = ContextMemory(store, now=NOW, dedup_threshold=0.5)
    shared = dict(text="usage based pricing is becoming the default", subject_slug="pricing",
                  entities=[], confidence="high", reusable=True)
    memory.write_back([_finding(**shared)])
    result = memory.write_back([_finding(**shared)])

    assert len(result["promoted"]) == 1
    assert result["merged"] == []
    assert len(list(store.chunks_dir.glob("*.md"))) == 2
