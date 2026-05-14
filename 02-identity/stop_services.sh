#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

for f in .pids.idp .pids.booking; do
  if [ -f "$f" ]; then
    pid=$(cat "$f")
    kill "$pid" 2>/dev/null || true
    rm -f "$f"
  fi
done
echo "Stopped."
