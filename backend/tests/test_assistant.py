"""Assistant: tool handlers, the agent loop (mocked Claude), and the chat endpoint."""

from datetime import date

import anthropic
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant import agent as agent_mod
from app.assistant.agent import run_chat
from app.assistant.tools import TOOLS_BY_NAME
from app.models import DailyWellbeing, SetEntry

DAY = "2026-05-25"


# --- tool handlers ---


async def test_log_set_tool_creates_session_and_set(session: AsyncSession) -> None:
    out = await TOOLS_BY_NAME["log_set"].handler(
        session, {"date": DAY, "exercise_slug": "leg-press-machine", "reps": "15", "weight": "40"}
    )
    assert out["logged"]["set_index"] == 1  # type: ignore[index]
    rows = (await session.execute(select(SetEntry))).scalars().all()
    assert len(rows) == 1 and rows[0].weight == "40"


async def test_set_wellbeing_tool(session: AsyncSession) -> None:
    await TOOLS_BY_NAME["set_wellbeing"].handler(session, {"date": DAY, "energy": 7, "stress": 3})
    row = await session.scalar(
        select(DailyWellbeing).where(DailyWellbeing.date == date(2026, 5, 25))
    )
    assert row is not None and row.energy == 7 and row.stress == 3


async def test_get_today_tool_runs_without_plan(session: AsyncSession) -> None:
    out = await TOOLS_BY_NAME["get_today"].handler(session, {"date": DAY})
    assert out["has_plan"] is False  # type: ignore[index]


# --- agent loop (Claude mocked) ---


class _Block:
    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)

    def model_dump(self) -> dict:
        return dict(self.__dict__)


class _Resp:
    def __init__(self, stop_reason: str, content: list[_Block]) -> None:
        self.stop_reason = stop_reason
        self.content = content


def _fake_anthropic(script: list[_Resp]):
    class _Messages:
        def __init__(self) -> None:
            self.i = 0

        async def create(self, **_: object) -> _Resp:
            r = script[self.i]
            self.i += 1
            return r

    class _Client:
        def __init__(self, *_: object, **__: object) -> None:
            self.messages = _Messages()

    return _Client


async def test_agent_loop_calls_tool_then_answers(session: AsyncSession, monkeypatch) -> None:
    script = [
        _Resp("tool_use", [_Block(type="tool_use", name="get_today", id="t1", input={})]),
        _Resp("end_turn", [_Block(type="text", text="You have no plan today.")]),
    ]
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _fake_anthropic(script))

    class _S:
        anthropic_api_key = "test-key"
        assistant_model = "claude-opus-4-8"
        timezone = "Pacific/Auckland"

    monkeypatch.setattr(agent_mod, "get_settings", lambda: _S())
    out = await run_chat(session, [{"role": "user", "content": "what's on today?"}])
    assert out.reply == "You have no plan today."
    assert out.tools_used == ["get_today"]


# --- endpoint ---


async def test_chat_503_without_api_key(auth_client: AsyncClient, monkeypatch) -> None:
    # With no ANTHROPIC_API_KEY the assistant is disabled (force it off — the dev
    # environment may have a real key exported, which we must never call in tests).
    class _S:
        anthropic_api_key = None
        assistant_model = "claude-opus-4-8"

    monkeypatch.setattr(agent_mod, "get_settings", lambda: _S())
    resp = await auth_client.post(
        "/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert resp.status_code == 503


# --- MCP server (tool layer; transport not exercised here) ---


async def test_mcp_tool_defs_match_registry() -> None:
    from app.assistant.mcp_server import mcp_tool_defs
    from app.assistant.tools import TOOLS

    defs = mcp_tool_defs()
    assert {d.name for d in defs} == {t.name for t in TOOLS}
    assert all(d.inputSchema.get("type") == "object" for d in defs)


async def test_mcp_call_tool_dispatches(session: AsyncSession) -> None:
    import json

    from app.assistant.mcp_server import call_mcp_tool

    # call_mcp_tool opens its own session via SessionLocal; just assert it returns JSON.
    out = json.loads(await call_mcp_tool("get_workout_history", {}))
    assert isinstance(out, list)
    bad = json.loads(await call_mcp_tool("nope", {}))
    assert "error" in bad
