"""Build the retrieval index.

Week-1 baseline is BM25 over heading-aware chunks: stdlib-only, deterministic, and
fast enough that the eval suite runs in CI with no API keys. It exists to be the
control. When embeddings or Vertex Vector Search land behind the same `Retriever`
interface, the golden set measures whether the swap actually helped instead of
assuming it did.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from psa.config import CORPUS_DIR, INDEX_PATH
from psa.rag.chunk import load_corpus
from psa.rag.tokenize import tokenize

INDEX_VERSION = 1


def build_index(corpus_dir: Path = CORPUS_DIR) -> dict:
    chunks = load_corpus(corpus_dir)
    postings: dict[str, list[list[int]]] = {}
    lengths: list[int] = []

    for idx, chunk in enumerate(chunks):
        # Weight the title and heading by repeating them: a query naming the symptom
        # should reach the right document even when the body phrases it differently.
        tokens = tokenize(f"{chunk.title} {chunk.heading} {chunk.title} {chunk.text}")
        lengths.append(len(tokens))
        for term, tf in Counter(tokens).items():
            postings.setdefault(term, []).append([idx, tf])

    avgdl = (sum(lengths) / len(lengths)) if lengths else 0.0
    return {
        "version": INDEX_VERSION,
        "built": datetime.now(UTC).isoformat(timespec="seconds"),
        "corpus_dir": str(corpus_dir),
        "n_docs": len({c.doc_id for c in chunks}),
        "n_chunks": len(chunks),
        "avgdl": avgdl,
        "lengths": lengths,
        "chunks": [asdict(c) for c in chunks],
        "postings": postings,
        "idf": {
            term: math.log(1 + (len(chunks) - len(plist) + 0.5) / (len(plist) + 0.5))
            for term, plist in postings.items()
        },
    }


def save_index(index: dict, path: Path = INDEX_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index), encoding="utf-8")
    return path


def main() -> None:
    index = build_index()
    path = save_index(index)
    print(
        f"indexed {index['n_docs']} documents / {index['n_chunks']} chunks "
        f"-> {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}"
    )


if __name__ == "__main__":
    main()
