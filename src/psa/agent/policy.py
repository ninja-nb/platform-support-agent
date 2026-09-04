"""Answer policy: citation extraction and behaviour classification.

The eval harness scores `behavior`, so how it is derived is part of the contract
and lives here rather than being inferred inside the runner.
"""

from __future__ import annotations

import re

CITATION_RE = re.compile(r"\[([a-z]{3,6}-\d{3})\]")

_ESCALATION_MARKERS = (
    "escalate",
    "owning service team",
    "network access team",
    "runtime team",
    "platform billing",
)

_REFUSAL_MARKERS = (
    "could not find",
    "not going to guess",
    "do not know",
    "don't know",
    "no help-center",
    "nothing in the help center",
)

# Asking for missing evidence is a distinct good outcome from refusing: the agent
# knows the relevant runbook but cannot apply it without knowing the target.
_ASK_MARKERS = (
    "which environment",
    "which service",
    "can you tell me",
    "i need to know",
    "could you confirm which",
)

# Behaviour labels used by data/evals/golden.jsonl.
ANSWER = "answer"
REFUSE = "refuse"
ESCALATE = "escalate"
DENY = "deny"
PROPOSE_ACTION = "propose_action"
CREATE_TICKET = "create_ticket"
ASK = "ask"

BEHAVIORS = (ANSWER, REFUSE, ESCALATE, DENY, PROPOSE_ACTION, CREATE_TICKET, ASK)


def extract_citations(text: str) -> list[str]:
    """Return cited doc_ids in first-appearance order, de-duplicated."""
    seen: dict[str, None] = {}
    for doc_id in CITATION_RE.findall(text or ""):
        seen.setdefault(doc_id, None)
    return list(seen)


def classify(
    *,
    answer: str,
    tools_called: list[str],
    denied: bool,
    pending_confirmation: bool,
    grounded: bool,
) -> str:
    text = (answer or "").lower()
    if pending_confirmation:
        return PROPOSE_ACTION
    if denied:
        return DENY
    if not grounded or any(marker in text for marker in _REFUSAL_MARKERS):
        return REFUSE
    if any(marker in text for marker in _ASK_MARKERS):
        return ASK
    if any(marker in text for marker in _ESCALATION_MARKERS):
        return ESCALATE
    if CREATE_TICKET in tools_called:
        return CREATE_TICKET
    return ANSWER
