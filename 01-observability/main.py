"""Entry point. Run with: amp-instrument python main.py

The amp-instrument CLI wrapper auto-installs OTEL GenAI instrumentation
for LangChain (and most other agent frameworks) before this process
starts, then ships spans to the AMP collector specified by
AMP_OTEL_ENDPOINT. No tracing imports in agent code.
"""

import os

import uvicorn

from agent import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
