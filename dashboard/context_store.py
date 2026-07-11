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
import re
import uuid
from pathlib import Path
from typing import Any, Protocol, Sequence

import pyarrow as pa

# A chunk_id becomes a filename (``chunks/<id>.md``) and a LanceDB predicate
# literal, so it must be a safe, traversal-free token (Plan 08 fix 15). Ids we
# generate (uuid4 hex) and the ids tests pass all satisfy this; anything else is
# rejected at the substrate boundary rather than silently written.
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


def _is_safe_id(value: str) -> bool:
    return bool(_SAFE_ID_RE.fullmatch(value or ""))


def _tokenize(text: str) -> list[str]:
    """Lexical tokens for the keyword/FTS path — alphanumeric runs, lowercased."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())

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


class HashEmbedder:
    """Deterministic, offline embedder — a bag-of-words hash, zero dependencies.

    Not a quality embedder; it exists so the CLI bridge and the end-to-end test
    can run fully hermetic (no fastembed model download, no network) while still
    giving shared-token texts high cosine similarity. Runtime uses
    ``FastEmbedEmbedder``; ``--embedder hash`` on the CLI selects this one.
    """

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import math
        import re
        import zlib

        out: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self._dim
            for token in re.findall(r"[a-z0-9]+", (text or "").lower()):
                vector[zlib.crc32(token.encode()) % self._dim] += 1.0
            norm = math.sqrt(sum(component * component for component in vector))
            if norm:
                vector = [component / norm for component in vector]
            out.append(vector)
        return out


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
        # Full-text (lexical) index lifecycle (Plan 08 fix 8 — hybrid retrieval).
        # LanceDB's FTS index is not auto-maintained on ``add``, so we mark it
        # dirty on every write and (re)build it lazily on the next lexical read.
        self._fts_dirty = True
        self._fts_ready = False
        # Records skipped by the last ``reindex`` (bad/unsafe chunk files),
        # surfaced to the caller instead of silently dropped (Plan 08 fix 9).
        self.reindex_skipped: list[dict[str, str]] = []

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
        # Injection hardening (Plan 08 fix 15): the id is a filename + a predicate
        # literal, so reject anything that is not a safe, traversal-free token.
        if not _is_safe_id(chunk_id):
            raise ValueError(f"unsafe chunk_id: {chunk_id!r}")
        full_meta = {key: meta.get(key) for key in META_FIELDS}
        full_meta["chunk_id"] = chunk_id

        # 1) Authoritative file — resolved and confirmed under the chunks root.
        path = (self.chunks_dir / f"{chunk_id}.md").resolve()
        if self.chunks_dir.resolve() not in path.parents:
            raise ValueError(f"chunk path escapes its root: {path}")
        path.write_text(
            _frontmatter_dump(full_meta) + "\n" + chunk_text.strip() + "\n",
            encoding="utf-8",
        )

        # 2) Derived index (upsert = delete-then-add on chunk_id).
        table = self._open_table(create=True)
        assert table is not None
        table.delete(f"chunk_id = '{chunk_id}'")
        table.add([self._row(chunk_id, chunk_text, full_meta)])
        self._fts_dirty = True  # the FTS index no longer reflects the table
        return chunk_id

    def search(
        self,
        query: str,
        k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw candidate chunks by vector similarity — NO ranking policy.

        Applies only substrate-level filtering: ``filters`` is a generic
        exact-metadata map (``{column: value}``, e.g. ``{"scope": "world"}``)
        over the stored string columns. The substrate does NOT interpret any
        acquisition vocabulary — no ``gap_type``, no ``scope`` special-casing.
        That mapping (``gap_type``→``context_type``, scope blends) is policy and
        lives in ``ContextMemory``. Each candidate carries a ``relevance`` in
        [0,1] from the vector distance; the policy blend (relevance × recency ×
        importance, MMR) lives one layer up.
        """
        table = self._open_table(create=False)
        if table is None:
            return []
        vector = self.embedder.embed([query or ""])[0]
        builder = table.search(vector).limit(max(k, 1) * 4)

        clauses = self._filter_clauses(filters)
        if clauses:
            builder = builder.where(" AND ".join(clauses))

        rows = builder.to_list()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(self._hydrate(row))
        return out[: max(k, 1) * 4]

    def search_lexical(
        self,
        query: str,
        k: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return candidates by full-text/keyword match — the lexical retrieval path.

        This is the exact-token complement to dense ``search`` (Plan 08 fix 8):
        a dense semantic embedder can miss a literal handle, date, or error code,
        so hybrid retrieval fuses this lexical path with the dense one *before*
        any policy ranking. Results are ordered by the substrate's BM25 score; the
        policy layer fuses + ranks them. Returns ``[]`` when the query has no
        lexical tokens or the table is empty/unindexed.
        """
        table = self._open_table(create=False)
        if table is None:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        self._ensure_fts_index()
        if not self._fts_ready:
            return []
        # Sanitize: pass only the plain tokens so FTS query operators in the raw
        # string are never interpreted (Plan 08 fix 15).
        fts_query = " ".join(tokens)
        builder = table.search(fts_query, query_type="fts").limit(max(k, 1) * 4)
        clauses = self._filter_clauses(filters)
        if clauses:
            builder = builder.where(" AND ".join(clauses))
        try:
            rows = builder.to_list()
        except Exception:
            return []
        return [self._hydrate(row) for row in rows][: max(k, 1) * 4]

    def _filter_clauses(self, filters: dict[str, Any] | None) -> list[str]:
        """Generic exact-metadata predicates over known string columns (SoC).

        Only ``{column: value}`` over ``_STRING_COLUMNS`` is honored, and every
        literal is quote-escaped so a value can never break out of the predicate
        (Plan 08 fix 15).
        """
        clauses: list[str] = []
        for column, value in (filters or {}).items():
            if column not in _STRING_COLUMNS:
                continue
            safe = str(value).replace("'", "''")
            clauses.append(f"{column} = '{safe}'")
        return clauses

    def _ensure_fts_index(self) -> None:
        """(Re)build the FTS index over ``text`` if the table changed since last build."""
        table = self._table
        if table is None or not self._fts_dirty:
            return
        if table.count_rows() == 0:
            self._fts_ready = False
            return
        table.create_fts_index("text", replace=True, use_tantivy=False)
        self._fts_dirty = False
        self._fts_ready = True

    def reindex(self) -> int:
        """Rebuild the vector table from the chunk markdown files — atomically.

        The files under ``data/context/chunks/`` are authoritative; the LanceDB
        table is a pure derivative. Rather than drop-then-rebuild (which leaves the
        live table missing if the rebuild fails), this validates every record into
        a **temporary** table first and only swaps the live table once that build
        succeeds (Plan 08 fix 9). Unreadable/unsafe chunk files are skipped and
        reported via ``self.reindex_skipped`` instead of aborting the whole rebuild.
        Returns the number of chunks reindexed.
        """
        db = self._connect()
        rows: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for path in sorted(self.chunks_dir.glob("*.md")):
            try:
                meta, body = _frontmatter_load(path.read_text(encoding="utf-8"))
                chunk_id = str(meta.get("chunk_id") or path.stem)
                if not _is_safe_id(chunk_id):
                    raise ValueError(f"unsafe chunk_id {chunk_id!r}")
                meta["chunk_id"] = chunk_id
                rows.append(self._row(chunk_id, body, meta))
            except Exception as exc:  # noqa: BLE001 — one bad file must not fail the rest
                skipped.append({"file": path.name, "error": str(exc)})

        # 1) Build + validate a temp table FIRST; the live table is untouched so
        #    far, so any failure here leaves the existing index intact.
        tmp_name = f"{self.table_name}__reindex_tmp"
        if tmp_name in db.table_names():
            db.drop_table(tmp_name)
        tmp = db.create_table(tmp_name, schema=self._schema())
        if rows:
            tmp.add(rows)
        if tmp.count_rows() != len(rows):
            db.drop_table(tmp_name)
            raise RuntimeError(
                f"reindex validation failed: staged {tmp.count_rows()} of {len(rows)} rows"
            )

        # 2) Swap: only now, with a validated build in hand, replace the live table.
        if self.table_name in db.table_names():
            db.drop_table(self.table_name)
        table = db.create_table(self.table_name, schema=self._schema())
        if rows:
            table.add(rows)
        db.drop_table(tmp_name)

        self._table = table
        self._fts_dirty = True
        self.reindex_skipped = skipped
        return len(rows)

    # --- Helpers ---------------------------------------------------------------

    def _hydrate(self, row: dict[str, Any]) -> dict[str, Any]:  # noqa: D401
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
