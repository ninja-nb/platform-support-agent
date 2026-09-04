from __future__ import annotations

import pytest

from psa.rag.chunk import parse_frontmatter, split_sections
from psa.rag.retrieve import BM25Retriever


@pytest.fixture(scope="module")
def retriever() -> BM25Retriever:
    return BM25Retriever.load()


def test_frontmatter_parses_lists():
    meta, body = parse_frontmatter("---\ndoc_id: x-1\ntags: a, b\n---\n# Title\ntext\n")
    assert meta["doc_id"] == "x-1"
    assert meta["tags"] == ["a", "b"]
    assert "text" in body


def test_sections_split_on_h2():
    headings = [h for h, _ in split_sections("# T\nintro\n## One\na\n## Two\nb\n")]
    assert "One" in headings and "Two" in headings


def test_vpn_query_retrieves_vpn_doc(retriever):
    hits = retriever.search("VPN client TLS handshake failed verifying peer", top_k=4)
    assert "vpn-001" in {h.doc_id for h in hits}


def test_deprecated_doc_is_outranked_by_its_replacement(retriever):
    hits = retriever.search("VPN pre-shared key rotate shared key", top_k=5)
    ranked = [h.doc_id for h in hits]
    assert "vpn-001" in ranked
    if "vpn-007" in ranked:
        assert ranked.index("vpn-001") < ranked.index("vpn-007")


def test_deprecated_doc_is_flagged(retriever):
    hits = retriever.search("pre-shared key PSK advanced settings", top_k=5)
    stale = [h for h in hits if h.doc_id == "vpn-007"]
    if stale:
        assert stale[0].deprecated
        assert stale[0].superseded_by == "vpn-001"


def test_coverage_threshold_rejects_off_corpus_queries(retriever):
    """A high coverage bar must yield nothing for a query the corpus cannot answer."""
    hits = retriever.search("snowflake connector certificate rotation procedure", min_score=0.6)
    assert hits == []
