# Evolving Your Enterprise Architecture for the Agentic Era 

**WSO2 Conference 2026 — Lab session**

## Tutorial Plan
```
00 — Baseline        A traditional agent deployment.
01 — Observability   OTEL GenAI traces in AM.
02 — Identity        Agent identity + on-behalf-of token exchange.
03 — Evaluation      Eval-driven development (rule + LLM-judge).
04 — Governance      Prompt-decorator guardrail at the LLM gateway.
```

## The use case

<img width="1253" height="374" alt="Screenshot 2026-05-19 at 13 55 29" src="https://github.com/user-attachments/assets/d2b94bdc-f874-4b02-b920-fcee4c95f619" />


A hotel concierge agent for *The Grand Meridian*, built on LangGraph +
FastAPI + OpenAI (~300 LOC). Three tools backed by static hotel data:

- `check_room_availability(room_type, check_in, nights)`
- `get_room_service_menu(meal)`
- `get_local_recommendations(category)`

The same `agent.py` is reused unchanged across every module.

## Prerequisites

- **Python 3.11 or 3.12.** Avoid 3.13 / 3.14. macOS: `brew install python@3.11`.
- **WSO2 Agent Manager instance** with permission to register an
  Externally-Hosted Agent and read its trace panel. Modules 01–04 need
  AM env vars; module 00 runs without AM. The fastest path is to sign
  up for the cloud version at
  [console.agent-manager.cloud.wso2.com](https://console.agent-manager.cloud.wso2.com).
- An OpenAI API key (`OPENAI_API_KEY=sk-...`).
- A clone of this repo.

```bash
git clone <repo-url> ai-lab-2026
```

