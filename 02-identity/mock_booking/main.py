"""Mock booking service — validates JWT, logs the actor chain.

Two paths supported, in this order:
1. Bearer token == BOOKING_SHARED_KEY: legacy shared-key path. Used by
   tools_shared_key.py for module 02 step 1 (the "wrong way" demo).
2. Otherwise: validate as JWT signed by the mock IdP. Require the
   booking.write scope. Log the agent (sub) and the user the agent is
   acting for (act.sub).
"""

from __future__ import annotations

import logging
import os
import uuid

import jwt
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("booking")

SECRET = os.environ.get("IDP_SECRET", "dev-only-secret-do-not-use-in-production")
SHARED_API_KEY = os.environ.get("BOOKING_SHARED_KEY", "shared-agent-key")
REQUIRED_SCOPE = "booking.write"

app = FastAPI(title="Mock Booking Service")


class BookingRequest(BaseModel):
    room_type: str
    check_in: str
    nights: int


@app.post("/bookings")
def book(req: BookingRequest, authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    raw = authorization.split(" ", 1)[1]

    if raw == SHARED_API_KEY:
        log.info(
            "BOOKING confirmed | caller=shared-agent-key | on_behalf_of=<unknown> | scopes=<unknown>"
        )
        return {
            "confirmation": str(uuid.uuid4()),
            "actor": "shared-agent-key",
            "on_behalf_of": None,
        }

    try:
        claims = jwt.decode(raw, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    scopes = set(claims.get("scope", "").split())
    if REQUIRED_SCOPE not in scopes:
        raise HTTPException(
            status_code=403, detail=f"Missing scope: {REQUIRED_SCOPE}"
        )

    actor = claims.get("sub")
    on_behalf_of = (claims.get("act") or {}).get("sub")
    log.info(
        "BOOKING confirmed | caller=%s | on_behalf_of=%s | scopes=%s",
        actor,
        on_behalf_of or "<none>",
        ",".join(sorted(scopes)),
    )
    return {
        "confirmation": str(uuid.uuid4()),
        "actor": actor,
        "on_behalf_of": on_behalf_of,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "9001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
