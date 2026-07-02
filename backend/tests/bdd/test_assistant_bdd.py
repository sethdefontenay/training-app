"""Execute features/assistant.feature via pytest-bdd (sync TestClient harness).

Testable scenarios (503-without-key, MCP bearer guard, MCP tool-registry parity) run for
real. The LLM-dependent scenarios seed their data but skip the When step, since they need a
live Anthropic model that the test environment has no key for.
"""

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.assistant import agent as agent_mod
from app.assistant.mcp_server import bearer_guard
from app.assistant.tools import TOOLS, anthropic_tools
from tests.bdd.seed import full_plan

scenarios("assistant.feature")

_CHAT = "/api/v1/assistant/chat"
_TOKEN = "secret-mcp-token"


# --- Background ---


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given("the assistant is configured with an Anthropic API key")
def _configured() -> None:
    pass  # nothing to do: the testable scenarios don't call the model


# --- Given steps ---


@given("no Anthropic API key is configured")
def _no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # The dev environment may export a real key; force the assistant off so no
    # live model is ever called from the test suite.
    class _S:
        anthropic_api_key = None
        assistant_model = "claude-opus-4-8"
        timezone = "Pacific/Auckland"

    monkeypatch.setattr(agent_mod, "get_settings", lambda: _S())


@given("there is no glucose data for the period asked about")
def _no_glucose() -> None:
    pass  # nothing seeded => no glucose rows


@given("the MCP server is enabled with a token")
def _mcp_enabled(context: dict[str, object]) -> None:
    context["mcp_token"] = _TOKEN


# --- When steps ---


@when(parsers.parse('I ask the assistant "{question}"'))
def _ask(question: str) -> None:
    pytest.skip("requires live Anthropic model")


@when(parsers.parse('I tell the assistant "{instruction}"'))
def _tell(seed, instruction: str) -> None:
    seed(lambda s: full_plan(s, start=date(2026, 5, 21)))
    pytest.skip("requires live Anthropic model")


@when("I ask the assistant about that period")
def _ask_about_period() -> None:
    pytest.skip("requires live Anthropic model")


@when("I ask the assistant for technique help on an exercise")
def _ask_technique() -> None:
    pytest.skip("requires live Anthropic model")


@when("I send a message to the assistant")
def _send_message(bdd_client: TestClient, context: dict[str, object]) -> None:
    context["resp"] = bdd_client.post(_CHAT, json={"messages": [{"role": "user", "content": "hi"}]})


@when("a client connects without the token")
def _connect_without_token(context: dict[str, object]) -> None:
    context["status"] = _probe_guard(str(context["mcp_token"]), authorization=None)


@when("an authorised client lists tools")
def _list_tools(context: dict[str, object]) -> None:
    context["tool_names"] = {t.name for t in TOOLS}
    context["anthropic_names"] = {t["name"] for t in anthropic_tools()}


# --- Then steps ---


@then("I am told the assistant isn't configured")
def _told_not_configured(context: dict[str, object]) -> None:
    resp = context["resp"]
    assert resp.status_code == 503
    assert "configured" in resp.json()["detail"].lower()


@then("the request is rejected as unauthorized")
def _rejected(context: dict[str, object]) -> None:
    assert context["status"] == 401


@then("it sees the same read and write tools the in-app assistant uses")
def _same_tools(context: dict[str, object]) -> None:
    names = context["tool_names"]
    # The MCP server (mcp_tool_defs) and anthropic_tools() draw from one registry.
    assert names == context["anthropic_names"]
    # And it's the full read+write set (writes are present).
    assert any(t.writes for t in TOOLS) and any(not t.writes for t in TOOLS)


# --- LLM-dependent Then steps (never reached: When skips) ---


@then("it reads my glucose data and answers with my real average and time-in-range")
def _glucose_answer() -> None:
    pass


@then("it reads my logged sets and answers with the trend over time")
def _progress_answer() -> None:
    pass


@then("the sets are recorded against today's session")
def _sets_recorded() -> None:
    pass


@then("it confirms exactly what it logged")
def _confirms_logged() -> None:
    pass


@then("it says there is no data rather than inventing numbers")
def _no_data_answer() -> None:
    pass


@then("it searches the web and returns links to short instructional videos")
def _video_links() -> None:
    pass


# --- helpers ---


def _probe_guard(token: str, *, authorization: str | None) -> int:
    """Drive bearer_guard as a raw ASGI app and capture the response status.

    The inner app returns 200; the guard should short-circuit to 401 when the
    bearer token is missing or wrong.
    """

    async def _inner(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    guarded = bearer_guard(_inner, token)
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    scope = {"type": "http", "headers": headers}
    captured: dict[str, int] = {}

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(message: dict[str, object]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = int(message["status"])  # type: ignore[arg-type]

    asyncio.run(guarded(scope, _receive, _send))
    return captured["status"]
