"""OAuth 2.0 token helpers for the agent.

Two flows:
- get_agent_token(): client_credentials grant. Agent acting alone.
- get_user_acting_token(user_token): RFC 8693 token exchange. Agent
  acting on behalf of a user; the user's identity ends up in the `act`
  claim of the issued token.

Both call IDP_TOKEN_ENDPOINT (mock IdP for the lab; Asgardeo in
production). Tokens are not cached for clarity — production code
should cache until ~30s before expiry.
"""

from __future__ import annotations

import os

import requests

IDP_TOKEN_ENDPOINT = os.environ.get(
    "IDP_TOKEN_ENDPOINT", "http://localhost:9700/oauth2/token"
)
AGENT_CLIENT_ID = os.environ.get("AGENT_CLIENT_ID", "grand-meridian-concierge")
AGENT_CLIENT_SECRET = os.environ.get("AGENT_CLIENT_SECRET", "agent-secret")


def get_agent_token(scope: str = "booking.write") -> str:
    response = requests.post(
        IDP_TOKEN_ENDPOINT,
        data={"grant_type": "client_credentials", "scope": scope},
        auth=(AGENT_CLIENT_ID, AGENT_CLIENT_SECRET),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_user_acting_token(user_token: str, scope: str = "booking.write") -> str:
    response = requests.post(
        IDP_TOKEN_ENDPOINT,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": user_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "scope": scope,
        },
        auth=(AGENT_CLIENT_ID, AGENT_CLIENT_SECRET),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]
