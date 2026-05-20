#!/usr/bin/env bash
# Convenience launcher for the mock identity + booking services. Each
# runs in the background under `exec`, so the recorded PID is the
# python process itself (not a parent subshell). stop_services.sh
# kills those PIDs directly.
#
# Usage:
#   ./run_services.sh        # start IdP + booking
#   ./stop_services.sh       # tear down

set -euo pipefail
cd "$(dirname "$0")"

mkdir -p .logs

# `exec` replaces the subshell with python, so $! is the python PID.
# Without exec, $! would be the subshell — killing it can leave python
# orphaned, still holding the port.
( cd mock_idp && exec python main.py ) > .logs/mock_idp.log 2>&1 &
echo "$!" > .pids.idp

( cd mock_booking && exec python main.py ) > .logs/mock_booking.log 2>&1 &
echo "$!" > .pids.booking

# Give the services a moment to bind or fail (port in use, import
# error, missing deps), then verify both are still alive.
sleep 1
fail=0
for name in idp booking; do
  pid=$(cat ".pids.$name" 2>/dev/null || echo "")
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    echo "ERROR: mock_$name failed to start. See .logs/mock_$name.log" >&2
    fail=1
  fi
done
if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "Mock IdP:      http://localhost:9700  (logs: .logs/mock_idp.log)"
echo "Booking svc:   http://localhost:9001  (logs: .logs/mock_booking.log)"
echo "PIDs in .pids.idp / .pids.booking. Stop with ./stop_services.sh"
