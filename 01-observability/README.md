# Module 01 — Observability: OTEL GenAI traces

**Duration:** 12 min

Register the agent as an Externally-Hosted Agent in WSO2 Agent Manager and
run it under the `amp-instrument` wrapper. The wrapper auto-installs OTEL
GenAI instrumentation and ships spans to AM's collector. Agent code is
unchanged from module 00.

## Step 1 — Register the agent in AM

In AM:

1. Open the project that will own this agent — the default project is
   fine, or pick one of your own.
2. Click **Add Agent** and pick **Externally-Hosted Agent**.
3. Give the agent a name (`Grand Meridian Concierge`) and a short
   description.
4. Click **Register**.

AM displays setup instructions on the next screen with two values you'll
paste into `.env`:

- `AMP_OTEL_ENDPOINT` — the OTEL collector URL on your AM deployment.
- `AMP_AGENT_API_KEY` — a long-lived JWT the wrapper uses to authenticate
  the exporter.

## Step 2 — Configure env and install deps

```bash
cd 01-observability
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # pulls in amp-instrumentation

cp .env.example .env
# Edit .env — paste OPENAI_API_KEY, AMP_OTEL_ENDPOINT, AMP_AGENT_API_KEY from AM
set -a; source .env; set +a
```

## Step 3 — Run the agent

```bash
amp-instrument python main.py
```

Startup banner confirms the wrapper is exporting spans:

```
Traceloop exporting traces to http://localhost:22893/otel, authenticating with custom headers
...
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

In AM, navigate to **Observability → Traces**. The trace list is empty —
no requests yet.

## Step 4 — A simple prompt

Send a message that does not invoke any tools:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What time is it?", "session_id": "demo-1", "context": {}}' | jq
```

Refresh **Observability → Traces**. One trace appears. Click into it.

Click the `ChatOpenAI.chat` span. The right panel exposes three tabs:

- **Overview** — `Input Messages` block with System and User entries
  rendered as readable text.
- **Tools** — the tool catalog presented to the model
  (`check_room_availability`, `get_room_service_menu`,
  `get_local_recommendations`).
- **Attributes** — raw OTEL GenAI attributes:
  `gen_ai.request.model`, `gen_ai.usage.input_tokens` / `output_tokens`,
  `gen_ai.prompt.N.content`, `gen_ai.completion.N.content`, etc.

## Step 5 — A multi-tool prompt

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Compare a junior suite and the presidential suite for a 3-night stay",
       "session_id": "demo-2", "context": {}}' | jq
```

A new trace lands with a richer hierarchy — multiple `execute_task agent`
branches with their own `ChatOpenAI.chat` spans, plus tool-execution spans
for each `check_room_availability` call. Each tool span's **Attributes**
tab shows the arguments JSON in and the return JSON out. Each
`ChatOpenAI.chat` span's **Overview** tab shows the prompt + assistant
response, the **Tools** tab shows the tool catalog, and the **Attributes**
tab shows raw OTEL GenAI attributes including token counts.

## Or: try it in the browser

```bash
open web/index.html         # macOS; Linux: xdg-open web/index.html
```

Same widget as module 00. Every chat from the page produces a trace in AM
just like the curl examples do. The traces in **Observability → Traces**
contain the full LLM reasoning either way.

## Going further

- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [`amp-instrumentation` on PyPI](https://pypi.org/project/amp-instrumentation/)
- [WSO2 Agent Manager](https://wso2.com/agent-platform/agent-manager/)
