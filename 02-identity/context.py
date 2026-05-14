"""Per-request context.

Used to pass the user's bearer token from the chat handler into tool
functions without threading it through every tool signature. Set per
chat request in agent.chat(); read in tools.book_room().
"""

import contextvars

USER_TOKEN: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_token", default=None
)
