# Module 02 — Identity: Agent identity + on-behalf-of token exchange

**Duration:** 10 min

Introduce a new tool, `book_room`, backed by a mock booking service.
First run uses a shared API key (the wrong pattern); then the agent gets
its own OAuth identity and exchanges a user token via RFC 8693 to call
the booking service as itself, on behalf of the user.

## Setup

The IdP and the booking service are mock FastAPI processes:

- `mock_idp/main.py` — `POST /oauth2/login` (issues user tokens) and
  `POST /oauth2/token` (RFC 6749 client_credentials + RFC 8693 token
  exchange). In production, replace with **Asgardeo**.
- `mock_booking/main.py` — `POST /bookings`. Validates the bearer token,
  requires the `booking.write` scope, logs the actor chain.

```bash
cd 02-identity
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r mock_idp/requirements.txt
pip install -r mock_booking/requirements.txt

cp .env.example .env
# Edit .env — paste OPENAI_API_KEY, AMP_OTEL_ENDPOINT, AMP_AGENT_API_KEY
# from AM (the values from module 01). The IDP_* / BOOKING_URL /
# AGENT_CLIENT_ID / AGENT_CLIENT_SECRET / IDP_SECRET defaults already
# match the local mocks and don't need editing.
set -a && source .env && set +a

./run_services.sh                                         # mock IdP (:9700) + booking (:9001) in background
amp-instrument python main.py                             # the agent (:8000); spans flow to AM
```

`./stop_services.sh` tears the mocks down. Logs are tailed at
`.logs/mock_idp.log` and `.logs/mock_booking.log`.

## Step 1 — The wrong way (shared credential)

`tools_shared_key.py` defines a `book_room` that reads a single static
API key from an env var and passes it to the booking service:

```python
def book_room(room_type: str, check_in: str, nights: int) -> dict:
    response = requests.post(
        f"{BOOKING_URL}/bookings",
        headers={"Authorization": f"Bearer {SHARED_API_KEY}"},
        json={"room_type": room_type, "check_in": check_in, "nights": nights},
    )
    return response.json()
```

Restart the agent in shared-key mode:

```bash
BOOKING_MODE=shared_key amp-instrument python main.py
```

Send a booking request through the agent, then tail the booking log:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Book the honeymoon suite for 2026-06-05, 2 nights",
       "session_id":"shared-key-1","context":{}}' | jq -r .response

grep -a BOOKING .logs/mock_booking.log | tail -1
# → BOOKING confirmed | caller=shared-agent-key | on_behalf_of=<unknown> | scopes=<unknown>
```

The booking service has no way to tell which agent ran this or which user
it was acting for.

## Step 2 — Register the agent at the IdP

In Asgardeo's Console:

1. Navigate to **Agents → + New Agent**.
2. Set the **Name** (`grand-meridian-concierge`) and an optional
   description.
3. Click **Register**. Asgardeo issues:
   - **Agent ID** — the OAuth `client_id`.
   - **Agent Secret** — shown only once on the success page; copy it
     immediately.
4. Grant the `booking.write` API scope through the API Authorization
   configuration.

For the lab, the mock IdP at `mock_idp/main.py` ships with this agent
pre-registered (see the `CLIENTS` dict). The credentials are in
`.env.example`:

```
AGENT_CLIENT_ID=grand-meridian-concierge       # would be the Agent ID in Asgardeo
AGENT_CLIENT_SECRET=agent-secret                # would be the Agent Secret in Asgardeo
```

**Reference:** [Register and manage AI agents in Asgardeo](https://wso2.com/asgardeo/docs/guides/agentic-ai/ai-agents/register-and-manage-agents/).

## Step 3 — The agent fetches its own token

Switch the agent back to identity mode (the default):

```bash
unset BOOKING_MODE
amp-instrument python main.py
```

`tools.py`'s `book_room` now goes through `identity.py`, which wraps the
OAuth client_credentials grant:

```python
def get_agent_token(scope: str = "booking.write") -> str:
    response = requests.post(
        IDP_TOKEN_ENDPOINT,
        data={"grant_type": "client_credentials", "scope": scope},
        auth=(AGENT_CLIENT_ID, AGENT_CLIENT_SECRET),
    )
    return response.json()["access_token"]
```

Send another booking request:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Book the deluxe suite for 2026-06-05, 1 night",
       "session_id":"agent-id-1","context":{}}' | jq -r .response

grep -a BOOKING .logs/mock_booking.log | tail -1
# → BOOKING confirmed | caller=grand-meridian-concierge | on_behalf_of=<none> | scopes=booking.write
```

## Step 4 — On-behalf-of via token exchange

The website that hosts the chat widget authenticates the guest to the
IdP and gets a user token, then passes it in the `context` field of the
chat request:

```bash
# Issue a user token for a fake guest "user-42":
USER_TOKEN=$(curl -s -X POST http://localhost:9700/oauth2/login \
  -H 'Content-Type: application/json' -d '{"user_id":"user-42"}' | jq -r .access_token)

# Send a chat request that carries the user token in context:
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d "{\"message\":\"Book the honeymoon suite for 2026-06-05, 2 nights\",
        \"session_id\":\"booking-1\",
        \"context\":{\"user_token\":\"$USER_TOKEN\"}}"
```

Inside the agent, `book_room` exchanges that user token for an
agent-acting-on-user token via `identity.get_user_acting_token`, which
calls the IdP's `/oauth2/token` with `grant_type=token-exchange`. The
response is a JWT with `sub=grand-meridian-concierge` (the agent) and
`act={sub: user-42}` (the user the agent is acting for).

The booking service log becomes:

```
BOOKING confirmed | caller=grand-meridian-concierge | on_behalf_of=user-42 | scopes=booking.write
```

## Step 5 — The audit chain in the trace

Re-open the trace for the booking conversation in AM's trace panel
(the `amp-instrument` wrapper from module 01 is still in effect). Click
into the `book_room` tool span. The tool's return value carries the audit
chain in-band:

```json
{
  "confirmation": "df36f3cc-0ff3-4e6d-8a9d-3c7629ce01b3",
  "actor": "grand-meridian-concierge",
  "on_behalf_of": "user-42"
}
```

- `actor` — the agent that signed the call to the booking service.
- `on_behalf_of` — the user the agent was acting for, sourced from the
  `act` claim in the token-exchange JWT.
- `confirmation` — ties this booking to a specific reservation record.

## Going further

- [RFC 8693 — OAuth 2.0 Token Exchange](https://datatracker.ietf.org/doc/html/rfc8693)
- [Register and manage AI agents in Asgardeo](https://wso2.com/asgardeo/docs/guides/agentic-ai/ai-agents/register-and-manage-agents/)
- [WSO2 Agent Manager](https://wso2.com/agent-manager)
