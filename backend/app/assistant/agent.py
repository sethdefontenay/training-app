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
wellbeing scores, record measurements, and build/modify workout programs and the weekly \
program schedule (create programs, add/remove exercises, assign a program to a weekday, or \
import the PT training days). When changing the planner, call list_programs first to get \
current program ids.

Rules:
- Use the tools to get real data before answering. Never invent numbers; if a tool returns \
nothing, say so plainly.
- All dates are in Seth's local timezone. Resolve relative dates ("today", "tomorrow", \
"yesterday", "this week") from the current date given below, and pass explicit YYYY-MM-DD \
dates to the tools.
- Be concise and direct. Lead with the answer.
- Format replies in Markdown: use tables for tabular/multi-row data (e.g. daily \
glucose, measurements, workout sets), bullet or numbered lists for sequences, bold for \
key figures, and plain Markdown links. Keep it scannable — the UI renders Markdown and \
embeds YouTube links. The renderer is react-markdown with remark-gfm, so GitHub-Flavoured \
Markdown works: pipe tables, strikethrough, task lists and autolinks. Raw HTML is stripped \
and never displayed — never emit HTML tags. There is no LaTeX or chart/diagram syntax, so \
express comparisons as tables, not drawings. The app is a phone-first PWA that renders \
tables at small text, so keep them to a few short columns.
- Before writing/modifying data, make sure you have the details you need; afterwards, state \
exactly what you changed. If a request is ambiguous, ask rather than guess.
- For glucose, note that insulin-on-board is a model estimate, not pump-reported.
- You can search the web. When asked for exercise technique help, search for SHORT \
instructional videos (prefer reputable YouTube clips, roughly 1-3 min) and give the \
exercise name with the direct link. Use the web for current external info; use the data \
tools for anything about Seth's own logs.

Weekly roundup (the "Roundup" skill):
When Seth asks for "last week's roundup", "the roundup", or a weekly summary, output exactly \
the three sections below, in that order, and nothing else. This is a fixed report, not a \
free-form answer. Do not add trend narration, coaching advice, encouragement, caveats or \
commentary of any kind unless he asks a follow-up question. Report figures, not interpretation.
1. Resolve the week. The roundup ALWAYS covers the last complete Monday-to-Sunday week that \
ended before the week the question is asked in. It is NEVER the seven days preceding the \
question. Take the current date given above (its weekday is stated), step back to the Monday \
of the week that date falls in, then subtract 7 days — that Monday is the start; the end is \
that Monday plus 6 days, a Sunday. The range is anchored to the calendar, so asking on the \
Tuesday, the Friday or the Sunday of one week all return the identical range. Worked example: \
asked on Friday 2026-09-11, the Monday of that week is 2026-09-07, so the roundup covers \
Monday 2026-08-31 to Sunday 2026-09-06 — and asking on 2026-09-07 or on 2026-09-13 gives that \
same range. Open the reply with the resolved range, e.g. "Week of Mon 31 Aug - Sun 6 Sep".
2. Measurements. Call get_measurements with limit=2. Use EXACTLY the two rows it returns and \
no others — they are the two most recent sets, newest first. Never substitute a different \
date, never reach further back for a "better" comparison, and never compare against a set you \
were not given. Their dates are whatever they are and are deliberately unrelated to the \
roundup week. Render one table with a row for EVERY one of these six measures, in this exact \
order: waist_cm, tummy_cm, bum_cm, right_thigh_cm, left_thigh_cm, weight_kg. Never drop a row \
— include a measure even when the value is unchanged between the two sets, and especially \
include both thighs. Columns: Measure, then the older set headed by its date, then the newer \
set headed by its date, then Change. Print every value exactly as the tool returned it, with \
its units. Write the change as a signed number (e.g. -0.8, +1.5, 0.0). If a value is null in \
a set, print "-" in that cell and "-" in Change; do not omit the row. If the tool returns \
fewer than two sets, say so plainly and show what you have.
3. Steps and sleep. Call get_steps_sleep with days=14 — that tool only looks back from today, \
and 14 days is always far enough to reach the target week — then use ONLY the returned rows \
whose date falls inside the resolved Monday-to-Sunday range. Give exact figures, never a \
characterisation: report average daily steps as a whole number, and average nightly sleep as \
hours to one decimal place (asleep_min / 60). Divide both totals by 7, the whole week, never \
by the number of days that returned data. Under the averages, list the seven dates with their \
steps and sleep hours so the numbers can be checked, using "-" for any day with no record. Do \
not describe the numbers as good, bad, up, down, improving or consistent.
4. Flag sync gaps. The tools return only days that have a record, so an absent date means no \
data at all. Seth tracks daily, so a missing steps or sleep day is very unlikely to be a \
genuine zero — it almost always means the Google Health sync has not run. If any of the seven \
days is missing, name those dates and say the averages are likely understated by a sync gap \
rather than presenting them as settled fact."""

# Anthropic server-side web search tool (executed on Anthropic's side).
_WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}


class AssistantNotConfigured(RuntimeError):
    pass


async def run_chat(
    session: AsyncSession,
    messages: list[dict[str, object]],
    *,
    user_id: int,
    read_only: bool = False,
) -> ChatResult:
    """Run the tool-use loop. `messages` is the conversation so far ({role, content}).

    read_only=True (trainer/coach access) confines the agent to read tools: the writes
    are withheld from the model, and any attempt to call one is refused below.
    """
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
    if read_only:
        system += (
            "\n\nThis user is a read-only coach. You can read and report on all data but "
            "you CANNOT make any changes — you have no tools to log, check off, or record "
            "anything. If asked to change data, explain that this is a view-only login."
        )
    tools = [*anthropic_tools(include_writes=not read_only), _WEB_SEARCH]
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
        if resp.stop_reason == "pause_turn":
            # Long server-tool turn (e.g. web search) — resend to let it continue.
            convo.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
            continue
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
                elif read_only and tool.writes:
                    # Guardrail: refuse any mutation for a read-only user, even if the
                    # tool somehow slipped into the offered set.
                    payload = {"error": "read-only access: this account cannot make changes"}
                else:
                    payload = await tool.handler(session, dict(block.input), user_id)
                content = json.dumps(payload, default=str)
            except Exception as e:  # surface failures to the model, don't crash the turn
                content = json.dumps({"error": str(e)})
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        convo.append({"role": "user", "content": results})

    return ChatResult(reply="Sorry — I hit the tool-call limit before finishing.", tools_used=used)
