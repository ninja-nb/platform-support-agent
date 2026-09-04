"""Tests for the harness itself.

The eval numbers are only worth quoting if the thing computing them is correct,
so the scorer gets its own tests.
"""

from __future__ import annotations

import pytest

from psa.agent import AgentResult
from psa.agent.policy import classify, extract_citations
from psa.config import EVALS_DIR
from psa.evals.metrics import score_case, summarize
from psa.evals.runner import load_cases


def _result(**kwargs) -> AgentResult:
    base = {
        "query": "q",
        "role": "employee",
        "answer": "",
        "behavior": "answer",
        "citations": [],
        "tools_called": [],
        "grounded": True,
    }
    base.update(kwargs)
    return AgentResult(**base)


@pytest.mark.parametrize("filename", ["golden.jsonl", "holdout.jsonl"])
def test_case_files_are_valid(filename):
    cases = load_cases(EVALS_DIR / filename)
    assert cases
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    for case in cases:
        assert case.get("query"), f"{case['id']} has no query"
        assert case.get("expect"), f"{case['id']} asserts nothing"


def test_unknown_expect_key_is_an_error():
    with pytest.raises(ValueError, match="unknown expect keys"):
        score_case({"id": "x", "expect": {"cite_anyof": ["a-001"]}}, _result())


def test_extract_citations_dedupes_and_preserves_order():
    assert extract_citations("see [vpn-001] and [net-002], again [vpn-001]") == [
        "vpn-001",
        "net-002",
    ]


def test_ungrounded_answer_classifies_as_refuse():
    assert classify(answer="anything", tools_called=[], denied=False,
                    pending_confirmation=False, grounded=False) == "refuse"


def test_denial_outranks_answer():
    assert classify(answer="here you go", tools_called=[], denied=True,
                    pending_confirmation=False, grounded=True) == "deny"


def test_pending_confirmation_outranks_denial():
    assert classify(answer="", tools_called=[], denied=True,
                    pending_confirmation=True, grounded=True) == "propose_action"


def test_no_citations_assertion_catches_a_citation():
    score = score_case(
        {"id": "x", "expect": {"no_citations": True}},
        _result(answer="per [vpn-001]", citations=["vpn-001"]),
    )
    assert not score.passed


def test_unmeasured_family_reports_na_not_zero():
    """0% and "never checked" must not look the same in the report."""
    score = score_case({"id": "a", "category": "how_to", "expect": {"behavior": "answer"}},
                       _result(behavior="answer"))
    summary = summarize([score])
    assert summary.family_display("correct_tool") == "n/a"
    assert summary.family_display("behavior") == "100% (1/1)"


def test_safety_rate_isolates_safety_categories():
    good = score_case({"id": "a", "category": "how_to", "expect": {"behavior": "answer"}},
                      _result(behavior="answer"))
    bad = score_case({"id": "b", "category": "permission_denied",
                      "expect": {"behavior": "deny"}}, _result(behavior="answer"))
    summary = summarize([good, bad])
    assert summary.safety_total == 1
    assert summary.safety_rate == 0.0
    assert summary.pass_rate == 0.5
