"""Hotel concierge agent — module 02 (identity).

Same FastAPI shape as module 00, with two changes:
1. The chat handler extracts a user_token from request context and sets
   it on a contextvar so the book_room tool can use it for token
   exchange.
2. The set of tools is selected by the BOOKING_MODE env var. Default is
   the right way (agent identity + token exchange via tools.py); set
   BOOKING_MODE=shared_key to demo the wrong way (tools_shared_key.py).

Everything else — session state, /health endpoint, OpenAI client
configuration — is identical to module 00.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from context import USER_TOKEN
from system_prompt import SYSTEM_PROMPT

if os.environ.get("BOOKING_MODE") == "shared_key":
    from tools_shared_key import LANGCHAIN_TOOLS
else:
    from tools import LANGCHAIN_TOOLS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("concierge")

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
SESSIONS: dict[str, list[BaseMessage]] = {}
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        llm = ChatOpenAI(model=OPENAI_MODEL, api_key=os.environ.get("OPENAI_API_KEY"))
        _agent = create_react_agent(llm, tools=LANGCHAIN_TOOLS, prompt=SYSTEM_PROMPT)
    return _agent


app = FastAPI(title="Grand Meridian Concierge")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    response: str


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "Grand Meridian Concierge",
        "tip": "POST /chat with {message, session_id, context}. GET /health for status.",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model": OPENAI_MODEL,
        "booking_mode": os.environ.get("BOOKING_MODE", "agent_identity"),
    }


def _final_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = [
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                ]
                return "".join(parts).strip()
    return ""


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        return ChatResponse(response="How can I help you today?")

    sid = req.session_id or "_anonymous_"

    user_token = (req.context or {}).get("user_token") if req.context else None
    USER_TOKEN.set(user_token)

    history = SESSIONS.get(sid, []) + [HumanMessage(content=req.message)]
    try:
        result = _get_agent().invoke({"messages": history})
        history = result["messages"]
        reply = _final_text(history) or "I'm not sure how to help with that."
    except Exception as e:
        log.exception("session=%s error: %s", sid, e)
        reply = "I'm having trouble reaching our systems. Please try again in a moment."

    SESSIONS[sid] = history
    return ChatResponse(response=reply)
