"""Plan 07 §5.4/§5.5/§5.5.1/§5.7 — ContextMemory: the stable policy layer.

Tests the policy that must survive a substrate swap: the
score = a·relevance + b·recency + c·importance blend, dedup/merge on write,
the promotion gate, reflection, evidence preservation, and diversity-selected
style exemplars. Runs against a temp data/context dir with the FakeEmbedder;
never touches the real data/.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from dashboard.context_memory import ContextMemory
from dashboard.context_store import ContextStore

NOW = dt.datetime(2026, 7, 10, 12, 0, 0)


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


def test_promotion_gate_heuristic_without_explicit_flag(store: ContextStore, memory: ContextMemory):
    # No explicit `reusable`: durable identity at high importance promotes;
    # ephemeral temporal at low importance stays brief-only.
    result = memory.write_back([
        _finding(text="acme founder background", context_type="identity", importance=0.8),
        _finding(text="passing meme about loops", context_type="temporal", importance=0.2,
                 entities=["loops"]),
    ])
    assert len(result["promoted"]) == 1
    assert len(result["brief_only"]) == 1


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
            1 for h in store.search("", k=200, scope="world")
            if h.get("context_type") == "insight"
        )

    assert _insight_count() == 1
    again = memory.reflect("world", subject="acme")
    assert "insight" not in (again["provenance"] if again else "")
    # Repeated reflect dedups/merges into the one insight — no unbounded growth.
    assert _insight_count() == 1


# --- §5.4 style exemplars (diversity, NOT topical) ---------------------------

def test_style_exemplars_are_diverse_not_topic_clustered(store: ContextStore, memory: ContextMemory):
    # Two distinct topic clusters of the persona's own tweets.
    for i in range(3):
        store.add(
            f"pricing pricing plans tier billing example {i}",
            {"scope": "self", "persona": "p", "subject_slug": "pricing",
             "context_type": "relational", "importance": 0.5,
             "created_at": NOW.isoformat(), "last_refreshed": NOW.isoformat(),
             "chunk_id": f"price{i}"},
        )
    for i in range(3):
        store.add(
            f"hiring team culture trial project example {i}",
            {"scope": "self", "persona": "p", "subject_slug": "hiring",
             "context_type": "relational", "importance": 0.5,
             "created_at": NOW.isoformat(), "last_refreshed": NOW.isoformat(),
             "chunk_id": f"hire{i}"},
        )

    exemplars = memory.style_exemplars("p", k=2)
    assert len(exemplars) == 2
    slugs = {e["subject_slug"] for e in exemplars}
    # Diversity objective spans both clusters rather than clustering on one topic.
    assert slugs == {"pricing", "hiring"}


def test_style_exemplars_filter_by_persona(store: ContextStore, memory: ContextMemory):
    store.add("persona a tweet", {"scope": "self", "persona": "a", "subject_slug": "x",
              "importance": 0.5, "created_at": NOW.isoformat(),
              "last_refreshed": NOW.isoformat(), "chunk_id": "a1"})
    store.add("persona b tweet", {"scope": "self", "persona": "b", "subject_slug": "y",
              "importance": 0.5, "created_at": NOW.isoformat(),
              "last_refreshed": NOW.isoformat(), "chunk_id": "b1"})
    exemplars = memory.style_exemplars("a", k=5)
    assert [e["chunk_id"] for e in exemplars] == ["a1"]
