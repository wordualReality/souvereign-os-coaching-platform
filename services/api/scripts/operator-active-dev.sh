#!/usr/bin/env bash
# Local operator procedure for the active dev JAR. It is not a hosted admission.
set -euo pipefail
set +m

jar=${1:-}
if [[ -z "$jar" || ! -f "$jar" ]]; then
  echo "usage: operator-active-dev.sh <jar>" >&2
  exit 2
fi

root=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$root"
python3 scripts/validate_effective_config.py --self-check

work=$(mktemp -d)
pid=""
cleanup() {
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill -TERM "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT

free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

wait_ready() {
  local port=$1
  local i
  for i in $(seq 1 75); do
    if curl --silent --max-time 1 "http://127.0.0.1:${port}/health/live" >/dev/null; then
      return 0
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return 1
    fi
    sleep 0.2
  done
  return 1
}

start_listener() {
  local port=$1
  local journal=$2
  local address=$3
  java -jar "$jar" \
    --spring.profiles.active=dev \
    --server.address="$address" \
    --server.port="$port" \
    --arcava.journal.path="$journal" >"$work/server.log" 2>&1 &
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

journal=$(mktemp)
port=$(free_port)
before=$(cksum "$journal")
start_listener "$port" "$journal" "127.0.0.1"
echo "START pid=$pid port=$port address=127.0.0.1"
if ! wait_ready "$port"; then
  echo "listener did not become ready" >&2
  cat "$work/server.log" >&2
  exit 1
fi
echo "CLASSIFY $(classify)"

live=$(curl --silent --show-error --output "$work/live.body" --write-out '%{http_code}' --max-time 5 "http://127.0.0.1:${port}/health/live")
ready=$(curl --silent --show-error --output "$work/ready.body" --write-out '%{http_code}' --max-time 5 "http://127.0.0.1:${port}/health/ready")
echo "LIVE_HTTP $live"
echo "READY_HTTP $ready"
[[ "$live" == "200" ]]
[[ "$ready" == "503" ]]
grep -q '"live_authority":"closed"' "$work/ready.body"

curl --silent --show-error --max-time 5 "http://127.0.0.1:${port}/health/effective" >"$work/effective.json"
python3 - "$journal" "$work/effective.json" <<'PY'
import hashlib, json, sys
path, payload = sys.argv[1], sys.argv[2]
body = json.load(open(payload))
digest = hashlib.sha256(path.encode()).hexdigest()
if body.get("ARCAVA_JOURNAL_PATH_SHA256") != digest:
    sys.exit("effective journal hash mismatch")
if path in json.dumps(body):
    sys.exit("journal path leaked into effective readback")
if body.get("e1_authority") != "NOT_ADMITTED" or body.get("e1_reason") != "LIVE_AUTHORITY_CLOSED":
    sys.exit("e1 authority is not admitted on this listener")
if body.get("piac_transport") != "not_connected" or body.get("kdb_transport") != "not_connected":
    sys.exit("live transport is not connected")
candidate = {
    "SERVER_ADDRESS": body["SERVER_ADDRESS"],
    "SERVER_PORT": body["SERVER_PORT"],
    "ARCAVA_JOURNAL_PATH": path,
    "ARCAVA_RUNTIME_ROLE": body["ARCAVA_RUNTIME_ROLE"],
    "SPRING_PROFILES_ACTIVE": body["SPRING_PROFILES_ACTIVE"],
}
json.dump(candidate, open(payload + ".candidate", "w"))
PY
python3 scripts/validate_effective_config.py "$work/effective.json.candidate" >/dev/null
echo "EFFECTIVE schema=pass journal=redacted address=127.0.0.1"
echo "E1 authority=NOT_ADMITTED reason=LIVE_AUTHORITY_CLOSED"

kill -TERM "$pid"
set +e
wait "$pid"
stop_status=$?
set -e
pid=""
echo "STOP_EXIT $stop_status"
[[ "$stop_status" == "143" ]]
if curl --silent --max-time 2 "http://127.0.0.1:${port}/health/live" >/dev/null; then
  echo "listener still answered after stop" >&2
  exit 1
fi
[[ "$(cksum "$journal")" == "$before" ]]
echo "CLASSIFY_AFTER_STOP $(classify)"
[[ "$(classify)" == "UNKNOWN" ]]
echo "UNKNOWN journal=unchanged"

port=$(free_port)
start_listener "$port" "$journal" "127.0.0.1"
if ! wait_ready "$port"; then
  echo "restart did not become ready" >&2
  exit 1
fi
restart_live=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 5 "http://127.0.0.1:${port}/health/live")
echo "RESTART_HTTP $restart_live"
[[ "$restart_live" == "200" ]]
[[ "$(cksum "$journal")" == "$before" ]]

kill -KILL "$pid"
set +e
wait "$pid"
crash_status=$?
set -e
echo "CRASH_EXIT $crash_status"
[[ "$(classify)" == "UNKNOWN" ]]
[[ "$(cksum "$journal")" == "$before" ]]
pid=""
port=$(free_port)
start_listener "$port" "$journal" "127.0.0.1"
if ! wait_ready "$port"; then
  echo "recovery did not become ready" >&2
  exit 1
fi
echo "RECOVERY journal=unchanged http=200"
[[ "$(cksum "$journal")" == "$before" ]]
kill -TERM "$pid"
set +e
wait "$pid"
set -e
pid=""

refuse_port=$(free_port)
start_listener "$refuse_port" "$journal" "0.0.0.0"
refuse_pid=$pid
bounded=0
for _ in $(seq 1 50); do
  if ! kill -0 "$refuse_pid" >/dev/null 2>&1; then
    bounded=1
    break
  fi
  sleep 0.2
done
if [[ "$bounded" -ne 1 ]]; then
  kill -KILL "$refuse_pid" >/dev/null 2>&1 || true
  echo "NON_LOOPBACK_TIMEOUT bound=10s" >&2
  exit 1
fi
set +e
wait "$refuse_pid"
refuse_status=$?
set -e
pid=""
echo "NON_LOOPBACK_EXIT $refuse_status"
[[ "$refuse_status" != "0" ]]
if curl --silent --max-time 2 "http://127.0.0.1:${refuse_port}/health/live" >/dev/null; then
  echo "non-loopback listener answered" >&2
  exit 1
fi

blank_port=$(free_port)
start_listener "$blank_port" "" "127.0.0.1"
blank_pid=$pid
blank_bounded=0
for _ in $(seq 1 50); do
  if ! kill -0 "$blank_pid" >/dev/null 2>&1; then
    blank_bounded=1
    break
  fi
  sleep 0.2
done
if [[ "$blank_bounded" -ne 1 ]]; then
  kill -KILL "$blank_pid" >/dev/null 2>&1 || true
  echo "BLANK_JOURNAL_TIMEOUT bound=10s" >&2
  exit 1
fi
set +e
wait "$blank_pid"
blank_status=$?
set -e
pid=""
echo "BLANK_JOURNAL_EXIT $blank_status"
[[ "$blank_status" != "0" ]]
echo "PASS operator_active_dev start=127.0.0.1 ready=503 stop=$stop_status unknown=dead recovery=journal_unchanged nonloopback=$refuse_status blank_journal=$blank_status"
