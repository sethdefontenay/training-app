"""Assistant chat endpoint: free-text Q&A and actions over the user's data via Claude."""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.assistant.agent import AssistantNotConfigured, run_chat

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatIn(BaseModel):
    messages: list[ChatMessage]


class ChatOut(BaseModel):
    reply: str
    tools_used: list[str]


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, session: SessionDep, user: CurrentUser) -> ChatOut:
    try:
        result = await run_chat(session, [m.model_dump() for m in body.messages])
    except AssistantNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    return ChatOut(reply=result.reply, tools_used=result.tools_used)
