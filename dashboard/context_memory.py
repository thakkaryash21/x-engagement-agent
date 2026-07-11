"""ContextMemory — the STABLE policy layer over ContextStore (Plan 07 §5.4).

This layer is preserved across substrate swaps. Everything that is *policy*
lives here and never leaks into the substrate:

- ``write_back`` (§5.5): distill -> dedup/merge -> promotion gate -> store.add,
  and preserve raw evidence immutably to ``data/context/evidence/`` (§5.7).
- ``reflect`` (§5.5.1): synthesize a higher-level insight chunk from a cluster
  of raw chunks and store it (run by ``learn``/``review``, not the hot path).
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
import math
import uuid
from pathlib import Path
from typing import Any, Sequence

from dashboard.context_store import ContextStore

# Context types the promotion gate treats as durable/reusable knowledge when the
# agent gives no explicit ``reusable`` verdict (§5.5 stage 3 heuristic fallback).
_DURABLE_CONTEXT_TYPES = frozenset({"identity", "factual", "cultural", "relational", "insight"})


class ContextMemory:
    def __init__(
        self,
        store: ContextStore,
        *,
        weights: tuple[float, float, float] = (0.55, 0.15, 0.30),
        recency_half_life_days: float = 14.0,
        dedup_threshold: float = 0.88,
        importance_promote_threshold: float = 0.5,
        mmr_lambda: float = 0.7,
        now: dt.datetime | None = None,
    ) -> None:
        self.store = store
        # score = a·relevance + b·recency_decay + c·importance
        self.a, self.b, self.c = weights
        self.recency_half_life_days = recency_half_life_days
        self.dedup_threshold = dedup_threshold
        self.importance_promote_threshold = importance_promote_threshold
        self.mmr_lambda = mmr_lambda
        self._now = now
        self.evidence_dir = store.context_dir / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def now(self) -> dt.datetime:
        return self._now or dt.datetime.now()

    # --- §5.5 unified write-back ----------------------------------------------

    def write_back(self, findings: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
        """Distill -> dedup/merge -> promotion gate -> store.add; preserve evidence.

        ``findings`` are raw acquisition results, each a dict with at least
        ``text`` plus §5.5 meta fields, and optionally ``evidence`` (raw source
        text) and an explicit ``reusable`` verdict. Returns a summary:
        ``{promoted, merged, brief_only, evidence}`` (lists of ids).
        """
        result: dict[str, list[str]] = {"promoted": [], "merged": [], "brief_only": [], "evidence": []}

        for finding in findings:
            chunk = self._distill(finding)

            # §5.7 — preserve the raw source immutably; the chunk indexes it.
            evidence_id = self._preserve_evidence(finding, chunk)
            chunk["evidence_id"] = evidence_id
            result["evidence"].append(evidence_id)

            # §5.5 stage 3 — persist-vs-ephemeral promotion gate.
            if not self._is_reusable(finding, chunk):
                result["brief_only"].append(chunk.get("chunk_id") or "")
                continue

            # §5.5 stage 2 — dedup/merge before write.
            merged_id = self._dedup_merge(chunk)
            if merged_id is not None:
                result["merged"].append(merged_id)
                continue

            chunk_id = self.store.add(chunk["text"], chunk)
            result["promoted"].append(chunk_id)

        return result

    # --- §5.5.1 reflection / consolidation ------------------------------------

    def reflect(self, scope: str, subject: str | None = None) -> dict[str, Any] | None:
        """Synthesize an insight chunk from a cluster of raw chunks and store it.

        Reads (via ``store.search``) the chunks for ``scope`` (optionally a
        single ``subject`` slug), synthesizes a higher-level ``insight`` chunk
        that no single raw chunk holds, and writes it back through ``store.add``
        with high importance and provenance = the source chunk ids. Returns the
        insight chunk (or ``None`` if there is nothing to consolidate).
        """
        candidates = self.store.search(subject or "", k=100, scope=scope)
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
        synthesis = f"Consolidated insight ({scope}/{label}): " + " ".join(
            chunk["text"].strip() for chunk in sources
        )
        insight = {
            "chunk_id": uuid.uuid4().hex,
            "text": synthesis,
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
        merged_id = self._dedup_merge(insight)
        if merged_id is not None:
            insight["chunk_id"] = merged_id
            return insight
        insight["chunk_id"] = self.store.add(insight["text"], insight)
        return insight

    # --- §5.4 CONTENT retrieval ------------------------------------------------

    def retrieve_content(
        self,
        query: str,
        scope: str | None = None,
        gap_type: str | None = None,
        k: int = 8,
    ) -> list[dict[str, Any]]:
        """The content read: score = a·relevance + b·recency + c·importance, + MMR.

        Calls ``store.search`` for raw candidates, applies the three-term blend
        (so a durable high-importance chunk can beat a fresher low-importance one
        at similar relevance), then MMR-diversifies the top set.
        """
        candidates = self.store.search(query, k=max(k, 1) * 4, scope=scope, gap_type=gap_type)
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

    # --- §5.4 STYLE-exemplar retrieval ----------------------------------------

    def style_exemplars(self, persona: str, k: int = 5) -> list[dict[str, Any]]:
        """The persona's own chunks, diversity-selected — NOT topical similarity.

        Style imitation degrades when exemplars are topic-clustered, so this
        selects for stylistic *coverage*: it takes the persona's ``scope=self``
        chunks and greedily picks the most mutually-dissimilar set (MMR with the
        relevance term neutralized).
        """
        pool = self.store.search("", k=200, scope="self")
        pool = [chunk for chunk in pool if not persona or chunk.get("persona") == persona]
        if not pool:
            return []
        # Pure-diversity selection: relevance weight 0, so topic never clusters them.
        for chunk in pool:
            chunk["_uniform"] = 1.0
        return self._mmr(pool, k, relevance_key="_uniform", diversity_lambda=1.0)

    # --- Internals -------------------------------------------------------------

    def _distill(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw finding into a single well-formed chunk (§5.5 stage 1)."""
        now_iso = self.now().isoformat()
        importance = finding.get("importance")
        chunk = {
            "chunk_id": finding.get("chunk_id") or uuid.uuid4().hex,
            "text": (finding.get("text") or "").strip(),
            "scope": finding.get("scope") or "world",
            "source_type": finding.get("source_type") or "web_search",
            "context_type": finding.get("context_type") or "factual",
            "confidence": finding.get("confidence") or "medium",
            "importance": float(importance) if importance is not None else 0.5,
            "entities": list(finding.get("entities") or []),
            "created_at": finding.get("created_at") or now_iso,
            "last_refreshed": finding.get("last_refreshed") or now_iso,
            "provenance": finding.get("provenance") or "",
            "evidence_id": finding.get("evidence_id") or "",
            "subject_slug": finding.get("subject_slug") or "",
            "persona": finding.get("persona") or "",
        }
        return chunk

    def _preserve_evidence(self, finding: dict[str, Any], chunk: dict[str, Any]) -> str:
        """Write the immutable raw-source record (§5.7) and return its id."""
        evidence_id = finding.get("evidence_id") or chunk.get("evidence_id") or f"ev_{uuid.uuid4().hex}"
        path = self.evidence_dir / f"{evidence_id}.md"
        if path.exists():  # append-only: never rewrite an existing evidence record
            return evidence_id
        raw = finding.get("evidence") or chunk["text"]
        header = [
            "---",
            f"evidence_id: {evidence_id}",
            f"captured_at: {self.now().isoformat()}",
            f"adapter: {chunk['source_type']}",
            f"source: {chunk['provenance']}",
            f"scope: {chunk['scope']}",
            "---",
        ]
        path.write_text("\n".join(header) + "\n" + str(raw).strip() + "\n", encoding="utf-8")
        return evidence_id

    def _is_reusable(self, finding: dict[str, Any], chunk: dict[str, Any]) -> bool:
        """Promotion gate (§5.5 stage 3): does this chunk deserve durable memory?

        An explicit agent verdict wins; otherwise a durable ``context_type`` at
        or above the importance threshold is promoted, and one-off/ephemeral
        material stays brief-only.
        """
        explicit = finding.get("reusable")
        if explicit is not None:
            return bool(explicit)
        if chunk["context_type"] not in _DURABLE_CONTEXT_TYPES:
            return False
        return chunk["importance"] >= self.importance_promote_threshold

    def _dedup_merge(self, chunk: dict[str, Any]) -> str | None:
        """Merge into a near-duplicate existing chunk if one exists (§5.5 stage 2).

        Returns the merged chunk_id when a merge happened, else ``None`` (caller
        then adds it fresh). A near-duplicate = high substrate relevance AND
        overlapping entities; the merge keeps the surviving chunk_id, prefers the
        higher-confidence text, and bumps ``last_refreshed``.
        """
        existing = self.store.search(chunk["text"], k=5, scope=chunk["scope"])
        new_entities = {entity.lower() for entity in chunk.get("entities") or []}
        for candidate in existing:
            if candidate.get("relevance", 0.0) < self.dedup_threshold:
                continue
            cand_entities = {entity.lower() for entity in candidate.get("entities") or []}
            if new_entities and cand_entities and not (new_entities & cand_entities):
                continue

            merged = dict(candidate)
            merged["chunk_id"] = candidate["chunk_id"]
            merged["last_refreshed"] = self.now().isoformat()
            merged["importance"] = max(
                float(candidate.get("importance", 0.0)), float(chunk.get("importance", 0.0))
            )
            if _confidence_rank(chunk["confidence"]) > _confidence_rank(candidate.get("confidence", "")):
                merged["text"] = chunk["text"]
                merged["confidence"] = chunk["confidence"]
            # union entities
            union: list[str] = list(candidate.get("entities") or [])
            for entity in chunk.get("entities") or []:
                if entity not in union:
                    union.append(entity)
            merged["entities"] = union
            for field in ("scope", "source_type", "context_type", "created_at", "provenance",
                          "evidence_id", "subject_slug", "persona"):
                merged.setdefault(field, candidate.get(field, ""))
            self.store.add(merged["text"], merged)
            return candidate["chunk_id"]
        return None

    def _recency_decay(self, created_at: Any, now: dt.datetime) -> float:
        """Exponential half-life decay in [0,1]; unparseable/empty = neutral 1.0."""
        if not created_at:
            return 1.0
        try:
            created = dt.datetime.fromisoformat(str(created_at))
        except (ValueError, TypeError):
            return 1.0
        age_days = max((now - created).total_seconds() / 86400.0, 0.0)
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


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
