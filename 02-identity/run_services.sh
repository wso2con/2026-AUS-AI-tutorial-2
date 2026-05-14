#!/usr/bin/env bash
# Convenience launcher for the mock identity + booking services. Each
# runs in the background; PIDs are saved to .pids for stop_services.sh.
#
# Usage:
#   ./run_services.sh        # start IdP + booking
#   ./stop_services.sh       # tear down

set -euo pipefail
cd "$(dirname "$0")"

mkdir -p .logs

(cd mock_idp && python main.py > ../.logs/mock_idp.log 2>&1) &
echo $! > .pids.idp

(cd mock_booking && python main.py > ../.logs/mock_booking.log 2>&1) &
echo $! > .pids.booking

echo "Mock IdP:      http://localhost:9700  (logs: .logs/mock_idp.log)"
echo "Booking svc:   http://localhost:9001  (logs: .logs/mock_booking.log)"
echo "PIDs in .pids.idp / .pids.booking. Stop with ./stop_services.sh"
