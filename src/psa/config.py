"""Environment-driven configuration. No secrets are read at import time."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
FIXTURES_DIR = DATA_DIR / "fixtures"
EVALS_DIR = DATA_DIR / "evals"
INDEX_PATH = REPO_ROOT / ".index" / "index.json"
AUDIT_LOG_PATH = Path(os.environ.get("PSA_AUDIT_LOG", REPO_ROOT / "audit.log"))


@dataclass(frozen=True)
class Settings:
    provider: str = os.environ.get("PROVIDER", "stub")
    role: str = os.environ.get("PSA_ROLE", "employee")
    user: str = os.environ.get("PSA_USER", "demo@meridiancloud.example")
    top_k: int = int(os.environ.get("PSA_TOP_K", "4"))
    # Minimum query-term coverage for a chunk to count as a hit. Below this the
    # agent must refuse rather than answer. Tuned against data/evals/golden.jsonl.
    min_score: float = float(os.environ.get("PSA_MIN_SCORE", "0.15"))


def settings() -> Settings:
    """Read settings fresh so tests and the UI can vary the environment per call."""
    return Settings()
