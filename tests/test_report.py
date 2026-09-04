"""The generated report must never destroy the hand-written regression log."""

from __future__ import annotations

from psa.agent import AgentResult
from psa.evals.metrics import score_case, summarize
from psa.evals.runner import REGRESSION_HEADING, preserved_regression_log, render_report


def _score():
    result = AgentResult(query="q", role="employee", answer="a", behavior="answer", grounded=True)
    return score_case({"id": "x", "category": "how_to", "expect": {"behavior": "answer"}}, result)


def test_regression_log_survives_regeneration(tmp_path, monkeypatch):
    report = tmp_path / "EVALS.md"
    report.write_text(
        "# Evaluation results\n\nold tables here\n\n"
        f"{REGRESSION_HEADING}\n\n### R1. Something important\n\nHand-written prose.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("psa.evals.runner.REPORT_PATH", report)

    rendered = render_report([_score()], summarize([_score()]), "stub")

    assert "R1. Something important" in rendered
    assert "Hand-written prose." in rendered
    assert "old tables here" not in rendered
    assert rendered.count(REGRESSION_HEADING) == 1


def test_first_run_emits_a_placeholder_log(tmp_path, monkeypatch):
    monkeypatch.setattr("psa.evals.runner.REPORT_PATH", tmp_path / "absent.md")
    rendered = render_report([_score()], summarize([_score()]), "stub")
    assert REGRESSION_HEADING in rendered
    assert "_No entries yet._" in rendered


def test_missing_heading_is_not_preserved(tmp_path, monkeypatch):
    report = tmp_path / "EVALS.md"
    report.write_text("# Evaluation results\n\nno log section\n", encoding="utf-8")
    monkeypatch.setattr("psa.evals.runner.REPORT_PATH", report)
    assert preserved_regression_log(report) is None
