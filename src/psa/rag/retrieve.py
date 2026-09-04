"""Retrieval interface and the BM25 implementation behind it.

`Retriever` is the seam a vector store swaps into. Anything downstream depends on
`Hit`, never on BM25.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from psa.config import INDEX_PATH, settings
from psa.rag.index import build_index
from psa.rag.tokenize import content_terms, tokenize

# BM25 parameters. Left at the standard defaults; retune only with eval evidence.
K1 = 1.5
B = 0.75

# Deprecated documents stay retrievable but are pushed down, so the agent can say
# "that procedure is retired, use X" instead of silently answering from stale text.
DEPRECATED_PENALTY = 0.35


@dataclass
class Hit:
    doc_id: str
    chunk_id: str
    title: str
    heading: str
    service: str
    text: str
    score: float
    coverage: float
    updated: str = ""
    deprecated: bool = False
    superseded_by: str | None = None

    def citation(self) -> str:
        return f"[{self.doc_id}] {self.title}" + (f" > {self.heading}" if self.heading else "")

    def snippet(self, limit: int = 320) -> str:
        flat = " ".join(self.text.split())
        return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "\u2026"


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 4, min_score: float = 0.0) -> list[Hit]: ...


@dataclass
class BM25Retriever:
    index: dict
    _chunks: list[dict] = field(init=False)

    def __post_init__(self) -> None:
        self._chunks = self.index["chunks"]

    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> BM25Retriever:
        """Load a saved index, building it in memory if none has been written yet."""
        if path.exists():
            return cls(json.loads(path.read_text(encoding="utf-8")))
        return cls(build_index())

    def search(self, query: str, top_k: int = 4, min_score: float = 0.0) -> list[Hit]:
        q_tokens = tokenize(query)
        q_terms = content_terms(query)
        if not q_tokens:
            return []

        postings = self.index["postings"]
        idf = self.index["idf"]
        lengths = self.index["lengths"]
        avgdl = self.index["avgdl"] or 1.0

        scores: dict[int, float] = {}
        for term in set(q_tokens):
            plist = postings.get(term)
            if not plist:
                continue
            term_idf = idf.get(term, 0.0)
            for idx, tf in plist:
                dl = lengths[idx] or 1
                denom = tf + K1 * (1 - B + B * dl / avgdl)
                scores[idx] = scores.get(idx, 0.0) + term_idf * (tf * (K1 + 1)) / denom

        hits: list[Hit] = []
        for idx, raw_score in scores.items():
            hit = self._make_hit(idx, raw_score, q_terms)
            if hit.coverage < min_score:
                continue
            hits.append(hit)

        hits.sort(key=lambda h: (h.score, h.coverage), reverse=True)
        return self._promote_replacements(hits, top_k, q_terms)

    def _coverage(self, chunk: dict, q_terms: list[str]) -> float:
        """Fraction of distinct query content terms present in the chunk.

        Unlike BM25 this is bounded 0..1, which is what makes it usable as an
        absolute "do we actually know this?" threshold for refusal.
        """
        if not q_terms:
            return 0.0
        chunk_tokens = set(tokenize(f"{chunk['title']} {chunk['heading']} {chunk['text']}"))
        distinct = set(q_terms)
        return sum(1 for t in distinct if t in chunk_tokens) / len(distinct)

    def _make_hit(self, idx: int, raw_score: float, q_terms: list[str]) -> Hit:
        chunk = self._chunks[idx]
        deprecated = chunk.get("status") == "deprecated"
        return Hit(
            doc_id=chunk["doc_id"],
            chunk_id=chunk["chunk_id"],
            title=chunk["title"],
            heading=chunk.get("heading", ""),
            service=chunk.get("service", "unknown"),
            text=chunk["text"],
            score=round(raw_score * (DEPRECATED_PENALTY if deprecated else 1.0), 4),
            coverage=round(self._coverage(chunk, q_terms), 4),
            updated=chunk.get("updated", ""),
            deprecated=deprecated,
            superseded_by=chunk.get("superseded_by"),
        )

    def _first_hit_for_doc(self, doc_id: str, q_terms: list[str]) -> Hit | None:
        """Build a hit from a document's opening chunk, ignoring the query score.

        Used to pull in a replacement document that the query terms alone would
        never surface, because users describe the retired procedure, not the new one.
        """
        for idx, chunk in enumerate(self._chunks):
            if chunk["doc_id"] == doc_id:
                return self._make_hit(idx, 0.0, q_terms)
        return None

    def _promote_replacements(self, hits: list[Hit], top_k: int, q_terms: list[str]) -> list[Hit]:
        """Guarantee a superseding document ranks above the document it replaces.

        A relevance penalty alone cannot promise this: a retired runbook is often
        the single best lexical match for a query, because the user is quoting it.
        Enforcing the ordering structurally means the agent always sees the current
        procedure before the stale one, whatever the scores happen to be.
        """
        final: list[Hit] = []
        seen_chunks: set[str] = set()
        seen_docs: set[str] = set()

        def emit(hit: Hit) -> None:
            if hit.chunk_id in seen_chunks:
                return
            seen_chunks.add(hit.chunk_id)
            seen_docs.add(hit.doc_id)
            final.append(hit)

        for hit in hits:
            if len(final) >= top_k:
                break
            if hit.deprecated and hit.superseded_by and hit.superseded_by not in seen_docs:
                replacement = next(
                    (h for h in hits if h.doc_id == hit.superseded_by),
                    None,
                ) or self._first_hit_for_doc(hit.superseded_by, q_terms)
                if replacement is not None:
                    emit(replacement)
                    if len(final) >= top_k:
                        break
            emit(hit)

        return final[:top_k]


_cached: BM25Retriever | None = None


def get_retriever(force_reload: bool = False) -> BM25Retriever:
    global _cached
    if _cached is None or force_reload:
        _cached = BM25Retriever.load()
    return _cached


def search(query: str, top_k: int | None = None, min_score: float | None = None) -> list[Hit]:
    cfg = settings()
    return get_retriever().search(
        query,
        top_k=cfg.top_k if top_k is None else top_k,
        min_score=cfg.min_score if min_score is None else min_score,
    )
