"""OpenAI provider tests.

These cover the translation layer — messages, tool schemas, usage, response
mapping — with a fake client. That is where provider bugs live; the HTTP call
itself is the SDK's problem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from psa.providers.base import Turn
from psa.providers.openai_provider import PRICE_PER_1M, OpenAIProvider


@dataclass
class FakeFunction:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunction


@dataclass
class FakeMessage:
    content: str | None = None
    tool_calls: list[FakeToolCall] = field(default_factory=list)


@dataclass
class FakeUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list[FakeChoice]
    usage: FakeUsage | None = None


class FakeClient:
    """Records the request and replays a canned response."""

    def __init__(self, response: FakeResponse):
        self._response = response
        self.last_request: dict[str, Any] = {}
        self.chat = self  # mimic client.chat.completions.create
        self.completions = self

    def create(self, **kwargs) -> FakeResponse:
        self.last_request = kwargs
        return self._response


def _provider(message: FakeMessage, usage: FakeUsage | None = None) -> OpenAIProvider:
    client = FakeClient(FakeResponse([FakeChoice(message)], usage))
    return OpenAIProvider(model="gpt-4o-mini", client=client)


def test_no_api_key_needed_when_client_injected(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert _provider(FakeMessage(content="hi")).name == "openai"


def test_missing_api_key_without_client_is_an_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIProvider()


def test_tool_calls_map_to_tool_requests():
    message = FakeMessage(
        tool_calls=[
            FakeToolCall("call_abc", FakeFunction("search_docs", '{"query": "vpn"}')),
        ]
    )
    step = _provider(message).next_step("vpn broken", "employee", [])
    assert not step.is_final
    assert step.tool_calls[0].name == "search_docs"
    assert step.tool_calls[0].args == {"query": "vpn"}
    assert step.tool_calls[0].call_id == "call_abc"


def test_tool_calls_win_over_content_in_the_same_message():
    """A run is not finished while the model is still asking for data."""
    message = FakeMessage(
        content="Let me look that up.",
        tool_calls=[FakeToolCall("c1", FakeFunction("get_status", '{"environment": "prod-east"}'))],
    )
    step = _provider(message).next_step("q", "sre", [])
    assert not step.is_final
    assert step.answer is None


def test_plain_content_is_a_final_answer():
    step = _provider(FakeMessage(content="Re-enroll the device [vpn-001].")).next_step(
        "q", "employee", []
    )
    assert step.is_final
    assert "vpn-001" in step.answer


def test_malformed_tool_arguments_degrade_to_empty_args():
    message = FakeMessage(tool_calls=[FakeToolCall("c1", FakeFunction("get_status", "{not json"))])
    step = _provider(message).next_step("q", "sre", [])
    assert step.tool_calls[0].args == {}


def test_non_object_tool_arguments_degrade_to_empty_args():
    message = FakeMessage(tool_calls=[FakeToolCall("c1", FakeFunction("get_status", "[1,2]"))])
    step = _provider(message).next_step("q", "sre", [])
    assert step.tool_calls[0].args == {}


def test_cost_is_computed_from_the_price_table():
    provider = _provider(FakeMessage(content="ok"), FakeUsage(1_000_000, 1_000_000))
    step = provider.next_step("q", "employee", [])
    in_price, out_price = PRICE_PER_1M["gpt-4o-mini"]
    assert step.usage.cost_usd == pytest.approx(in_price + out_price)


def test_unknown_model_costs_zero_rather_than_guessing():
    client = FakeClient(FakeResponse([FakeChoice(FakeMessage(content="ok"))], FakeUsage(100, 100)))
    provider = OpenAIProvider(model="gpt-9-imaginary", client=client)
    assert provider.next_step("q", "employee", []).usage.cost_usd == 0.0


def test_history_replays_as_paired_assistant_and_tool_messages():
    provider = _provider(FakeMessage(content="done"))
    history = [
        Turn(tool="search_docs", args={"query": "vpn"}, result={"hits": []}, call_id="call_1"),
    ]
    provider.next_step("vpn", "employee", history)
    messages = provider.client.last_request["messages"]

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assistant, tool = messages[2], messages[3]
    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert assistant["tool_calls"][0]["function"]["name"] == "search_docs"
    # Every tool message must reference the call it answers.
    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "call_1"


def test_tool_errors_reach_the_model_as_content():
    """A denial the model cannot read is a denial it will retry forever."""
    provider = _provider(FakeMessage(content="You lack permission."))
    history = [Turn(tool="restart_service", args={}, error="role 'employee' may not", call_id="c9")]
    provider.next_step("restart it", "employee", history)
    tool_message = provider.client.last_request["messages"][3]
    assert "may not" in json.loads(tool_message["content"])["error"]


def test_role_note_is_included_in_the_system_prompt():
    provider = _provider(FakeMessage(content="ok"))
    provider.next_step("q", "sre", [])
    assert "sre" in provider.client.last_request["messages"][0]["content"]


def test_every_tool_is_advertised_with_a_schema():
    provider = _provider(FakeMessage(content="ok"))
    provider.next_step("q", "employee", [])
    tools = provider.client.last_request["tools"]
    names = {t["function"]["name"] for t in tools}
    assert {"search_docs", "restart_service", "create_ticket"} <= names
    for tool in tools:
        assert tool["function"]["parameters"]["type"] == "object"


def test_temperature_is_pinned_for_reproducible_evals():
    provider = _provider(FakeMessage(content="ok"))
    provider.next_step("q", "employee", [])
    assert provider.client.last_request["temperature"] == 0
