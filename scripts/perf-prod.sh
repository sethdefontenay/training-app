#!/usr/bin/env bash
# Latency profiler for prod. Single-user app, so this measures per-request
# response time (TTFB), NOT load/concurrency — that's what makes pages feel slow.
#
# Usage:
#   railway link -p profound-connection         # once, to link the project
#   ./scripts/perf-prod.sh                       # logs in via SEED_* and times the pages
#   BASE=https://your-host TOKEN=ey... ./scripts/perf-prod.sh   # bring your own token
#
# Reads the "network floor" from /health (no DB, no auth): anything close to that
# number is network-bound (region/distance); anything well above it is server-side work.
set -euo pipefail

BASE="${BASE:-https://training-app-production-e048.up.railway.app}"
HITS="${HITS:-3}"

# Token: use $TOKEN if given, else log in with Railway's SEED_* creds.
TOKEN="${TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  EMAIL=$(railway variables --service training-app --json | python3 -c "import sys,json;print(json.load(sys.stdin)['SEED_EMAIL'])")
  PASS=$(railway variables --service training-app --json | python3 -c "import sys,json;print(json.load(sys.stdin)['SEED_PASSWORD'])")
  TOKEN=$(curl -s -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
fi
AUTH="Authorization: Bearer $TOKEN"
TODAY=$(date +%Y-%m-%d)

ttfb () { curl -s -o /dev/null -w '%{time_starttransfer}' "$@"; }

FLOOR=$(ttfb "$BASE/health")
printf 'network floor (/health, no DB): %ss\n\n' "$FLOOR"
printf '%-34s %s\n' "endpoint" "TTFB (x$HITS)"
printf '%-34s %s\n' "--------" "------------"

time_endpoint () { # $1=label $2=path
  printf '%-34s' "$1"
  for _ in $(seq 1 "$HITS"); do printf '%ss ' "$(ttfb -H "$AUTH" "$BASE$2")"; done
  echo
}

time_endpoint "/daily/today (Today + Workout)" "/api/v1/daily/$TODAY"
time_endpoint "/sessions (workout history)"    "/api/v1/sessions"
time_endpoint "/check-ins"                      "/api/v1/check-ins"
time_endpoint "/plans/current"                  "/api/v1/plans/current"
time_endpoint "/tracking/measurements"          "/api/v1/tracking/measurements"
