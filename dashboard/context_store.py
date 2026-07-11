"""ContextStore — the SWAPPABLE retrieval substrate (Plan 07 §5.4).

This is the *only* file that changes when LanceDB+fastembed is swapped for
mem0 / Supermemory / a stronger embedder. It owns nothing but the substrate:
embed a chunk, upsert it, and return raw similarity candidates. It deliberately
holds **no policy** — no score blend, no dedup/merge, no promotion gate, no
reflection. All of that lives one layer up in ``context_memory.ContextMemory``
(§5.4 seam split; SRP).

Storage model (constraint 6 — files are authoritative, the index is derived):

- ``data/context/chunks/<chunk_id>.md`` is the authoritative record for one
  chunk: a JSON-per-line frontmatter block (the §5.5 metadata schema) followed
  by the distilled chunk text. ``add`` writes this file, then upserts the
  LanceDB row. ``reindex`` drops the vector table and rebuilds it purely from
  these files, so the index at ``data/context/index/`` is a disposable
  accelerator — delete it and ``reindex`` reconstructs it.

The embedder is **injectable** (constructor arg): tests pass a deterministic,
offline fake; runtime falls back to ``FastEmbedEmbedder`` (bundled ONNX model,
no network at call time). fastembed downloads a model on first use, so injection
is what keeps the test suite offline.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Protocol, Sequence

import pyarrow as pa

# --- The §5.5 chunk metadata schema (single source: the plan; mirrored here) ---
#
# Every stored chunk carries these fields. ``ContextStore`` persists them; it
# does not interpret ``importance``/``created_at`` (that is policy, §5.4).
META_FIELDS: tuple[str, ...] = (
    "scope",  # world | self  (retrieval filter, §5.0)
    "source_type",  # x_navigation | x_search | web_search | dossier | persona_history | persona_file | reflection
    "context_type",  # identity | factual | temporal | cultural | relational | insight
    "confidence",  # high(primary) | medium | low
    "importance",  # float 0..1 — durability/significance (§5.4 score term)
    "entities",  # list[str] — named things this chunk is about
    "created_at",  # ISO8601 — drives recency decay
    "last_refreshed",  # ISO8601 — bumped on dedup/merge
    "provenance",  # handle/URL + the query that found it
    "evidence_id",  # link to the immutable raw snapshot (§5.7)
    "subject_slug",  # which dossier it belongs to
    "persona",  # owning persona for scope=self chunks ("" for world)
)

# LanceDB columns that mirror META_FIELDS but flatten list/float types for Arrow.
_STRING_COLUMNS: tuple[str, ...] = (
    "chunk_id",
    "text",
    "scope",
    "source_type",
    "context_type",
    "confidence",
    "entities",  # stored as a JSON string; parsed back to list on read
    "created_at",
    "last_refreshed",
    "provenance",
    "evidence_id",
    "subject_slug",
    "persona",
)


class Embedder(Protocol):
    """The injectable embedding seam.

    ``dim`` is the fixed vector width; ``embed`` maps a batch of texts to a
    batch of vectors. Any object satisfying this protocol works — the runtime
    ``FastEmbedEmbedder`` and the tests' fake both do.
    """

    @property
    def dim(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """Runtime embedder: fastembed's bundled ONNX model, loaded lazily.

    The model is only constructed on first ``embed`` call so importing this
    module (or constructing a store with an injected fake) never triggers the
    one-time model download.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", dim: int = 384) -> None:
        self._model_name = model_name
        self._dim = dim
        self._model = None

    @property
    def dim(self) -> int:
        return self._dim

    def _ensure(self) -> None:
        if self._model is None:
            from fastembed import TextEmbedding  # imported lazily; downloads on first use

            self._model = TextEmbedding(model_name=self._model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self._ensure()
        assert self._model is not None
        return [vector.tolist() for vector in self._model.embed(list(texts))]


def _frontmatter_dump(meta: dict[str, Any]) -> str:
    """Serialize meta as one ``key: <json-value>`` line per field (list/float safe)."""
    lines = ["---"]
    for key in ("chunk_id", *META_FIELDS):
        lines.append(f"{key}: {json.dumps(meta.get(key))}")
    lines.append("---")
    return "\n".join(lines)


def _frontmatter_load(raw: str) -> tuple[dict[str, Any], str]:
    """Inverse of ``_frontmatter_dump`` — return (meta, body_text)."""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("chunk file missing frontmatter")
    meta: dict[str, Any] = {}
    idx = 1
    while idx < len(lines) and lines[idx].strip() != "---":
        line = lines[idx]
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = json.loads(value.strip())
        idx += 1
    body = "\n".join(lines[idx + 1 :]).strip("\n")
    return meta, body


class ContextStore:
    """The swappable substrate: ``add`` / ``search`` / ``reindex`` only."""

    def __init__(
        self,
        context_dir: str | Path,
        embedder: Embedder | None = None,
        table_name: str = "chunks",
    ) -> None:
        self.context_dir = Path(context_dir).resolve()
        self.chunks_dir = self.context_dir / "chunks"
        self.index_dir = self.context_dir / "index"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        # embedder is INJECTABLE: tests pass a deterministic fake; runtime uses fastembed.
        self.embedder: Embedder = embedder if embedder is not None else FastEmbedEmbedder()
        self.table_name = table_name
        self._db = None
        self._table = None

    # --- LanceDB lifecycle (lazy; the table is created on first write) ---------

    def _connect(self):
        if self._db is None:
            import lancedb

            self._db = lancedb.connect(str(self.index_dir))
        return self._db

    def _schema(self) -> pa.Schema:
        fields = [pa.field("vector", pa.list_(pa.float32(), self.embedder.dim))]
        for name in _STRING_COLUMNS:
            fields.append(pa.field(name, pa.string()))
        fields.append(pa.field("importance", pa.float32()))
        return pa.schema(fields)

    def _open_table(self, create: bool = False):
        db = self._connect()
        if self.table_name in db.table_names():
            self._table = db.open_table(self.table_name)
        elif create:
            self._table = db.create_table(self.table_name, schema=self._schema())
        else:
            self._table = None
        return self._table

    def _row(self, chunk_id: str, text: str, meta: dict[str, Any]) -> dict[str, Any]:
        vector = self.embedder.embed([text])[0]
        row: dict[str, Any] = {"vector": vector, "chunk_id": chunk_id, "text": text}
        for name in _STRING_COLUMNS:
            if name in ("chunk_id", "text"):
                continue
            if name == "entities":
                row["entities"] = json.dumps(meta.get("entities") or [])
            else:
                value = meta.get(name)
                row[name] = "" if value is None else str(value)
        importance = meta.get("importance")
        row["importance"] = float(importance) if importance is not None else 0.0
        return row

    # --- Public substrate API --------------------------------------------------

    def add(self, chunk_text: str, meta: dict[str, Any]) -> str:
        """Low-level upsert of one chunk. Returns its ``chunk_id``.

        Writes the authoritative chunk markdown file first, then upserts the
        LanceDB row (files-first, so a crash between them is healed by
        ``reindex``). No policy here: ``meta`` is stored as given.
        """
        chunk_id = str(meta.get("chunk_id") or uuid.uuid4().hex)
        full_meta = {key: meta.get(key) for key in META_FIELDS}
        full_meta["chunk_id"] = chunk_id

        # 1) Authoritative file.
        path = self.chunks_dir / f"{chunk_id}.md"
        path.write_text(
            _frontmatter_dump(full_meta) + "\n" + chunk_text.strip() + "\n",
            encoding="utf-8",
        )

        # 2) Derived index (upsert = delete-then-add on chunk_id).
        table = self._open_table(create=True)
        assert table is not None
        table.delete(f"chunk_id = '{chunk_id}'")
        table.add([self._row(chunk_id, chunk_text, full_meta)])
        return chunk_id

    def search(
        self,
        query: str,
        k: int = 20,
        scope: str | None = None,
        gap_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw candidate chunks by vector similarity — NO ranking policy.

        Applies only substrate-level filtering: a ``scope`` equality filter
        (``world`` / ``self``; ``both``/``None`` = no filter) and an optional
        soft ``gap_type``→``context_type`` narrowing. Each candidate carries a
        ``relevance`` in [0,1] derived from the vector distance; the *policy*
        blend (relevance × recency × importance, MMR) lives in ContextMemory.
        """
        table = self._open_table(create=False)
        if table is None:
            return []
        vector = self.embedder.embed([query or ""])[0]
        builder = table.search(vector).limit(max(k, 1) * 4)

        clauses: list[str] = []
        if scope in ("world", "self"):
            clauses.append(f"scope = '{scope}'")
        ctx = _GAP_TO_CONTEXT.get((gap_type or "").lower())
        if ctx:
            clauses.append(f"context_type = '{ctx}'")
        if clauses:
            builder = builder.where(" AND ".join(clauses))

        rows = builder.to_list()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(self._hydrate(row))
        return out[: max(k, 1) * 4]

    def reindex(self) -> int:
        """Drop and rebuild the vector table from the chunk markdown files.

        The files under ``data/context/chunks/`` are authoritative; the LanceDB
        table is a pure derivative. Returns the number of chunks reindexed.
        """
        db = self._connect()
        if self.table_name in db.table_names():
            db.drop_table(self.table_name)
        self._table = None

        rows: list[dict[str, Any]] = []
        for path in sorted(self.chunks_dir.glob("*.md")):
            meta, body = _frontmatter_load(path.read_text(encoding="utf-8"))
            chunk_id = str(meta.get("chunk_id") or path.stem)
            meta["chunk_id"] = chunk_id
            rows.append(self._row(chunk_id, body, meta))

        table = db.create_table(self.table_name, schema=self._schema())
        self._table = table
        if rows:
            table.add(rows)
        return len(rows)

    # --- Helpers ---------------------------------------------------------------

    def _hydrate(self, row: dict[str, Any]) -> dict[str, Any]:
        """Turn a raw LanceDB row into a candidate chunk dict."""
        distance = float(row.get("_distance", 0.0))
        chunk: dict[str, Any] = {
            "chunk_id": row.get("chunk_id", ""),
            "text": row.get("text", ""),
            "importance": float(row.get("importance", 0.0)),
            "relevance": 1.0 / (1.0 + distance),
            "_distance": distance,
        }
        for name in _STRING_COLUMNS:
            if name in ("chunk_id", "text", "entities"):
                continue
            chunk[name] = row.get(name, "")
        raw_entities = row.get("entities", "") or "[]"
        try:
            chunk["entities"] = json.loads(raw_entities)
        except (ValueError, TypeError):
            chunk["entities"] = []
        return chunk


# gap_type (Layer-3 vocabulary, §5.3) → context_type (§3.0.1) soft narrowing.
# Only applied when a mapping exists; "none"/"mixed"/unknown = no narrowing.
_GAP_TO_CONTEXT: dict[str, str] = {
    "discourse": "cultural",
    "cultural": "cultural",
    "factual": "factual",
    "identity": "identity",
    "temporal": "temporal",
    "relational": "relational",
}
