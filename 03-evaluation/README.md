# Module 03 — Evaluation: Eval-driven development

**Duration:** 12 min

Run the agent through a battery of evaluators — three rule-based (tool
efficiency, step success rate, latency under SLA) and two LLM-as-judge
(helpfulness, groundedness). Break the system prompt, watch the suite
catch the regression, fix it.

## Setup

```bash
cd 03-evaluation
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — paste OPENAI_API_KEY, AMP_OTEL_ENDPOINT, AMP_AGENT_API_KEY
# from AM (the values from module 01).
set -a && source .env && set +a
```

Eval runs are wrapped with `amp-instrument`, so every reference
conversation produces a trace in AM.

The eval suite lives in `evals/`:

- `conversations.py` — ten reference user messages with the tool each
  one is expected to (or expected NOT to) call.
- `evaluators.py` — five evaluators (detailed below).
- `run_eval.py` — orchestrator. Invokes the agent in-process for each
  conversation, runs every evaluator, prints a per-conversation table
  and an aggregate summary, exits non-zero if any aggregate pass-rate
  falls below `PASS_THRESHOLD` (default 80%).

### The evaluators

Each evaluator returns a numeric value, a pass/fail flag, and a one-line
reason. The five run on every reference conversation. Together they
cover **behavior** (did the agent do the right thing?), **quality**
(was the answer any good?), and **cost** (was it fast enough?). A single
metric is easy to game; the matrix is what catches regressions.

**Rule-based** — deterministic, no LLM cost, run on the message trail
and the latency clock:

- `tool_efficiency` — did the agent call the **expected** tool, and only
  that tool? Score is `expected_seen / (expected_seen + other_seen)`;
  passes at `1.0`. When `expected_tool` is `none`, passes only when zero
  tool calls were made. Multiple calls of the expected tool are allowed
  (comparison prompts often re-invoke the same tool); unexpected tools
  drag the score down.
- `step_success_rate` — of the tool calls made, how many returned a
  result without an `{"error": ...}` payload? Catches tool-side failures
  (bad arguments, unhandled cases) even when the agent's chat reply
  "sounds" fine. Passes at `1.0`.
- `latency_under_sla` — end-to-end wall time per turn. Passes when
  `<= LATENCY_SLA_MS` (default `8000`). Tracks operational regressions:
  a prompt change that doubles tokens shows up here before users
  complain.

**LLM-as-judge** — gpt-4o-mini (override via `JUDGE_MODEL`) scoring on a
0–100 rubric, `temperature=0.0` for repeatability, JSON-mode responses:

- `helpfulness` — did the response **actually answer** the user's
  question? Rubric anchors: 100 = directly addresses with actionable
  detail, 60 = partial answer requiring follow-up, 20 = irrelevant or
  rude. Passes at `>= HELPFULNESS_THRESHOLD` (default `80`). Sees the
  user message and the assistant response only — no tool results — so
  it scores presentation, not truth.
- `groundedness` — were factual claims (prices, names, hours, items)
  **backed by tool results**? The judge sees the user message, the JSON
  returns from every tool the agent invoked, and the final assistant
  response. Rubric anchors: 100 = every claim traceable, 60 = one minor
  invented detail, 20 = ignored tools entirely. Pure policy answers
  (no factual claims) score 100. Passes at `>= GROUNDEDNESS_THRESHOLD`
  (default `80`). This is the evaluator that catches fluent
  fabrication — high helpfulness with low groundedness is the
  pathology Step 2 demonstrates.

| Evaluator              | What it sees                   | What it catches                                  | Cost          |
|------------------------|--------------------------------|--------------------------------------------------|---------------|
| `tool_efficiency`      | Tool-call trail                | Agent skipping or substituting tools             | Free          |
| `step_success_rate`    | Tool return values             | Tool errors masked by smooth chat replies        | Free          |
| `latency_under_sla`    | Wall clock                     | Performance regressions from prompt/model drift  | Free          |
| `helpfulness`          | User msg + assistant response  | Off-topic, evasive, or low-effort answers        | 1 LLM call    |
| `groundedness`         | + tool results                 | Fluent fabrication; ignoring tool output         | 1 LLM call    |

The set is deliberately small and orthogonal — five complementary signals
beat fifteen overlapping ones. Add domain-specific evaluators
(price-accuracy, hours-accuracy, safety-policy) by appending to the
`EVALUATORS` list in `evaluators.py`; each one is a function that takes
the per-conversation context and returns an `EvalScore`.

## Step 1 — Baseline evaluation

Run the suite against the unmodified agent:

```bash
python -m evals.run_eval
```

Summary at the end looks roughly like:

```
=== Summary ===

  evaluator                   mean       p95   pass-rate
  ✓ eval_tool_efficiency       1.00      1.00        100%
  ✓ eval_step_success_rate     1.00      1.00        100%
  ✓ eval_latency_under_sla  2400.00   3200.00        100%
  ✓ eval_helpfulness          92.00     98.00        100%
  ✓ eval_groundedness         94.00    100.00        100%

PASS: all evaluators above threshold
```

LLM-judge scores are on a 0–100 scale; rule-based scores are on their
own native units (`1.00` for ratios, milliseconds for latency).

## Step 2 — Break the system prompt

`system_prompt.py` ships with a deliberately weakened `BROKEN_PROMPT`
variant. Switch to it via env var (no code edit, no agent restart):

```bash
SYSTEM_PROMPT_VARIANT=broken python -m evals.run_eval
```

Summary now looks roughly like:

```
  ✗ eval_tool_efficiency       0.30      1.00         30%   FAIL — agent skipped tools as instructed
  ✓ eval_step_success_rate     1.00      1.00        100%   (unchanged)
  ✓ eval_latency_under_sla  1689.20   2493.80        100%   (faster — no tool calls)
  ✓ eval_helpfulness          94.00    100.00        100%   PASS — fabricated responses still read as helpful
  ✗ eval_groundedness         38.00    100.00         30%   FAIL — invented data caught

FAIL: eval_tool_efficiency, eval_groundedness below 80% pass-rate threshold
```

Exit code is 1. `tool_efficiency` collapses because the agent obeyed
`BROKEN_PROMPT`'s instruction not to call tools. `groundedness` collapses
because the model filled the gap with invented prices, hours, and
amenities. `helpfulness` stays at 100% — fabricated responses still read
as complete, on-topic, useful answers.

## Step 3 — Read the judge's reasoning

The harness prints the judge's per-conversation reason directly in the
output. Find a row where `eval_tool_efficiency` or `eval_groundedness`
failed:

```
[q1_honeymoon_availability]  (1200ms)
  Q: Is the honeymoon suite available the first weekend in June?
  A: The Honeymoon Suite is available from around $480/night, featuring
     a private terrace and butler service.
  ✗ tool_efficiency        value=  0.00  expected check_room_availability, agent called []
  ✓ step_success_rate      value=  1.00  no tool calls
  ✓ latency_under_sla      value=1200.00  1200ms (SLA 8000ms)
  ✓ helpfulness            value= 95.00  Directly answers availability and adds relevant amenities
  ✗ groundedness           value= 20.00  Quoted $480 with no tool result backing it; the suite is $420 per the data
```

## Step 4 — Fix and verify

Run the baseline again (no env var override):

```bash
python -m evals.run_eval
# → all five aggregates pass again, exit 0
```

## Going further

- [G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment](https://arxiv.org/abs/2303.16634)
- [Hamel Husain — "Your AI product needs evals"](https://hamel.dev/blog/posts/evals/)
- [OpenAI Evals](https://github.com/openai/evals)
- [WSO2 Agent Manager evaluation](https://wso2.com/agent-platform/agent-manager/)
