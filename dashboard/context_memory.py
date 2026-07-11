"""ContextMemory — the STABLE policy layer over ContextStore (Plan 07 §5.4).

This layer is preserved across substrate swaps. Everything that is *policy*
lives here and never leaks into the substrate:

- ``write_back`` (§5.5): distill -> dedup/merge -> promotion gate -> store.add,
  and preserve raw evidence immutably to ``data/context/evidence/`` (§5.7).
- ``reflect`` (§5.5.1): the INTERIM consolidation pass — concatenate a cluster of
  raw chunks into one labeled ``insight`` chunk and store it (run by
  ``learn``/``review``, not the hot path). This is a simple concatenating
  consolidation, NOT real synthesis; true synthesis (an abstraction beyond the
  union of the source texts) is deferred (roadmap).
- ``retrieve_content`` (§5.4): the CONTENT read — ``store.search`` then the
  ``score = a·relevance + b·recency_decay + c·importance`` blend + MMR.
- ``style_exemplars`` (§5.4): the STYLE read — the persona's own chunks selected
  for stylistic **diversity/coverage**, explicitly NOT topical similarity.

Callers (scroll 2.4b, learn, review) talk to ContextMemory; ContextMemory talks
to ContextStore. The score blend, dedup/merge, promotion gate, and reflection
are HERE — never in the store.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from typing import Any, Sequence

from dashboard.context_store import ContextStore, _is_safe_id

# Context types the promotion gate treats as durable/reusable knowledge when the
# agent gives no explicit ``reusable`` verdict (§5.5 stage 3 heuristic fallback).
_DURABLE_CONTEXT_TYPES = frozenset({"identity", "factual", "cultural", "relational", "insight"})

# gap_type (the Layer-3 acquisition vocabulary, §5.3) → context_type (§3.0.1).
# This is ACQUISITION POLICY and belongs here, NOT in the substrate (SoC, Plan 08
# fix 6). ``ContextStore`` takes only generic exact-metadata filters; ContextMemory
# is what knows a "discourse" gap means ``context_type=cultural``.
_GAP_TO_CONTEXT: dict[str, str] = {
    "discourse": "cultural",
    "cultural": "cultural",
    "factual": "factual",
    "identity": "identity",
    "temporal": "temporal",
    "relational": "relational",
}


def _safe_slug(value: str) -> str:
    """Sanitize a slug/id for use as a filename — no traversal, ASCII-safe."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "misc"


def _as_utc(value: dt.datetime) -> dt.datetime:
    """Coerce a datetime to UTC-aware; a naive value is assumed to already be UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _to_utc_iso(value: Any, fallback_iso: str) -> str:
    """Normalize a timestamp to a UTC-aware ISO string at ingestion (Plan 08 fix 16).

    Missing -> ``fallback_iso`` (a just-captured finding is "now"). Unparseable ->
    ``""`` so the read-side recency decay treats it as stale rather than freshest.
    """
    if value in (None, ""):
        return fallback_iso
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return ""
    return _as_utc(parsed).isoformat()


# Content-addressed evidence ids (Plan 08 fix 5): the id is a stable function of
# the raw captured bytes, so identical evidence collapses to one immutable record
# and any id can be re-verified against its file's content. ``ev_`` + 24 lowercase
# hex chars is also a safe, traversal-free filename.
_EVIDENCE_ID_RE = re.compile(r"ev_[0-9a-f]{24}")


def _content_address(raw: str) -> str:
    """Derive a content-addressed evidence id from the raw source bytes."""
    digest = hashlib.sha256((raw or "").strip().encode("utf-8")).hexdigest()
    return f"ev_{digest[:24]}"


def _valid_evidence_id(evidence_id: str) -> bool:
    """True iff ``evidence_id`` is a well-formed content-addressed id."""
    return bool(_EVIDENCE_ID_RE.fullmatch(evidence_id or ""))


class ContextMemory:
    def __init__(
        self,
        store: ContextStore,
        *,
        weights: tuple[float, float, float] = (0.55, 0.15, 0.30),
        recency_half_life_days: float = 14.0,
        dedup_threshold: float = 0.88,
        importance_promote_threshold: float = 0.5,
        sighting_promote_threshold: int = 2,
        mmr_lambda: float = 0.7,
        now: dt.datetime | None = None,
    ) -> None:
        self.store = store
        # score = a·relevance + b·recency_decay + c·importance
        self.a, self.b, self.c = weights
        self.recency_half_life_days = recency_half_life_days
        self.dedup_threshold = dedup_threshold
        self.importance_promote_threshold = importance_promote_threshold
        # Promotion without an explicit reusability verdict needs the subject to
        # have been sighted at least this many times (Plan 08 fix 10 — no
        # promote-on-first-sight, which pollutes memory with one-off noise).
        self.sighting_promote_threshold = sighting_promote_threshold
        self.mmr_lambda = mmr_lambda
        self._now = now
        # The three durable homes materialized on write-back (§5.1/§5.2/§5.7):
        self.evidence_dir = store.context_dir / "evidence"  # Layer 0 immutable raw source
        self.subjects_dir = store.context_dir / "subjects"  # Layer 1 world dossiers
        self.self_dir = store.context_dir / "self"  # Layer 1 self dossiers (per persona)
        self.briefs_dir = store.context_dir / "briefs"  # Layer 2 per-draft briefs
        for directory in (self.evidence_dir, self.subjects_dir, self.self_dir, self.briefs_dir):
            directory.mkdir(parents=True, exist_ok=True)
        # Persistent per-subject sighting counts (fix 10) — survives across CLI
        # invocations so "seen twice" holds across separate mode runs.
        self.sightings_path = store.context_dir / "sightings.json"

    def now(self) -> dt.datetime:
        return self._now or dt.datetime.now()

    def _now_utc_iso(self) -> str:
        """The current instant as a UTC-aware ISO string (ingestion timestamps)."""
        return _as_utc(self.now()).isoformat()

    # --- Acquisition-policy filter construction (SoC — Plan 08 fix 6) ----------

    def _filters(
        self,
        scope: str | None = None,
        gap_type: str | None = None,
        persona: str | None = None,
    ) -> dict[str, str]:
        """Translate acquisition vocabulary (scope, gap_type, persona) → substrate filters.

        The substrate only understands exact ``{column: value}`` filters; this is
        where the ``gap_type``→``context_type`` mapping and the scope filter live.

        Persona isolation (Plan 08 fix 4): ``scope=self`` memory is owned per
        persona and must never be read or merged across personas, so a persona
        clause is added for self reads/dedup. World memory is shared, so persona
        never narrows it.
        """
        filters: dict[str, str] = {}
        if scope in ("world", "self"):
            filters["scope"] = scope
        if scope == "self" and persona:
            filters["persona"] = str(persona)
        ctx = _GAP_TO_CONTEXT.get((gap_type or "").lower())
        if ctx:
            filters["context_type"] = ctx
        return filters

    # --- §5.5 unified write-back ----------------------------------------------

    def write_back(
        self,
        findings: Sequence[dict[str, Any]],
        reply_id: str | None = None,
        *,
        gaps: Sequence[Any] | None = None,
        queries: Sequence[Any] | None = None,
        shaped_draft: str | None = None,
    ) -> dict[str, list[str]]:
        """Distill -> evidence -> promotion gate -> dedup/merge -> store + dossier;
        and, when ``reply_id`` is given, a per-draft brief (§5.2).

        ``findings`` are raw acquisition results, each a dict with at least
        ``text`` plus §5.5 meta fields, and optionally ``evidence`` (raw source
        text) and an explicit ``reusable`` verdict. Every promoted/merged chunk
        also creates/merges its Layer-1 dossier section (§5.1) — the chunk is the
        index, the dossier is the human-editable home. Returns a summary:
        ``{promoted, merged, brief_only, evidence, dossiers, brief}``.
        """
        result: dict[str, list[str]] = {
            "promoted": [], "merged": [], "brief_only": [],
            "evidence": [], "dossiers": [], "brief": [],
        }
        decisions: list[dict[str, Any]] = []  # per-finding record for the Layer-2 brief

        for finding in findings:
            chunk = self._distill(finding)

            # §5.7 — preserve the raw source immutably; the chunk indexes it.
            # ``evidence_id`` is "" when no real captured source exists; the
            # promotion gate (fix 5) then keeps such a finding brief-only.
            evidence_id = self._preserve_evidence(finding, chunk)
            chunk["evidence_id"] = evidence_id
            if evidence_id:
                result["evidence"].append(evidence_id)

            decision: dict[str, Any] = {
                "text": chunk["text"],
                "scope": chunk["scope"],
                "subject_slug": chunk["subject_slug"],
                "provenance": chunk["provenance"],
                "evidence_id": evidence_id,
            }

            # Every finding is one sighting of its subject; record it before the
            # gate so an implicit-promotion decision can require repeated sightings.
            sightings = self._bump_sighting(chunk)

            # §5.5 stage 3 — persist-vs-ephemeral promotion gate.
            if not self._is_reusable(finding, chunk, sightings):
                result["brief_only"].append(chunk.get("chunk_id") or "")
                decision["promotion"] = "brief_only"
                decisions.append(decision)
                continue

            # §5.5 stage 2 — dedup/merge before write.
            merged = self._dedup_merge(chunk)
            if merged is not None:
                # Use the SURVIVING merged chunk (winning text/confidence + full
                # provenance chain) as the durable chunk from here on, so the
                # Layer-1 dossier below reflects the winner — not this raw incoming
                # chunk, which on a lower-confidence contradiction is the loser.
                chunk = merged
                result["merged"].append(chunk["chunk_id"])
                decision["promotion"] = "merged"
                decision["chunk_id"] = chunk["chunk_id"]
            else:
                chunk_id = self.store.add(chunk["text"], chunk)
                chunk["chunk_id"] = chunk_id
                result["promoted"].append(chunk_id)
                decision["promotion"] = "promoted"
                decision["chunk_id"] = chunk_id

            # §5.1 — the durable chunk gets a home in its Layer-1 dossier.
            dossier_path = self._upsert_dossier(chunk)
            result["dossiers"].append(str(dossier_path))
            decision["dossier"] = str(dossier_path)
            decisions.append(decision)

        # §5.2 — the per-draft brief: complete provenance for THIS reply.
        if reply_id:
            brief_path = self._write_brief(
                reply_id, gaps or [], queries or [], decisions, shaped_draft, result
            )
            result["brief"].append(str(brief_path))

        return result

    # --- §5.1 Layer-1 dossiers / §5.2 Layer-2 briefs --------------------------

    def _dossier_path(self, chunk: dict[str, Any]) -> Path:
        """Resolve the dossier file for a chunk, kept strictly under its root."""
        slug = _safe_slug(chunk.get("subject_slug") or "")
        if (chunk.get("scope") or "world") == "self":
            persona = _safe_slug(chunk.get("persona") or "unknown")
            path = (self.self_dir / persona / f"{slug}.md").resolve()
            root = self.self_dir.resolve()
        else:
            path = (self.subjects_dir / f"{slug}.md").resolve()
            root = self.subjects_dir.resolve()
        if root not in path.parents:  # traversal guard
            raise ValueError(f"dossier path escapes its root: {path}")
        return path

    def _upsert_dossier(self, chunk: dict[str, Any]) -> Path:
        """Create or merge the Layer-1 dossier section for one durable chunk.

        Dossiers are the human-editable home; each chunk owns a section marked by
        ``<!-- chunk:<id> -->`` so re-writing the same chunk updates its section
        in place rather than appending a duplicate.
        """
        path = self._dossier_path(chunk)
        path.parent.mkdir(parents=True, exist_ok=True)
        now_iso = self.now().isoformat()
        slug = _safe_slug(chunk.get("subject_slug") or "")
        scope = chunk.get("scope") or "world"
        persona = chunk.get("persona") or ""
        chunk_id = str(chunk.get("chunk_id") or "")

        first_seen = now_iso
        sections: dict[str, str] = {}
        order: list[str] = []
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            meta = re.search(r"^first_seen:\s*(.+)$", raw, re.MULTILINE)
            if meta:
                first_seen = meta.group(1).strip()
            for match in re.finditer(
                r"<!-- chunk:(?P<id>[^\s>]+) -->\n(?P<body>.*?)\n<!-- /chunk:(?P=id) -->",
                raw,
                re.DOTALL,
            ):
                cid = match.group("id")
                if cid not in sections:
                    order.append(cid)
                sections[cid] = match.group("body")

        block = (
            f"## {chunk.get('context_type', 'note')} — {chunk.get('confidence', '')}\n"
            f"{chunk.get('text', '').strip()}\n\n"
            f"_source: {chunk.get('provenance', '')} | evidence: {chunk.get('evidence_id', '')}_"
        )
        if chunk_id not in sections:
            order.append(chunk_id)
        sections[chunk_id] = block

        lines = [
            "---",
            f"slug: {slug}",
            f"scope: {scope}",
            f"persona: {persona}",
            f"display_name: {chunk.get('subject_slug') or slug}",
            f"first_seen: {first_seen}",
            f"last_refreshed: {now_iso}",
            "---",
            "",
            f"# {chunk.get('subject_slug') or slug}",
            "",
        ]
        for cid in order:
            lines.append(f"<!-- chunk:{cid} -->")
            lines.append(sections[cid])
            lines.append(f"<!-- /chunk:{cid} -->")
            lines.append("")
        path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
        return path

    def _write_brief(
        self,
        reply_id: str,
        gaps: Sequence[Any],
        queries: Sequence[Any],
        decisions: Sequence[dict[str, Any]],
        shaped_draft: str | None,
        result: dict[str, list[str]],
    ) -> Path:
        """Write the Layer-2 per-draft brief (§5.2), keyed to ``reply_id``."""
        path = (self.briefs_dir / f"{_safe_slug(reply_id)}.md").resolve()
        if self.briefs_dir.resolve() not in path.parents:
            raise ValueError(f"brief path escapes its root: {path}")

        def _fmt(item: Any) -> str:
            return item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)

        lines = [
            "---",
            f"reply_id: {reply_id}",
            f"written_at: {self.now().isoformat()}",
            "---",
            "",
            f"# Context brief — {reply_id}",
            "",
            "## Gaps",
        ]
        lines += [f"- {_fmt(g)}" for g in gaps] or ["- (none)"]
        lines += ["", "## Queries issued"]
        lines += [f"- {_fmt(q)}" for q in queries] or ["- (none)"]
        lines += ["", "## Findings & promotion decisions"]
        if decisions:
            for decision in decisions:
                lines.append(
                    f"- [{decision.get('promotion', '')}] ({decision.get('scope', '')}) "
                    f"{decision.get('text', '').strip()}"
                )
                lines.append(
                    f"  - evidence: {decision.get('evidence_id', '')} | "
                    f"chunk: {decision.get('chunk_id', '-')} | "
                    f"subject: {decision.get('subject_slug', '')} | "
                    f"source: {decision.get('provenance', '')}"
                )
        else:
            lines.append("- (none)")
        lines += ["", "## Evidence ids"]
        lines += [f"- {eid}" for eid in result.get("evidence", [])] or ["- (none)"]
        lines += ["", "## Promotion summary"]
        lines.append(
            f"- promoted: {len(result.get('promoted', []))} | "
            f"merged: {len(result.get('merged', []))} | "
            f"brief_only: {len(result.get('brief_only', []))}"
        )
        lines += ["", "## Shaped draft", shaped_draft or "(not recorded)"]
        path.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
        return path

    # --- §5.5.1 reflection / consolidation ------------------------------------

    def reflect(self, scope: str, subject: str | None = None) -> dict[str, Any] | None:
        """Consolidate a cluster of raw chunks into one labeled ``insight`` and store it.

        Reads (via ``store.search``) the chunks for ``scope`` (optionally a
        single ``subject`` slug) and writes back one ``insight`` chunk through
        ``store.add`` with high importance and provenance = the source chunk ids.
        Returns the insight chunk (or ``None`` if there is nothing to consolidate).

        INTERIM behaviour (Plan 08 Decisions): the ``insight`` text is a simple
        labeled concatenation of the source texts — a consolidation, not real
        synthesis. It does NOT distill an abstraction that the raw chunks do not
        already state; genuine synthesis is a deferred roadmap feature. The chunk
        is honestly labeled ``context_type=insight`` / ``source_type=reflection``
        so a reader can tell interim consolidation apart from the future pass.
        """
        candidates = self.store.search(subject or "", k=100, filters=self._filters(scope))
        # A reflection consolidates *raw* material, not prior insights.
        sources = [
            chunk
            for chunk in candidates
            if chunk.get("context_type") != "insight"
            and (subject is None or chunk.get("subject_slug") == subject)
        ]
        if not sources:
            return None

        source_ids = [chunk["chunk_id"] for chunk in sources]
        entities: list[str] = []
        for chunk in sources:
            for entity in chunk.get("entities") or []:
                if entity not in entities:
                    entities.append(entity)

        label = subject or scope
        # INTERIM consolidation (Plan 08): a labeled *concatenation* of the source
        # texts — deliberately NOT synthesis. Genuine synthesis (an abstraction
        # beyond the union of these texts) is a deferred roadmap feature; see
        # docs/roadmap.md -> Deferred. Named `consolidated`, not `synthesis`, so
        # the code does not overclaim what this pass does.
        consolidated = f"Consolidated insight ({scope}/{label}): " + " ".join(
            chunk["text"].strip() for chunk in sources
        )
        insight = {
            "chunk_id": uuid.uuid4().hex,
            "text": consolidated,
            "scope": scope,
            "source_type": "reflection",
            "context_type": "insight",
            "confidence": "high",
            "importance": max(
                0.8, max((float(chunk.get("importance", 0.0)) for chunk in sources), default=0.0)
            ),
            "entities": entities,
            "created_at": self.now().isoformat(),
            "last_refreshed": self.now().isoformat(),
            "provenance": "reflection over: " + ",".join(source_ids),
            "evidence_id": "",
            "subject_slug": subject or "",
            "persona": sources[0].get("persona", ""),
        }
        # §5.5.1 — reflections flow through the SAME dedup/merge as write-back so
        # repeated consolidation (learn/review run this every batch) merges into
        # the one insight instead of appending an identical duplicate each time.
        merged = self._dedup_merge(insight)
        if merged is not None:
            return merged
        insight["chunk_id"] = self.store.add(insight["text"], insight)
        return insight

    # --- §5.4 CONTENT retrieval ------------------------------------------------

    def retrieve_content(
        self,
        query: str,
        scope: str | None = None,
        gap_type: str | None = None,
        k: int = 8,
        persona: str | None = None,
    ) -> list[dict[str, Any]]:
        """The content read: score = a·relevance + b·recency + c·importance, + MMR.

        Calls ``store.search`` for raw candidates, applies the three-term blend
        (so a durable high-importance chunk can beat a fresher low-importance one
        at similar relevance), then MMR-diversifies the top set.

        ``persona`` scopes ``scope=self`` reads to that persona (Plan 08 fix 4) so
        one persona never retrieves another's self memory; it is ignored for world.

        Retrieval is HYBRID (Plan 08 fix 8): a dense (semantic) candidate set and a
        lexical (exact-token) candidate set are fused by reciprocal-rank fusion
        BEFORE the policy blend, so a literal handle/date/error-code the dense
        embedder would miss still surfaces its chunk.
        """
        filters = self._filters(scope, gap_type, persona)
        limit = max(k, 1) * 4
        dense = self.store.search(query, k=limit, filters=filters)
        lexical = self.store.search_lexical(query, k=limit, filters=filters)
        candidates = self._fuse(dense, lexical)
        if not candidates:
            return []

        now = self.now()
        for chunk in candidates:
            relevance = float(chunk.get("relevance", 0.0))
            recency = self._recency_decay(chunk.get("created_at"), now)
            importance = float(chunk.get("importance", 0.0))
            chunk["recency"] = recency
            chunk["score"] = self.a * relevance + self.b * recency + self.c * importance

        candidates.sort(key=lambda chunk: chunk["score"], reverse=True)
        return self._mmr(candidates, k, relevance_key="score", diversity_lambda=self.mmr_lambda)

    def _fuse(
        self,
        dense: list[dict[str, Any]],
        lexical: list[dict[str, Any]],
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """Reciprocal-rank fusion of the dense and lexical candidate lists (fix 8).

        Each list contributes ``1/(rrf_k + rank)`` to a chunk's fused score; the
        combined score is normalized into ``relevance`` in [0,1] so the downstream
        blend (relevance × recency × importance) consumes one unified relevance.
        A chunk that ranks highly on EITHER path is pulled up — that is what lets
        an exact-token lexical hit beat a dense-only semantic distractor.
        """
        scores: dict[str, float] = {}
        chosen: dict[str, dict[str, Any]] = {}
        for ranked in (dense, lexical):
            for rank, chunk in enumerate(ranked):
                cid = chunk.get("chunk_id") or ""
                if not cid:
                    continue
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
                chosen.setdefault(cid, chunk)
        if not scores:
            return []
        top = max(scores.values())
        fused: list[dict[str, Any]] = []
        for cid, chunk in chosen.items():
            chunk["relevance"] = scores[cid] / top if top else 0.0
            fused.append(chunk)
        return fused

    # --- §5.4 STYLE-exemplar retrieval ----------------------------------------

    def style_exemplars(self, persona: str, k: int = 5) -> list[dict[str, Any]]:
        """The persona's own chunks, selected for stylistic *register* coverage.

        Style imitation degrades when exemplars are picked by topic (Plan 08 fix
        14): what matters for voice is stylistic variety — sentence length,
        question vs statement, punctuation energy, casing — NOT that the examples
        span different subjects. So this scores each ``scope=self`` chunk on
        register/length features (deliberately topic-agnostic) and greedily picks
        the most stylistically spread-out set (max-min distance in feature space).
        """
        pool = self.store.search("", k=200, filters={"scope": "self"})
        pool = [chunk for chunk in pool if not persona or chunk.get("persona") == persona]
        if not pool:
            return []
        features = [_style_features(chunk.get("text", "")) for chunk in pool]
        return self._maxmin_select(pool, features, k)

    def _maxmin_select(
        self,
        pool: list[dict[str, Any]],
        features: list[list[float]],
        k: int,
    ) -> list[dict[str, Any]]:
        """Greedy max-min diversity over a feature space (farthest-point sampling).

        Seeds with the most stylistically "extreme" item (largest feature norm),
        then repeatedly adds the item whose nearest already-selected item is
        farthest — spreading the picks across the register range.
        """
        k = min(k, len(pool))
        if k <= 0:
            return []
        seed = max(range(len(pool)), key=lambda i: sum(v * v for v in features[i]))
        selected = [seed]
        while len(selected) < k:
            best_idx, best_gap = None, -math.inf
            for idx in range(len(pool)):
                if idx in selected:
                    continue
                gap = min(_euclidean(features[idx], features[s]) for s in selected)
                if gap > best_gap:
                    best_gap, best_idx = gap, idx
            if best_idx is None:
                break
            selected.append(best_idx)
        return [pool[i] for i in selected]

    # --- Internals -------------------------------------------------------------

    def _distill(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw finding into a single well-formed chunk (§5.5 stage 1)."""
        now_iso = self._now_utc_iso()
        importance = finding.get("importance")
        # Injection hardening (fix 15): a caller-supplied chunk_id becomes a
        # filename and a predicate literal downstream — accept it only if it is a
        # safe token, otherwise mint a fresh uuid.
        supplied_id = str(finding.get("chunk_id") or "")
        chunk_id = supplied_id if _is_safe_id(supplied_id) else uuid.uuid4().hex
        chunk = {
            "chunk_id": chunk_id,
            "text": (finding.get("text") or "").strip(),
            "scope": finding.get("scope") or "world",
            "source_type": finding.get("source_type") or "web_search",
            "context_type": finding.get("context_type") or "factual",
            "confidence": finding.get("confidence") or "medium",
            "importance": float(importance) if importance is not None else 0.5,
            "entities": list(finding.get("entities") or []),
            # Timestamps normalized to UTC-aware at ingestion (fix 16).
            "created_at": _to_utc_iso(finding.get("created_at"), now_iso),
            "last_refreshed": _to_utc_iso(finding.get("last_refreshed"), now_iso),
            "provenance": finding.get("provenance") or "",
            "evidence_id": finding.get("evidence_id") or "",
            "subject_slug": finding.get("subject_slug") or "",
            "persona": finding.get("persona") or "",
        }
        return chunk

    def _preserve_evidence(self, finding: dict[str, Any], chunk: dict[str, Any]) -> str:
        """Write/reference the immutable raw-source record (§5.7); return its id or "".

        Evidence integrity (Plan 08 fix 5): the model-distilled chunk ``text`` may
        NEVER become its own evidence. An id is returned only when the finding
        carries real captured raw source, or references an already-preserved,
        valid record. The id is content-addressed from the raw bytes so identical
        evidence collapses to one immutable file and the id is verifiable. When
        there is neither, "" is returned and the promotion gate keeps the finding
        brief-only.
        """
        raw = (finding.get("evidence") or "").strip()
        if raw:
            evidence_id = _content_address(raw)
            path = self.evidence_dir / f"{evidence_id}.md"
            if not path.exists():  # append-only + content-addressed: write once
                header = [
                    "---",
                    f"evidence_id: {evidence_id}",
                    f"captured_at: {self.now().isoformat()}",
                    f"adapter: {chunk['source_type']}",
                    f"source: {chunk['provenance']}",
                    f"scope: {chunk['scope']}",
                    "---",
                ]
                path.write_text("\n".join(header) + "\n" + raw + "\n", encoding="utf-8")
            return evidence_id

        # No fresh raw source: accept ONLY a reference to an existing, valid record
        # (e.g. re-verification refreshing memory from preserved evidence). A
        # dangling or malformed reference is treated as no evidence.
        ref = (finding.get("evidence_id") or chunk.get("evidence_id") or "").strip()
        if ref and _valid_evidence_id(ref) and (self.evidence_dir / f"{ref}.md").exists():
            return ref
        return ""

    def _is_reusable(
        self, finding: dict[str, Any], chunk: dict[str, Any], sightings: int
    ) -> bool:
        """Promotion gate (§5.5 stage 3): does this chunk deserve durable memory?

        Hard precondition (Plan 08 fix 5): a durable / draft-usable fact must
        trace to captured raw evidence (or a verified existing record). Without an
        ``evidence_id`` the finding stays brief-only regardless of any ``reusable``
        verdict — the distilled text can never be its own justification.

        Given evidence, an explicit agent verdict wins. Absent an explicit verdict
        we do NOT promote on first sight (Plan 08 fix 10 — that pollutes memory
        with one-off noise): a durable ``context_type`` at/above the importance
        threshold promotes only once its subject has been sighted at least
        ``sighting_promote_threshold`` times.
        """
        if not chunk.get("evidence_id"):
            return False
        explicit = finding.get("reusable")
        if explicit is not None:
            return bool(explicit)
        if chunk["context_type"] not in _DURABLE_CONTEXT_TYPES:
            return False
        if chunk["importance"] < self.importance_promote_threshold:
            return False
        return sightings >= self.sighting_promote_threshold

    def _sighting_key(self, chunk: dict[str, Any]) -> str:
        """Stable per-subject key for sighting counts (scope/persona/subject)."""
        scope = chunk.get("scope") or "world"
        persona = (chunk.get("persona") or "") if scope == "self" else ""
        subject = chunk.get("subject_slug") or ",".join(
            sorted(entity.lower() for entity in chunk.get("entities") or [])
        )
        return f"{scope}|{persona}|{subject or '_'}"

    def _bump_sighting(self, chunk: dict[str, Any]) -> int:
        """Increment and persist this subject's sighting count; return the new count."""
        key = self._sighting_key(chunk)
        data: dict[str, int] = {}
        if self.sightings_path.exists():
            try:
                data = json.loads(self.sightings_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                data = {}
        count = int(data.get(key, 0)) + 1
        data[key] = count
        self.sightings_path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        return count

    def _dedup_merge(self, chunk: dict[str, Any]) -> dict[str, Any] | None:
        """Merge into a near-duplicate existing chunk if one exists (§5.5 stage 2).

        Returns the merged SURVIVING chunk when a merge happened, else ``None``
        (caller then adds it fresh). The caller must upsert the Layer-1 dossier
        from this returned chunk — never from the raw incoming chunk — so the
        dossier shows the surviving (winning) text/confidence, not a superseded
        contradiction loser. Identity is DETERMINISTIC (Plan 08 fix 7): a candidate
        is the same subject only when scope, persona and subject_slug all match AND
        the entity sets overlap — a high vector relevance alone is not enough, and
        an empty entity overlap never merges (too uncertain). On a real match the
        surviving text is the higher-confidence one (ties break to the more
        recent); a differing text is treated as a contradiction/update — the loser
        is superseded with a dated note and the full provenance/evidence chain is
        retained rather than dropped.
        """
        # Persona isolation (Plan 08 fix 4): a self chunk only ever dedups against
        # its OWN persona's memory, so two personas' identical self-facts stay
        # distinct instead of collapsing into one cross-persona chunk.
        existing = self.store.search(
            chunk["text"],
            k=5,
            filters=self._filters(chunk["scope"], persona=chunk.get("persona")),
        )
        new_entities = {entity.lower() for entity in chunk.get("entities") or []}
        for candidate in existing:
            if candidate.get("relevance", 0.0) < self.dedup_threshold:
                continue
            # Deterministic identity keys must all agree.
            if (candidate.get("scope") or "world") != (chunk.get("scope") or "world"):
                continue
            if (candidate.get("persona") or "") != (chunk.get("persona") or ""):
                continue
            if (candidate.get("subject_slug") or "") != (chunk.get("subject_slug") or ""):
                continue
            cand_entities = {entity.lower() for entity in candidate.get("entities") or []}
            # No merge on empty-entity overlap (fix 7): without a shared named
            # entity we cannot assert these are the same fact.
            if not (new_entities & cand_entities):
                continue

            merged = self._merge_chunks(candidate, chunk)
            self.store.add(merged["text"], merged)
            return merged
        return None

    def _merge_chunks(
        self, candidate: dict[str, Any], incoming: dict[str, Any]
    ) -> dict[str, Any]:
        """Combine an incoming chunk into an existing one, keeping every chain (fix 7)."""
        merged = dict(candidate)
        merged["chunk_id"] = candidate["chunk_id"]
        merged["last_refreshed"] = self._now_utc_iso()
        merged["importance"] = max(
            float(candidate.get("importance", 0.0)), float(incoming.get("importance", 0.0))
        )

        # union entities
        union: list[str] = list(candidate.get("entities") or [])
        for entity in incoming.get("entities") or []:
            if entity not in union:
                union.append(entity)
        merged["entities"] = union

        # Surviving text: higher confidence wins; a tie breaks to the more recent.
        cand_rank = _confidence_rank(candidate.get("confidence", ""))
        inc_rank = _confidence_rank(incoming.get("confidence", ""))
        take_incoming = inc_rank > cand_rank or (
            inc_rank == cand_rank
            and _iso_key(incoming.get("created_at")) >= _iso_key(candidate.get("created_at"))
        )
        texts_differ = _normtext(candidate.get("text", "")) != _normtext(incoming.get("text", ""))
        if take_incoming:
            merged["text"] = incoming["text"]
            merged["confidence"] = incoming["confidence"]
            merged["context_type"] = incoming.get("context_type") or candidate.get("context_type", "")
            if incoming.get("created_at"):
                merged["created_at"] = incoming["created_at"]
            if incoming.get("evidence_id"):
                merged["evidence_id"] = incoming["evidence_id"]

        # Provenance chain (fix 7): retain BOTH sources — never let a setdefault
        # drop the incoming provenance — and, on a contradiction, a supersession
        # note so the losing claim is recorded as superseded, not silently erased.
        chain: list[str] = []
        for part in (candidate.get("provenance", ""), incoming.get("provenance", "")):
            part = (part or "").strip()
            if part and part not in chain:
                chain.append(part)
        if texts_differ:
            superseded = candidate["text"] if take_incoming else incoming["text"]
            chain.append(f"superseded@{merged['last_refreshed']}: {superseded.strip()}")
        # Retain a differing evidence id from the loser so the chain is complete.
        loser_evidence = (candidate if take_incoming else incoming).get("evidence_id", "")
        if loser_evidence and loser_evidence != merged.get("evidence_id"):
            chain.append(f"evidence:{loser_evidence}")
        merged["provenance"] = " | ".join(chain)
        return merged

    def _recency_decay(self, created_at: Any, now: dt.datetime) -> float:
        """Exponential half-life decay in [0,1].

        Missing or unparseable timestamps are treated as STALE (0.0), not freshest
        (Plan 08 fix 16) — a chunk with no valid date must never outrank a dated
        one on recency. Both operands are normalized to UTC-aware before comparison.
        """
        if not created_at:
            return 0.0
        try:
            created = dt.datetime.fromisoformat(str(created_at))
        except (ValueError, TypeError):
            return 0.0
        age_days = max((_as_utc(now) - _as_utc(created)).total_seconds() / 86400.0, 0.0)
        return 0.5 ** (age_days / self.recency_half_life_days)

    def _mmr(
        self,
        candidates: list[dict[str, Any]],
        k: int,
        relevance_key: str,
        diversity_lambda: float,
    ) -> list[dict[str, Any]]:
        """Maximal Marginal Relevance selection over candidate chunks.

        selection score = (1-λ)·relevance − λ·max_similarity_to_selected.
        Similarity uses the store's own embedder over chunk text (policy owns
        this — the store returns candidates, MMR is a ranking decision here).
        """
        if not candidates:
            return []
        k = min(k, len(candidates))
        texts = [chunk["text"] for chunk in candidates]
        vectors = self.store.embedder.embed(texts)

        selected: list[int] = []
        remaining = list(range(len(candidates)))
        while remaining and len(selected) < k:
            best_idx = None
            best_score = -math.inf
            for idx in remaining:
                relevance = float(candidates[idx].get(relevance_key, 0.0))
                if selected:
                    max_sim = max(_cosine(vectors[idx], vectors[s]) for s in selected)
                else:
                    max_sim = 0.0
                score = (1.0 - diversity_lambda) * relevance - diversity_lambda * max_sim
                if score > best_score:
                    best_score = score
                    best_idx = idx
            selected.append(best_idx)  # type: ignore[arg-type]
            remaining.remove(best_idx)  # type: ignore[arg-type]
        return [candidates[idx] for idx in selected]


def _confidence_rank(confidence: str) -> int:
    order = {"low": 0, "medium": 1, "high": 2, "high(primary)": 3}
    return order.get((confidence or "").lower(), 1)


def _normtext(text: str) -> str:
    """Whitespace/case-normalized text for equality checks in merges."""
    return " ".join((text or "").lower().split())


def _iso_key(value: Any) -> str:
    """Sort key for created_at recency ties — a missing value sorts oldest."""
    return str(value or "")


def _style_features(text: str) -> list[float]:
    """A small, topic-agnostic register/length fingerprint of a piece of text.

    Deliberately captures HOW something is written, not what it is about:
    length, average word length, question/exclamation energy, uppercase ratio,
    and digit presence. Each feature is scaled to roughly [0,1] so no single one
    dominates the distance (Plan 08 fix 14).
    """
    stripped = (text or "").strip()
    words = re.findall(r"\S+", stripped)
    word_count = len(words)
    char_count = len(stripped)
    avg_word_len = (sum(len(w) for w in words) / word_count) if word_count else 0.0
    questions = stripped.count("?")
    exclaims = stripped.count("!")
    letters = [c for c in stripped if c.isalpha()]
    upper_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0.0
    digit_ratio = (sum(1 for c in stripped if c.isdigit()) / char_count) if char_count else 0.0
    return [
        min(word_count / 40.0, 1.0),          # length in words
        min(char_count / 280.0, 1.0),         # length in chars (a tweet ceiling)
        min(avg_word_len / 12.0, 1.0),        # lexical density
        min((questions + exclaims) / 3.0, 1.0),  # punctuation energy
        min(upper_ratio * 2.0, 1.0),          # casing / register
        1.0 if digit_ratio > 0 else 0.0,      # numbers present
    ]


def _euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
