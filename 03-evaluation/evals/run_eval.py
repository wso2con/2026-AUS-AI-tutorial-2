"""Run the eval suite against the agent.

Usage:
    python -m evals.run_eval                      # baseline prompt
    SYSTEM_PROMPT_VARIANT=broken python -m evals.run_eval

Invokes the agent in-process (no HTTP), runs every reference
conversation, runs every evaluator, and prints a summary table.

Exit code 0 if every aggregate pass-rate is ≥ pass-threshold
(see PASS_THRESHOLD). Non-zero otherwise — wire to CI as a quality gate.
"""

from __future__ import annotations

import os
import statistics
import sys
import time

from langchain_core.messages import HumanMessage

from agent import _get_agent, _final_text
from evals.conversations import REFERENCE_CONVERSATIONS
from evals.evaluators import EVALUATORS, EvalScore

PASS_THRESHOLD = float(os.environ.get("PASS_THRESHOLD", "0.8"))


def _run_one(convo: dict) -> dict:
    started = time.perf_counter()
    result = _get_agent().invoke({"messages": [HumanMessage(content=convo["user_message"])]})
    latency_ms = int((time.perf_counter() - started) * 1000)
    messages = result["messages"]
    response = _final_text(messages)
    return {
        "id": convo["id"],
        "user_message": convo["user_message"],
        "expected_tool": convo["expected_tool"],
        "response": response,
        "messages": messages,
        "latency_ms": latency_ms,
    }


def _format_score(s: EvalScore) -> str:
    flag = "✓" if s.passed else "✗"
    return f"  {flag} {s.name:22s} value={s.value:6.2f}  {s.reason[:80]}"


def main() -> int:
    variant = os.environ.get("SYSTEM_PROMPT_VARIANT", "baseline")
    print(f"\n=== Eval run :: SYSTEM_PROMPT_VARIANT={variant} ===\n")

    aggregate: dict[str, list[float]] = {ev.__name__: [] for ev in EVALUATORS}
    aggregate_passed: dict[str, list[bool]] = {ev.__name__: [] for ev in EVALUATORS}

    for convo in REFERENCE_CONVERSATIONS:
        run = _run_one(convo)
        print(f"[{run['id']}]  ({run['latency_ms']}ms)")
        print(f"  Q: {run['user_message']}")
        print(f"  A: {run['response'][:120]}{'...' if len(run['response']) > 120 else ''}")
        for ev in EVALUATORS:
            score = ev(**run)
            print(_format_score(score))
            aggregate[ev.__name__].append(score.value)
            aggregate_passed[ev.__name__].append(score.passed)
        print()

    print("=== Summary ===\n")
    print(f"  {'evaluator':24s}  {'mean':>8s}  {'p95':>8s}  {'pass-rate':>10s}")
    overall_failed = []
    for name in aggregate:
        values = aggregate[name]
        passes = aggregate_passed[name]
        mean = statistics.mean(values)
        try:
            p95 = statistics.quantiles(values, n=20)[18]
        except statistics.StatisticsError:
            p95 = mean
        pass_rate = sum(passes) / len(passes)
        flag = "✓" if pass_rate >= PASS_THRESHOLD else "✗"
        print(f"  {flag} {name:22s}  {mean:8.2f}  {p95:8.2f}  {pass_rate:10.0%}")
        if pass_rate < PASS_THRESHOLD:
            overall_failed.append(name)

    print()
    if overall_failed:
        print(f"FAIL: {', '.join(overall_failed)} below {PASS_THRESHOLD:.0%} pass-rate threshold")
        return 1
    print("PASS: all evaluators above threshold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
