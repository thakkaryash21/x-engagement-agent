"""End-to-end integration gate for the context subsystem (Plan 08 fix 1).

The earlier build passed every per-component unit test yet did not wire together
at runtime — nothing constructed ``ContextMemory``, and two of three storage
layers were never materialized. This test closes that gap by driving a
*mode-shaped call path* through the real CLI bridge (``dashboard.context_cli``)
as a subprocess, exactly as ``modes/scroll.md`` §2.4b invokes it:

    write-back a finding (with reply_id)  ->  assert chunk + evidence + Layer-1
    dossier + Layer-2 brief were all created  ->  search retrieves it.

It runs offline via ``--embedder hash`` (no fastembed download).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(context_dir: Path, command: str, payload: dict | None = None,
         *extra: str) -> dict | list:
    """Invoke the CLI as a subprocess (the real mode-shaped call path)."""
    argv = [
        sys.executable, "-m", "dashboard.context_cli", command,
        "--context-dir", str(context_dir),
        "--embedder", "hash",
        *extra,
    ]
    proc = subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        input=json.dumps(payload or {}),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"CLI failed: {proc.stderr}\n{proc.stdout}"
    return json.loads(proc.stdout)


@pytest.fixture
def context_dir(tmp_path: Path) -> Path:
    return tmp_path / "data" / "context"


def test_write_back_then_search_through_cli(context_dir: Path):
    """The full mode call path: enrich -> persist all layers -> retrieve."""
    finding = {
        "text": "acme is a plg developer tools company on usage based pricing",
        "scope": "world",
        "source_type": "web_search",
        "context_type": "identity",
        "confidence": "high",
        "importance": 0.8,
        "entities": ["acme"],
        "subject_slug": "acme",
        "provenance": "https://acme.com/about",
        "evidence": "RAW: acme.com about page — Acme builds developer tools, usage-based pricing.",
        "reusable": True,
    }

    # 1) write-back exactly as scroll.md §2.4b stage 6 does (reply_id threaded).
    result = _run(context_dir, "write-back", {
        "findings": [finding],
        "reply_id": "reply-001",
        "gaps": [{"context_type": "identity", "entity": "acme", "why_needed": "place the handle"}],
        "queries": ["acme.com what does it do"],
        "shaped_draft": "led with acme's PLG positioning, not a generic caveat",
    })
    assert isinstance(result, dict)
    assert len(result["promoted"]) == 1
    assert len(result["evidence"]) == 1
    assert len(result["dossiers"]) == 1
    assert len(result["brief"]) == 1

    # 2) all three durable homes were materialized on disk.
    chunk_files = list((context_dir / "chunks").glob("*.md"))
    assert len(chunk_files) == 1, "flat chunk index"
    assert list((context_dir / "evidence").glob("*.md")), "immutable evidence (§5.7)"
    dossier = context_dir / "subjects" / "acme.md"
    assert dossier.is_file(), "Layer-1 world dossier (§5.1)"
    assert "developer tools" in dossier.read_text(encoding="utf-8")
    brief = context_dir / "briefs" / "reply-001.md"
    assert brief.is_file(), "Layer-2 per-draft brief (§5.2)"
    brief_text = brief.read_text(encoding="utf-8")
    assert "reply_id: reply-001" in brief_text
    assert "generic caveat" in brief_text  # shaped-draft recorded

    # evidence id in the brief matches the preserved evidence file.
    evidence_id = result["evidence"][0]
    assert (context_dir / "evidence" / f"{evidence_id}.md").is_file()
    assert evidence_id in brief_text

    # 3) search retrieves what write-back promoted (the round trip closes).
    hits = _run(context_dir, "search", {"query": "acme developer tools pricing", "scope": "world"})
    assert isinstance(hits, list) and hits, "search must retrieve the promoted chunk"
    assert any("acme" in (h.get("entities") or []) for h in hits)
    top = hits[0]
    assert "score" in top  # policy-ranked read (retrieve_content), not raw substrate


def test_reindex_rebuilds_index_through_cli(context_dir: Path):
    """reindex reconstructs the derived index from authoritative chunk files."""
    _run(context_dir, "write-back", {
        "findings": [{
            "text": "acme shipped v3 this quarter",
            "scope": "world", "context_type": "factual", "confidence": "high",
            "importance": 0.7, "entities": ["acme"], "subject_slug": "acme",
            "evidence": "RAW: acme changelog — v3 shipped this quarter.",
            "reusable": True,
        }],
    })
    import shutil

    shutil.rmtree(context_dir / "index")  # blow away the derived accelerator
    out = _run(context_dir, "reindex")
    assert out["reindexed"] == 1
    hits = _run(context_dir, "search", {"query": "acme v3", "scope": "world"})
    assert hits, "reindex must restore retrievability from the chunk files"
