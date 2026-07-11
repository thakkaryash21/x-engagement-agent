"""Plan 07 §5.4 — ContextStore: the swappable retrieval substrate.

These tests exercise the substrate ONLY (add/search round-trip, scope filter,
reindex rebuild-from-files). Ranking/dedup/promotion policy is tested in
test_context_memory.py — the store must hold none of it. Everything runs against
a temp data/context dir with the injected FakeEmbedder, never the real data/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dashboard.context_store import ContextStore


def _meta(**over):
    base = {
        "scope": "world",
        "source_type": "web_search",
        "context_type": "identity",
        "confidence": "high",
        "importance": 0.7,
        "entities": ["acme"],
        "created_at": "2026-07-01T00:00:00",
        "last_refreshed": "2026-07-01T00:00:00",
        "provenance": "https://acme.com about",
        "evidence_id": "ev_1",
        "subject_slug": "acme",
        "persona": "",
    }
    base.update(over)
    return base


@pytest.fixture
def store(tmp_path: Path, fake_embedder) -> ContextStore:
    return ContextStore(tmp_path / "data" / "context", embedder=fake_embedder)


def test_add_search_round_trip(store: ContextStore):
    chunk_id = store.add("Acme is a PLG developer tools company", _meta())
    assert chunk_id

    hits = store.search("Acme developer tools company", k=5)
    assert hits, "expected a candidate for a matching query"
    top = hits[0]
    assert top["chunk_id"] == chunk_id
    assert top["text"] == "Acme is a PLG developer tools company"
    assert top["scope"] == "world"
    assert top["context_type"] == "identity"
    assert top["entities"] == ["acme"]  # list round-trips through the JSON column
    assert 0.0 < top["relevance"] <= 1.0
    # The substrate returns similarity only — no policy score keys.
    assert "score" not in top


def test_add_writes_authoritative_chunk_file(store: ContextStore):
    chunk_id = store.add("a durable fact", _meta())
    files = list(store.chunks_dir.glob("*.md"))
    assert [p.stem for p in files] == [chunk_id]
    body = files[0].read_text(encoding="utf-8")
    assert "a durable fact" in body
    assert '"acme"' in body  # entities serialized in frontmatter


def test_add_is_upsert_on_chunk_id(store: ContextStore):
    store.add("first version", _meta(chunk_id="fixed"))
    store.add("second version", _meta(chunk_id="fixed"))
    hits = store.search("version", k=10)
    ids = [h["chunk_id"] for h in hits]
    assert ids.count("fixed") == 1
    assert next(h for h in hits if h["chunk_id"] == "fixed")["text"] == "second version"
    assert len(list(store.chunks_dir.glob("*.md"))) == 1


def test_search_scope_filter(store: ContextStore):
    store.add("world subject fact about launch", _meta(chunk_id="w", scope="world"))
    store.add(
        "self experience about launch",
        _meta(chunk_id="s", scope="self", persona="p", subject_slug="launch"),
    )
    world_hits = store.search("launch", k=10, filters={"scope": "world"})
    assert world_hits and all(h["scope"] == "world" for h in world_hits)
    self_hits = store.search("launch", k=10, filters={"scope": "self"})
    assert self_hits and all(h["scope"] == "self" for h in self_hits)


def test_search_generic_metadata_filter(store: ContextStore):
    """The substrate applies only generic exact-metadata filters (SoC, fix 6)."""
    store.add("acme identity fact", _meta(chunk_id="id", context_type="identity"))
    store.add("acme cultural take", _meta(chunk_id="cu", context_type="cultural"))
    hits = store.search("acme", k=10, filters={"context_type": "cultural"})
    assert hits and all(h["context_type"] == "cultural" for h in hits)


def test_store_owns_no_gap_routing(store: ContextStore):
    """The substrate must not carry the gap_type->context_type acquisition map."""
    import dashboard.context_store as mod

    assert not hasattr(mod, "_GAP_TO_CONTEXT")
    # search takes generic `filters`, not a `gap_type` acquisition arg.
    import inspect

    assert "gap_type" not in inspect.signature(store.search).parameters
    assert "filters" in inspect.signature(store.search).parameters


def test_search_empty_store_returns_empty(store: ContextStore):
    assert store.search("anything", k=5) == []


def test_search_lexical_matches_exact_tokens(store: ContextStore):
    """The lexical path retrieves an exact literal token (fix 8)."""
    store.add("incident ERR-4021 root cause", _meta(chunk_id="hit", entities=["err-4021"]))
    store.add("unrelated pricing discussion", _meta(chunk_id="miss", entities=["pricing"]))
    hits = store.search_lexical("ERR-4021", k=5)
    assert [h["chunk_id"] for h in hits] == ["hit"]
    # Respects the same generic metadata filters as dense search.
    assert store.search_lexical("ERR-4021", k=5, filters={"scope": "self"}) == []
    # A query with no lexical tokens yields nothing (never crashes).
    assert store.search_lexical("", k=5) == []


def test_reindex_rebuilds_from_files(tmp_path: Path, fake_embedder):
    context_dir = tmp_path / "data" / "context"
    store = ContextStore(context_dir, embedder=fake_embedder)
    store.add("chunk one about pricing", _meta(chunk_id="c1", entities=["pricing"]))
    store.add("chunk two about hiring", _meta(chunk_id="c2", entities=["hiring"]))
    store.add("chunk three about launch", _meta(chunk_id="c3", entities=["launch"]))

    # Blow away the derived index entirely; the chunk .md files are the truth.
    import shutil

    shutil.rmtree(store.index_dir)
    rebuilt = ContextStore(context_dir, embedder=fake_embedder)
    assert rebuilt.search("pricing", k=5) == []  # nothing indexed yet

    count = rebuilt.reindex()
    assert count == 3
    hits = rebuilt.search("pricing", k=5)
    assert any(h["chunk_id"] == "c1" for h in hits)
    assert {p.stem for p in rebuilt.chunks_dir.glob("*.md")} == {"c1", "c2", "c3"}


def test_reindex_skips_and_reports_bad_files_and_swaps_on_success(tmp_path: Path, fake_embedder):
    """Plan 08 fix 9: a corrupt chunk file is skipped + reported (not fatal), the
    good chunks still reindex, and the live table is swapped only after the temp
    build validated."""
    context_dir = tmp_path / "data" / "context"
    store = ContextStore(context_dir, embedder=fake_embedder)
    store.add("good chunk about pricing", _meta(chunk_id="good", entities=["pricing"]))

    # A malformed chunk file with no frontmatter — must not abort the rebuild.
    (store.chunks_dir / "broken.md").write_text("no frontmatter here\n", encoding="utf-8")

    count = store.reindex()
    assert count == 1  # only the good chunk was staged + swapped in
    assert [s["file"] for s in store.reindex_skipped] == ["broken.md"]
    hits = store.search("pricing", k=5)
    assert {h["chunk_id"] for h in hits} == {"good"}


def test_add_rejects_unsafe_chunk_id(store: ContextStore):
    """Injection hardening (fix 15): a traversal-y chunk_id is refused, never written."""
    with pytest.raises(ValueError):
        store.add("evil", _meta(chunk_id="../../etc/passwd"))
