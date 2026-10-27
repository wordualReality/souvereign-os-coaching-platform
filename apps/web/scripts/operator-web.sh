#!/usr/bin/env bash
# Local operator procedure for the static Next.js shell. It is not a hosted admission.
set -euo pipefail
set +m

root=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$root"

refuse_secret() {
  local name
  for name in DATABASE_URL SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY CORE_ACCESS_API_BASE CANONICAL_API_BASE; do
    if [[ -n "${!name:-}" ]]; then
      echo "REFUSED forbidden_env=$name" >&2
      exit 1
    fi
  done
}

if [[ "${1:-}" == "--refuse-check" ]]; then
  refuse_secret
  echo "REFUSE_CHECK_ALLOWED"
  exit 0
fi

if [[ ! -x node_modules/.bin/next ]]; then
  echo "next is not installed. Run npm ci from the repository root." >&2
  exit 2
fi

export NEXT_TELEMETRY_DISABLED=1
npm run web:build

work=$(mktemp -d)
pid=""
stop_tree() {
  local parent=$1
  local child
  for child in $(pgrep -P "$parent" || true); do
    stop_tree "$child"
  done
  kill -TERM "$parent" >/dev/null 2>&1 || true
}
cleanup() {
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    stop_tree "$pid"
    wait "$pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT

free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

start_renderer() {
  refuse_secret
  local port=$1
  env -i \
    PATH="$PATH" \
    HOME="${HOME:-/tmp}" \
    TMPDIR="${TMPDIR:-/tmp}" \
    NEXT_TELEMETRY_DISABLED=1 \
    ./node_modules/.bin/next start apps/web --hostname 127.0.0.1 --port "$port" >"$work/server.log" 2>&1 &
  pid=$!
  echo "$pid" >"$work/pid"
}

classify() {
  if [[ ! -s "$work/pid" ]]; then
    echo ABSENT
    return
  fi
  local recorded
  recorded=$(cat "$work/pid")
  if kill -0 "$recorded" >/dev/null 2>&1; then
    echo RUNNING
  else
    echo UNKNOWN
  fi
}

wait_ready() {
  local port=$1
  local i
  for i in $(seq 1 50); do
    if curl --silent --max-time 1 "http://127.0.0.1:${port}/" >/dev/null; then
      return 0
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return 1
    fi
    sleep 0.2
  done
  return 1
}

check_routes() {
  local port=$1
  local path code
  for path in / /coach/journeys /client/member-home /admin/provisioning; do
    code=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 5 "http://127.0.0.1:${port}${path}")
    echo "HTTP $code $path"
    [[ "$code" == "200" ]]
  done
}

port=$(free_port)
start_renderer "$port"
echo "START pid=$pid port=$port address=127.0.0.1 telemetry=disabled"
if ! wait_ready "$port"; then
  echo "renderer did not become ready" >&2
  cat "$work/server.log" >&2
  exit 1
fi
echo "CLASSIFY $(classify)"
check_routes "$port"
if ! grep -q "127.0.0.1:${port}" "$work/server.log"; then
  echo "renderer log does not show the loopback bind" >&2
  exit 1
fi

stop_tree "$pid"
set +e
wait "$pid"
stop_status=$?
set -e
echo "STOP_EXIT $stop_status"
[[ "$stop_status" == "143" ]]
closed=0
for _ in $(seq 1 50); do
  if ! curl --silent --max-time 1 "http://127.0.0.1:${port}/" >/dev/null; then
    closed=1
    break
  fi
  sleep 0.2
done
[[ "$closed" == "1" ]]
echo "CLASSIFY_AFTER_STOP $(classify)"
[[ "$(classify)" == "UNKNOWN" ]]

pid=""
port=$(free_port)
start_renderer "$port"
if ! wait_ready "$port"; then
  echo "restart did not become ready" >&2
  exit 1
fi
echo "RESTART http=200"
kill_tree_hard() {
  local parent=$1
  local child
  for child in $(pgrep -P "$parent" || true); do
    kill_tree_hard "$child"
  done
  kill -KILL "$parent" >/dev/null 2>&1 || true
}
kill_tree_hard "$pid"
set +e
wait "$pid"
crash_status=$?
set -e
echo "CRASH_EXIT $crash_status"
echo "CLASSIFY_AFTER_CRASH $(classify)"
[[ "$(classify)" == "UNKNOWN" ]]

pid=""
port=$(free_port)
start_renderer "$port"
if ! wait_ready "$port"; then
  echo "recovery did not become ready" >&2
  exit 1
fi
echo "RECOVERY http=200"
stop_tree "$pid"
set +e
wait "$pid"
set -e
pid=""

set +e
output=$(SUPABASE_SERVICE_ROLE_KEY=sentinel "$0" --refuse-check 2>&1)
status=$?
set -e
[[ "$status" != "0" ]]
[[ "$output" == *"REFUSED forbidden_env=SUPABASE_SERVICE_ROLE_KEY"* ]]
if grep -q "sentinel" <<<"$output"; then
  echo "secret value leaked into the refusal" >&2
  exit 1
fi
echo "REFUSED forbidden_env=SUPABASE_SERVICE_ROLE_KEY"
echo "PASS operator_web bind=127.0.0.1 routes=4 stop=$stop_status unknown=dead recovery=started telemetry=disabled secret=refused"
