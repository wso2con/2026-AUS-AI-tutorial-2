"""Five evaluators for the concierge agent.

Three rule-based (deterministic, no LLM cost):
- tool_efficiency: did the agent call the expected tool, and only that?
- step_success_rate: did any tool return an {"error": ...}?
- latency_under_sla: end-to-end latency below threshold?

Two LLM-as-judge (rubric-based, gpt-4o-mini):
- helpfulness: did the response actually answer the user's question?
- groundedness: were factual claims supported by tool results?

Each evaluator returns an EvalScore: a numeric value, a pass/fail flag
against a threshold, and a short reason. The eval runner aggregates
them across all reference conversations.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from openai import OpenAI

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gpt-4o-mini")
LATENCY_SLA_MS = int(os.environ.get("LATENCY_SLA_MS", "8000"))
# LLM-judge scores are on a 0–100 scale; thresholds are pass-mark percentages.
HELPFULNESS_THRESHOLD = float(os.environ.get("HELPFULNESS_THRESHOLD", "80"))
GROUNDEDNESS_THRESHOLD = float(os.environ.get("GROUNDEDNESS_THRESHOLD", "80"))

_judge_client: OpenAI | None = None


def _judge() -> OpenAI:
    global _judge_client
    if _judge_client is None:
        _judge_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _judge_client


@dataclass
class EvalScore:
    name: str
    value: float
    passed: bool
    reason: str


def _tool_calls(messages: list) -> list[dict]:
    """Extract every tool invocation from a LangGraph message trail."""
    calls = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                calls.append({"name": tc["name"], "args": tc.get("args", {})})
    return calls


def _tool_returns(messages: list) -> list[dict]:
    """Pull each tool's return value, parsed as JSON if possible."""
    returns = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                parsed = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                parsed = {"_raw": str(msg.content)}
            returns.append({"name": msg.name, "result": parsed})
    return returns


# ─── Rule-based ────────────────────────────────────────────────────────


def eval_tool_efficiency(*, messages: list, expected_tool: str, **_) -> EvalScore:
    calls = _tool_calls(messages)
    if expected_tool == "none":
        passed = len(calls) == 0
        return EvalScore(
            name="tool_efficiency",
            value=1.0 if passed else 0.0,
            passed=passed,
            reason=("no tool calls expected" if passed else f"unexpected tool calls: {[c['name'] for c in calls]}"),
        )
    if not calls:
        return EvalScore("tool_efficiency", 0.0, False, f"expected {expected_tool}, got no tool calls")
    expected_seen = sum(1 for c in calls if c["name"] == expected_tool)
    other_seen = len(calls) - expected_seen
    if expected_seen == 0:
        return EvalScore(
            "tool_efficiency", 0.0, False,
            f"expected {expected_tool}, agent called {[c['name'] for c in calls]}",
        )
    # Allow multiple calls of the expected tool (e.g. comparison prompts) but
    # penalize calls of unexpected tools.
    value = expected_seen / (expected_seen + other_seen)
    return EvalScore(
        "tool_efficiency", value, value == 1.0,
        f"expected={expected_tool} expected_seen={expected_seen} other_seen={other_seen}",
    )


def eval_step_success_rate(*, messages: list, **_) -> EvalScore:
    returns = _tool_returns(messages)
    if not returns:
        return EvalScore("step_success_rate", 1.0, True, "no tool calls")
    errors = sum(1 for r in returns if isinstance(r["result"], dict) and "error" in r["result"])
    rate = (len(returns) - errors) / len(returns)
    return EvalScore(
        "step_success_rate", rate, rate == 1.0,
        f"{len(returns) - errors}/{len(returns)} tool calls succeeded",
    )


def eval_latency_under_sla(*, latency_ms: int, **_) -> EvalScore:
    passed = latency_ms <= LATENCY_SLA_MS
    return EvalScore(
        "latency_under_sla", float(latency_ms), passed,
        f"{latency_ms}ms (SLA {LATENCY_SLA_MS}ms)",
    )


# ─── LLM-as-judge ──────────────────────────────────────────────────────


_HELPFULNESS_RUBRIC = """Score the assistant's response on helpfulness, 0–100.
100: directly addresses the user's question with useful, actionable detail.
 80: addresses the question but missing minor detail or warmth.
 60: partial answer, requires the user to ask follow-ups for basics.
 40: tangentially related; misses the user's actual need.
 20: irrelevant, refuses without alternative, or rude.
  0: empty / unintelligible.

Use the full 0–100 range; intermediate scores are fine.

Reply with valid JSON: {"score": <integer 0–100>, "reason": "<one sentence>"}.
"""

_GROUNDEDNESS_RUBRIC = """Score the assistant's response on groundedness, 0–100.
You will see what the assistant returned and the JSON results from any
tools it called. Score:
100: every factual claim (prices, names, hours, items) is backed by a tool result.
 80: minor presentational paraphrasing, but no invented facts.
 60: one minor invented or unverifiable detail.
 40: multiple invented details, or contradicts a tool result.
 20: response invents most factual content; tools were ignored.
  0: response is mostly fabricated and inconsistent with the data.

If no factual claims need backing (e.g. policy explanations), score 100.

Use the full 0–100 range; intermediate scores are fine.

Reply with valid JSON: {"score": <integer 0–100>, "reason": "<one sentence>"}.
"""


def _judge_score(rubric: str, payload: str) -> tuple[float, str]:
    response = _judge().chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": rubric},
            {"role": "user", "content": payload},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    data = json.loads(response.choices[0].message.content or "{}")
    return float(data.get("score", 0)), str(data.get("reason", ""))


def eval_helpfulness(*, user_message: str, response: str, **_) -> EvalScore:
    payload = f"User: {user_message}\n\nAssistant: {response}"
    score, reason = _judge_score(_HELPFULNESS_RUBRIC, payload)
    return EvalScore("helpfulness", score, score >= HELPFULNESS_THRESHOLD, reason)


def eval_groundedness(
    *, user_message: str, response: str, messages: list, **_
) -> EvalScore:
    returns = _tool_returns(messages)
    payload = (
        f"User: {user_message}\n\n"
        f"Tool results:\n{json.dumps(returns, indent=2, default=str)}\n\n"
        f"Assistant: {response}"
    )
    score, reason = _judge_score(_GROUNDEDNESS_RUBRIC, payload)
    return EvalScore("groundedness", score, score >= GROUNDEDNESS_THRESHOLD, reason)


EVALUATORS = [
    eval_tool_efficiency,
    eval_step_success_rate,
    eval_latency_under_sla,
    eval_helpfulness,
    eval_groundedness,
]
