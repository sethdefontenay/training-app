"""The Opus agent loop: Claude + the tool registry, executed in-process."""

import json
from dataclasses import dataclass

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.tools import TOOLS_BY_NAME, anthropic_tools
from app.clock import local_now
from app.config import get_settings

MAX_TURNS = 10
MAX_TOKENS = 2048


@dataclass
class ChatResult:
    reply: str
    tools_used: list[str]


_SYSTEM = """You are the assistant built into Seth's personal training, nutrition and \
Type 1 diabetes app. Answer his free-text questions about his data, and make changes when \
he asks. You have tools to read his plan, daily logs, meals, wellbeing, body measurements, \
glucose/insulin, steps/sleep and workout history — and to log sets, check off meals, set \
wellbeing scores and record measurements.

Rules:
- Use the tools to get real data before answering. Never invent numbers; if a tool returns \
nothing, say so plainly.
- All dates are in Seth's local timezone. Resolve relative dates ("today", "tomorrow", \
"yesterday", "this week") from the current date given below, and pass explicit YYYY-MM-DD \
dates to the tools.
- Be concise and direct. Lead with the answer.
- Before writing/modifying data, make sure you have the details you need; afterwards, state \
exactly what you changed. If a request is ambiguous, ask rather than guess.
- For glucose, note that insulin-on-board is a model estimate, not pump-reported."""


class AssistantNotConfigured(RuntimeError):
    pass


async def run_chat(session: AsyncSession, messages: list[dict[str, object]]) -> ChatResult:
    """Run the tool-use loop. `messages` is the conversation so far ({role, content})."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise AssistantNotConfigured("Assistant not configured — set ANTHROPIC_API_KEY.")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    now = local_now()
    system = (
        f"{_SYSTEM}\n\nThe current date is {now:%A, %Y-%m-%d} "
        f"(time {now:%H:%M}) in Seth's timezone, {settings.timezone}. "
        "Compute relative dates from this."
    )
    tools = anthropic_tools()
    convo: list[dict[str, object]] = list(messages)
    used: list[str] = []

    for _ in range(MAX_TURNS):
        resp = await client.messages.create(
            model=settings.assistant_model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tools,  # type: ignore[arg-type]
            messages=convo,  # type: ignore[arg-type]
        )
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return ChatResult(reply=text, tools_used=used)

        convo.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            used.append(block.name)
            tool = TOOLS_BY_NAME.get(block.name)
            try:
                if tool is None:
                    payload: object = {"error": f"unknown tool {block.name}"}
                else:
                    payload = await tool.handler(session, dict(block.input))
                content = json.dumps(payload, default=str)
            except Exception as e:  # surface failures to the model, don't crash the turn
                content = json.dumps({"error": str(e)})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        convo.append({"role": "user", "content": results})

    return ChatResult(reply="Sorry — I hit the tool-call limit before finishing.", tools_used=used)
