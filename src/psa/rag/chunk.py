"""Corpus loading: frontmatter parsing and heading-aware chunking.

Chunking on `##` headings keeps "Resolution" and "Escalate when" as separate
retrievable units, which is what makes the escalation eval cases answerable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LIST_KEYS = {"tags"}


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    service: str
    status: str
    updated: str
    heading: str
    text: str
    superseded_by: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def is_deprecated(self) -> bool:
        return self.status == "deprecated"


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Parse a minimal `key: value` frontmatter block. Avoids a PyYAML dependency."""
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    meta: dict = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key in _LIST_KEYS:
            meta[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            meta[key] = value
    return meta, raw[m.end() :]


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, text) pairs on `##` boundaries."""
    sections: list[tuple[str, str]] = []
    heading = ""
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if buf and "".join(buf).strip():
                sections.append((heading, "\n".join(buf).strip()))
            heading = line[3:].strip()
            buf = []
        elif line.startswith("# "):
            # Document title line; fold into the preamble rather than its own chunk.
            heading = heading or line[2:].strip()
        else:
            buf.append(line)
    if buf and "".join(buf).strip():
        sections.append((heading, "\n".join(buf).strip()))
    return sections


def load_document(path: Path) -> list[Chunk]:
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    doc_id = meta.get("doc_id") or path.stem
    chunks: list[Chunk] = []
    for i, (heading, text) in enumerate(split_sections(body)):
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}#{i}",
                doc_id=doc_id,
                title=meta.get("title", doc_id),
                service=meta.get("service", "unknown"),
                status=meta.get("status", "current"),
                updated=meta.get("updated", ""),
                superseded_by=meta.get("superseded_by"),
                tags=meta.get("tags", []),
                heading=heading,
                text=text,
            )
        )
    return chunks


def load_corpus(corpus_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        chunks.extend(load_document(path))
    if not chunks:
        raise FileNotFoundError(f"no corpus documents found in {corpus_dir}")
    return chunks
