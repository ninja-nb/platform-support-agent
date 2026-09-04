"""Shared tokenizer. Index and query must tokenize identically."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9_]+")

# Deliberately small. Removing domain words like "network" or "restart" would
# destroy the signal these queries depend on.
STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those there here
    is are was were be been being am do does did doing done
    i me my we our you your it its he she they them their
    of in on at to from by for with without about into over under
    as not no can cannot could should would will just very so too
    what why how when where which who whom whose
    get got getting have has had having need needs
    """.split()  # noqa: SIM905 - readability beats the literal here
)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def content_terms(text: str) -> list[str]:
    """Query tokens with stopwords removed, used for coverage scoring."""
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]
