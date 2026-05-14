"""Wrong-way tools for module 02, step 1 of the walkthrough.

Same three read-only tools, plus a book_room that uses a single hardcoded
shared API key. The booking service log will show this caller as
`shared-agent-key` with no on_behalf_of attribution — exactly the gap
the rest of the module fixes.

Activate with BOOKING_MODE=shared_key when running the agent.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from langchain_core.tools import tool

from hotel_data import ROOMS
from tools import (
    check_room_availability,
    get_local_recommendations,
    get_room_service_menu,
)

BOOKING_URL = os.environ.get("BOOKING_URL", "http://localhost:9001")
SHARED_API_KEY = os.environ.get("BOOKING_SHARED_KEY", "shared-agent-key")


def book_room(room_type: str, check_in: str, nights: int) -> dict[str, Any]:
    """Book a room. Wrong way: shared static API key, no per-agent attribution."""
    if room_type not in ROOMS:
        return {"error": f"Unknown room type. Available: {', '.join(ROOMS.keys())}."}

    response = requests.post(
        f"{BOOKING_URL}/bookings",
        headers={"Authorization": f"Bearer {SHARED_API_KEY}"},
        json={"room_type": room_type, "check_in": check_in, "nights": nights},
        timeout=10,
    )
    if response.status_code >= 400:
        return {
            "error": f"Booking service returned {response.status_code}",
            "detail": response.text,
        }
    return response.json()


LANGCHAIN_TOOLS = [
    tool(check_room_availability),
    tool(get_room_service_menu),
    tool(get_local_recommendations),
    tool(book_room),
]
