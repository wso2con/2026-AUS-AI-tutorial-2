"""Hotel concierge agent — FastAPI service exposing POST /chat.

Module 04 (governance): identical to module 00's agent.py except for
_resolve_openai_config(), which switches the OpenAI client between BYO
mode (direct to OpenAI) and governed mode (through AM's LLM Service
Provider gateway). The switch is env-driven — set OPENAI_BASE_URL to
the gateway URL AM provides, and the agent routes through it.

Tools, prompts, session handling, /health, /chat — unchanged.
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

from system_prompt import SYSTEM_PROMPT
from tools import LANGCHAIN_TOOLS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("concierge")

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

SESSIONS: dict[str, list[BaseMessage]] = {}

_agent = None


def _resolve_openai_config() -> dict[str, Any]:
    """Pick OpenAI client config based on whether we're running governed.

    BYO mode (no OPENAI_BASE_URL): direct to OpenAI, standard auth.

    Governed mode (OPENAI_BASE_URL set): route through AM's LLM Service
    Provider gateway. AM expects the token on a custom `API-Key` header
    rather than the SDK's default `Authorization: Bearer`, so we
    suppress Authorization via default_headers and pass the AM-issued
    JWT through API-Key. `api_key` is set to a non-empty sentinel so
    the SDK constructor doesn't reject the call as missing
    credentials.
    """
    base_url = os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if base_url:
        return {
            "base_url": base_url,
            "api_key": "unused",
            "default_headers": {
                "API-Key": api_key or "",
                "Authorization": "",
            },
        }
    return {"api_key": api_key}


def _get_agent():
    global _agent
    if _agent is None:
        llm = ChatOpenAI(model=OPENAI_MODEL, **_resolve_openai_config())
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
        "governed": bool(os.environ.get("OPENAI_BASE_URL")),
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
