"""Mock IdP — mimics Asgardeo OAuth 2.0 token endpoints for the lab.

In production, replace with Asgardeo (https://wso2.com/asgardeo). The
endpoints here implement RFC 6749 (client_credentials grant) and RFC
8693 (token exchange) — the same standards Asgardeo speaks.

Endpoints:
  POST /oauth2/login   Issue a user JWT. Lab convenience; in production
                       this would be Asgardeo's interactive login flow.
  POST /oauth2/token   Issue agent tokens via:
                         - grant_type=client_credentials, or
                         - grant_type=urn:ietf:params:oauth:grant-type:token-exchange

JWTs are HS256-signed with a shared secret (IDP_SECRET) for lab
simplicity. Asgardeo uses RS256 with rotating keys advertised via JWKS.
"""

from __future__ import annotations

import base64
import os
import time

import jwt
from fastapi import FastAPI, Form, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ISSUER = "http://mock-idp.local"
SECRET = os.environ.get("IDP_SECRET", "dev-only-secret-do-not-use-in-production")
USER_AUDIENCE = "lab-resource-server"

# Pre-registered M2M client (the agent). In Asgardeo, this is created
# through the application registration UI.
CLIENTS: dict[str, dict] = {
    "grand-meridian-concierge": {
        "secret": "agent-secret",
        "scopes": {"booking.write"},
    },
}

app = FastAPI(title="Mock IdP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    user_id: str


@app.post("/oauth2/login")
def login(req: LoginRequest) -> dict:
    """Issue a user token without real authentication. Lab only."""
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "sub": req.user_id,
        "aud": USER_AUDIENCE,
        "iat": now,
        "exp": now + 3600,
        "scope": "openid profile",
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "Bearer", "expires_in": 3600}


def _verify_client(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("basic "):
        raise HTTPException(status_code=401, detail="Basic auth required")
    try:
        decoded = base64.b64decode(authorization.split(" ", 1)[1]).decode()
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Basic auth header")
    cid, _, csec = decoded.partition(":")
    if cid not in CLIENTS or CLIENTS[cid]["secret"] != csec:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    return cid


@app.post("/oauth2/token")
def token(
    grant_type: str = Form(...),
    scope: str = Form(""),
    subject_token: str | None = Form(None),
    subject_token_type: str | None = Form(None),
    authorization: str | None = Header(None),
) -> dict:
    client_id = _verify_client(authorization)
    requested = set(scope.split())
    granted = requested & CLIENTS[client_id]["scopes"]

    now = int(time.time())
    payload: dict = {
        "iss": ISSUER,
        "sub": client_id,
        "iat": now,
        "exp": now + 3600,
        "scope": " ".join(sorted(granted)),
        "client_id": client_id,
    }

    if grant_type == "client_credentials":
        # Agent acting alone. No `act` claim.
        pass

    elif grant_type == "urn:ietf:params:oauth:grant-type:token-exchange":
        # Agent acting on behalf of a user. Validate the subject token,
        # extract the user, and embed in the `act` claim per RFC 8693.
        if not subject_token:
            raise HTTPException(status_code=400, detail="subject_token required")
        try:
            user_claims = jwt.decode(
                subject_token,
                SECRET,
                algorithms=["HS256"],
                audience=USER_AUDIENCE,
            )
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=400, detail=f"Invalid subject_token: {e}")
        payload["act"] = {"sub": user_claims["sub"]}

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")

    access_token = jwt.encode(payload, SECRET, algorithm="HS256")
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": payload["scope"],
        "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "9700"))
    uvicorn.run(app, host="0.0.0.0", port=port)
