# Module 00 — Baseline: A traditional agent deployment

**Duration:** 5 min

A hotel concierge agent for *The Grand Meridian*, built on LangGraph +
OpenAI's tool-calling API. One endpoint:

```
POST /chat   { "message": str, "session_id": str, "context": {} }
         →   { "response": str }
```

Three tools: `check_room_availability`, `get_room_service_menu`,
`get_local_recommendations`. A unit-test suite covers each tool's pure
logic.

## Run it

```bash
cd 00-baseline
python3.11 -m venv .venv && source .venv/bin/activate    # 3.11 or 3.12; avoid 3.13/3.14
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python main.py
# → listening on http://localhost:8000
```

## Smoke test

Open the chat widget:

```bash
open web/index.html         # macOS; Linux: xdg-open web/index.html
```

The landing page for The Grand Meridian loads. Click the launcher in
the bottom-right corner, then pick a chip ("Check availability", "Room
service", "Things to do nearby") or type a question of your own. The
agent replies in the chat panel.

<details>
<summary>Or via curl</summary>

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Is the honeymoon suite available the first weekend in June?",
       "session_id": "smoke-1", "context": {}}' | jq
```

</details>

## Multi-tool prompt (used in module 01)

In the widget, type: *"Compare a junior suite and the presidential
suite for a 3-night stay."*

Server logs show one inbound HTTP request and one outbound response —
the two tool calls and the model's reasoning in between are not visible.
Module 01 fixes that.

<details>
<summary>Or via curl</summary>

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Compare a junior suite and the presidential suite for a 3-night stay",
       "session_id": "crack-1", "context": {}}' | jq
```

</details>
