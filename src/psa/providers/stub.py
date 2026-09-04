"""Deterministic offline provider.

Purpose: make the eval harness runnable on a clean checkout with no API key, so
CI can verify the harness itself and so the golden set has a published baseline.

This is NOT a model and its scores are NOT a measure of agent quality. It is a
crude rule-based planner that is expected to fail the harder golden categories.
Those failures are the week-2 worklist: a real provider has to beat this number,
and `docs/EVALS.md` records both.
"""

from __future__ import annotations

import re

from psa.providers.base import Provider, Step, ToolRequest, Turn, Usage

_ENV_RE = re.compile(r"\b((?:prod|staging|sandbox)-[a-z0-9]+)\b", re.IGNORECASE)
_SERVICE_RE = re.compile(r"\b([a-z]+-(?:api|worker|runner))\b", re.IGNORECASE)
_TICKET_RE = re.compile(r"\b(TIC-\d+)\b", re.IGNORECASE)


class StubProvider(Provider):
    name = "stub"

    def next_step(self, query: str, role: str, history: list[Turn]) -> Step:
        called = {t.tool for t in history}
        usage = Usage(input_tokens=len(query.split()), output_tokens=24, cost_usd=0.0)

        ticket_id = _TICKET_RE.search(query)
        environment = _ENV_RE.search(query)
        service = _SERVICE_RE.search(query)

        # 1. Always ground first.
        if "search_docs" not in called:
            return Step(tool_calls=[ToolRequest("search_docs", {"query": query})], usage=usage)

        # 2. Pull the named ticket, if the query names one.
        if ticket_id and "lookup_ticket" not in called:
            request = ToolRequest("lookup_ticket", {"ticket_id": ticket_id.group(1).upper()})
            return Step(tool_calls=[request], usage=usage)

        # 3. Read live state when the query names an environment.
        if environment and "get_status" not in called:
            args: dict = {"environment": environment.group(1)}
            if service:
                args["service"] = service.group(1)
            return Step(tool_calls=[ToolRequest("get_status", args)], usage=usage)

        return Step(answer=self._compose(query, history), usage=usage)

    def _compose(self, query: str, history: list[Turn]) -> str:
        """Assemble an extractive answer from retrieved passages.

        Extractive rather than generative on purpose: with no model available the
        only honest thing to do is quote the corpus and cite it.
        """
        docs = self._grounded_docs(history)
        if not docs:
            return (
                "I could not find anything in the help center that covers this, so I am "
                "not going to guess. I can open a ticket for the platform team instead."
            )

        lines: list[str] = []
        for hit in docs[:2]:
            if hit.get("deprecated"):
                lines.append(
                    f"Note: [{hit['doc_id']}] \"{hit['title']}\" is retired"
                    + (f" and is replaced by [{hit['superseded_by']}]." if hit.get("superseded_by")
                       else ".")
                )
            else:
                lines.append(f"{hit['snippet']} [{hit['doc_id']}]")

        for turn in history:
            if turn.tool == "get_status" and turn.result:
                workers = turn.result.get("workers") or {}
                if workers:
                    lines.append(
                        f"Current state: {workers.get('ready')} of {workers.get('desired')} "
                        f"workers ready."
                    )
        return "\n\n".join(lines)

    @staticmethod
    def _grounded_docs(history: list[Turn]) -> list[dict]:
        for turn in history:
            if turn.tool == "search_docs" and turn.result:
                return turn.result.get("hits", [])
        return []
