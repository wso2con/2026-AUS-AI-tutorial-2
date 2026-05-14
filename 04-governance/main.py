"""Entry point. Run with: amp-instrument python main.py

amp-instrument auto-installs OTEL GenAI instrumentation before this
process starts and ships spans to AMP. No tracing code in this module.
"""

import os

import uvicorn

from agent import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
