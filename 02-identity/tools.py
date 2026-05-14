"""Hotel concierge tools — module 02 (identity).

The three read-only tools (room availability, room service menu, local
recommendations) are unchanged from module 00. The new book_room tool
demonstrates the agent identity pattern: the agent fetches its own token
from the IdP via OAuth 2.0 client_credentials, and — if the chat request
carries a user token in context — exchanges that user token (RFC 8693)
to produce an agent-acting-on-user token before calling the booking
service.

For the wrong-way demo (shared static API key), see tools_shared_key.py
and run the agent with BOOKING_MODE=shared_key.
"""

from __future__ import annotations

import os
import re
from typing import Any

import requests
from langchain_core.tools import tool

from context import USER_TOKEN
from hotel_data import MENU, RECOMMENDATIONS, ROOMS
from identity import get_agent_token, get_user_acting_token

BOOKING_URL = os.environ.get("BOOKING_URL", "http://localhost:9001")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_room_availability(
    room_type: str,
    check_in: str | None = None,
    nights: int | None = None,
) -> dict[str, Any]:
    """Check availability and price for hotel rooms.

    Args:
        room_type: One of: honeymoon, deluxe, standard, junior, presidential.
        check_in: Check-in date (YYYY-MM-DD). Optional.
        nights: Number of nights. Optional, defaults to 1.
    """
    if not isinstance(room_type, str) or room_type not in ROOMS:
        return {"error": f"Unknown room type. Available: {', '.join(ROOMS.keys())}."}
    if check_in is not None and not _ISO_DATE.match(check_in):
        return {"error": "Check-in date must be in YYYY-MM-DD format."}
    n = 1 if nights is None else nights
    if not isinstance(n, int) or n < 1 or n > 30:
        return {"error": "Nights must be an integer between 1 and 30."}

    room = ROOMS[room_type]
    return {
        "room_type": room_type,
        "name": room["name"],
        "price_per_night_usd": room["price_per_night_usd"],
        "nights": n,
        "total_usd": room["price_per_night_usd"] * n,
        "size_sqft": room["size_sqft"],
        "description": room["description"],
        "available": True,
        "check_in": check_in,
    }


def get_room_service_menu(vegetarian_only: bool | None = None) -> dict[str, Any]:
    """Return the room service menu.

    Args:
        vegetarian_only: Filter to vegetarian items only. Optional.
    """
    veg = bool(vegetarian_only)
    items = [m for m in MENU if (not veg) or m["vegetarian"]]
    return {
        "items": items,
        "filtered": "vegetarian_only" if veg else "none",
        "count": len(items),
    }


def get_local_recommendations(category: str) -> dict[str, Any]:
    """Return curated recommendations near the hotel by category.

    Args:
        category: One of: restaurants, family, nightlife, outdoors.
    """
    if not isinstance(category, str) or category not in RECOMMENDATIONS:
        return {
            "error": f"Unknown category. Available: {', '.join(RECOMMENDATIONS.keys())}."
        }
    return {
        "category": category,
        "recommendations": RECOMMENDATIONS[category],
        "count": len(RECOMMENDATIONS[category]),
    }


def book_room(room_type: str, check_in: str, nights: int) -> dict[str, Any]:
    """Book a room. Requires booking.write scope at the IdP.

    Args:
        room_type: One of: honeymoon, deluxe, standard, junior, presidential.
        check_in: Check-in date (YYYY-MM-DD).
        nights: Number of nights (1-30).
    """
    if room_type not in ROOMS:
        return {"error": f"Unknown room type. Available: {', '.join(ROOMS.keys())}."}
    if not _ISO_DATE.match(check_in or ""):
        return {"error": "Check-in date must be YYYY-MM-DD."}
    if not isinstance(nights, int) or nights < 1 or nights > 30:
        return {"error": "Nights must be 1-30."}

    user_token = USER_TOKEN.get()
    token = (
        get_user_acting_token(user_token) if user_token else get_agent_token()
    )

    response = requests.post(
        f"{BOOKING_URL}/bookings",
        headers={"Authorization": f"Bearer {token}"},
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
