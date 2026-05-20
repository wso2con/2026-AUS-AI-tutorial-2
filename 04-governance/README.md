# Module 04 — Governance: Prompt-decorator guardrail at the LLM gateway

**Duration:** 12 min

Run the agent in two modes — *direct mode* (agent talks directly to OpenAI)
and *governed mode* (agent talks to OpenAI through AM's **LLM Service
Provider** with a prompt-decorator guardrail attached). Same agent code,
same prompt — the guardrail injects a pricing disclaimer when the
response touches pricing.

## Setup — install deps and seed `.env`

```bash
cd 04-governance
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — the AMP_OTEL_ENDPOINT / AMP_AGENT_API_KEY pair from
# module 01 is still required (this module produces traces too).
# Leave OPENAI_BASE_URL empty for now; we set it in step 3.
set -a && source .env && set +a
```

## Step 1 — No governance

Start the agent with `OPENAI_API_KEY` pointed directly at OpenAI:

```bash
unset OPENAI_BASE_URL    # ensure we are NOT going through AM
amp-instrument python main.py
```

Open the chat widget and ask about pricing:

```bash
open web/index.html         # macOS; Linux: xdg-open web/index.html
```

Type: *"What is the price difference between a standard room and a
deluxe suite?"* The reply comes back along the lines of:

```
A standard room is $280 per night and a deluxe suite is $340 per night,
so the deluxe suite is $60 more per night.
```

No disclaimer. Keep this tab open; we'll come back to it after switching
to governed mode.

<details>
<summary>Or via curl</summary>

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the price difference between a standard room and a deluxe suite?",
       "session_id":"ungoverned","context":{}}' | jq -r .response
```

</details>

## Step 2 — Configure an LLM Service Provider in AM

The LLM Service Provider (LSP) is an organization-level abstraction in AM.

1. **Add the provider.** In AM, navigate to **organization-level
   settings → LLM Service Providers → + Add Provider**. Pick OpenAI (or
   Anthropic / Bedrock; the shape is the same), supply the upstream
   credential. This is the only place the real OpenAI key lives.

2. **Attach a guardrail.** On the same provider, attach a **Prompt
   Decorator** guardrail with content along these lines:

   > If the response mentions pricing, room rates, or availability, append exactly one line at the end: *"Rates and availability subject to confirmation at time of booking."*

3. **Attach the LSP to the agent.** Open the agent you registered in
   module 01 (`Grand Meridian Concierge`) and pick this LSP from its
   configuration. AM now provides a per-agent **gateway URL** + a **JWT
   token** to authenticate against that gateway.

The agent never sees the real upstream credential.

## Step 3 — Switch to governed mode

Point the agent at AM's LLM Service Provider gateway by replacing the two
OpenAI env vars. The agent code does not change;
`_resolve_openai_config()` detects governed mode by the presence of
`OPENAI_BASE_URL` and rewires the OpenAI client to send the JWT on the
`API-Key` header.

```bash
export OPENAI_BASE_URL=https://YOUR-AM-DEPLOYMENT/projects/hospitality/llm-service-providers/openai/
export OPENAI_API_KEY=eyJhbGciOi...    # AM-issued JWT for the LSP, copy from the agent's settings page
amp-instrument python main.py
```

Go back to the widget tab from Step 1 and ask the same pricing question 
again. The reply now ends with the disclaimer:

```
A standard room is $280 per night and a deluxe suite is $340 per night,
so the deluxe suite is $60 more per night.

Rates and availability subject to confirmation at time of booking.
```

Same agent code, same prompt, same widget — only the gateway changed.

<details>
<summary>Or via curl</summary>

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the price difference between a standard room and a deluxe suite?",
       "session_id":"governed","context":{}}' | jq -r .response
```

</details>

## Step 4 — A non-pricing question

In the same widget tab, ask: *"What restaurants do you recommend
nearby?"* The reply comes back without the disclaimer. The decorator is
conditional — the model evaluates whether the trigger applies and
appends the disclaimer only when it does.

<details>
<summary>Or via curl</summary>

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What restaurants do you recommend nearby?",
       "session_id":"governed","context":{}}' | jq -r .response
```

</details>

## Going further

- [WSO2 Agent Manager LLM Service Provider](https://wso2.com/agent-platform/agent-manager/)
- [Azure AI Content Safety](https://azure.microsoft.com/en-us/products/ai-services/ai-content-safety) and [AWS Bedrock Guardrails](https://aws.amazon.com/bedrock/guardrails/)
