#!/usr/bin/env bash
# Starts the packaged Arcava JAR, checks the closed loopback lifecycle, then stops it.
set -euo pipefail

jar_path=${1:?usage: jar-lifecycle-smoke.sh path-to-executable-jar}
if [[ ! -f "$jar_path" ]]; then
  echo "jar missing: $jar_path" >&2
  exit 2
fi

manifest=$(unzip -p "$jar_path" META-INF/MANIFEST.MF | tr -d '\r')
grep -q 'Main-Class: org.springframework.boot.loader.launch.JarLauncher' <<<"$manifest"
grep -q 'Start-Class: com.projectb.api.Application' <<<"$manifest"
grep -q 'Spring-Boot-Version: 4.1.1' <<<"$manifest"
echo "MANIFEST_OK main=JarLauncher start=com.projectb.api.Application boot=4.1.1"
if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$jar_path"
else
  sha256sum "$jar_path"
fi

work=$(mktemp -d)
refuse_pid=""
cleanup() {
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill -TERM "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "${refuse_pid}" ]] && kill -0 "$refuse_pid" >/dev/null 2>&1; then
    kill -TERM "$refuse_pid" >/dev/null 2>&1 || true
    wait "$refuse_pid" >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT

journal="$work/journal.ndjson"
: >"$journal"
before=$(cksum "$journal")

free_port() {
  python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

start_jar() {
  local port=$1
  local log=$2
  shift 2
  java -jar "$jar_path" \
    --spring.profiles.active=dev \
    --server.address=127.0.0.1 \
    --server.port="$port" \
    --arcava.journal.path="$journal" \
    "$@" >"$log" 2>&1 &
  pid=$!
  echo "PID $pid PORT $port"
  local i
  for i in $(seq 1 50); do
    if grep -q "Tomcat started on port $port" "$log"; then
      return 0
    fi
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "process exited before listen" >&2
      cat "$log" >&2
      return 1
    fi
    sleep 0.1
  done
  echo "listener timeout" >&2
  cat "$log" >&2
  return 1
}

stop_jar() {
  kill -TERM "$pid"
  local status=0
  set +e
  wait "$pid"
  status=$?
  set -e
  pid=""
  echo "STOP_EXIT $status"
  if [[ "$status" -ne 0 && "$status" -ne 143 ]]; then
    echo "unexpected stop status $status" >&2
    return 1
  fi
}

# A denial body on HTTP 200 is not a closed route. The status is the oracle.
deny_status_closed() {
  local code=$1
  local body=$2
  if [[ "$code" == "200" ]]; then
    return 1
  fi
  [[ "$code" == "403" ]] || return 1
  grep -q 'LIVE_AUTHORITY_CLOSED' <<<"$body"
}

if deny_status_closed 200 '{"error":{"code":"LIVE_AUTHORITY_CLOSED"}}'; then
  echo "oracle accepted an http 200 denial body" >&2
  exit 1
fi
echo "ORACLE_HTTP200_WITH_DENIAL_BODY_FAILS"

check_http() {
  local port=$1
  local live_code ready denied_code denied absent
  live_code=$(curl --silent --show-error --output "$work/live.body" --write-out '%{http_code}' --max-time 3 \
    "http://127.0.0.1:${port}/health/live")
  echo "LIVE_HTTP $live_code"
  [[ "$live_code" == "200" ]]
  grep -q 'ACTIVE_DEV_HTTP' "$work/live.body"
  grep -q '"live_authority":"closed"' "$work/live.body"
  if grep -q 'NON_WEB_INACTIVE_BOOTSTRAP' "$work/live.body"; then
    return 1
  fi
  ready=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 3 \
    "http://127.0.0.1:${port}/health/ready")
  echo "READY $ready"
  [[ "$ready" == "503" ]]
  absent=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 3 \
    -X POST "http://127.0.0.1:${port}/project-b/v1/tenants/11111111-1111-4111-8111-111111111111/producers/CT-ARC-003" \
    -H 'content-type: application/json' \
    --data '{"consent_verified":true}')
  echo "ABSENT_BEARER $absent"
  [[ "$absent" == "401" ]]
  denied_code=$(curl --silent --show-error --output "$work/denied.body" --write-out '%{http_code}' --max-time 3 \
    -X POST "http://127.0.0.1:${port}/project-b/v1/tenants/11111111-1111-4111-8111-111111111111/producers/CT-ARC-004" \
    -H 'authorization: Bearer coach-a' \
    -H 'content-type: application/json' \
    --data '{"consent_verified":true,"publication_state":"PUBLISHED","runtime_session_refs":["sov-session"],"forged-grant":true}')
  denied=$(cat "$work/denied.body")
  echo "DENIED_HTTP $denied_code"
  echo "DENIED $denied"
  deny_status_closed "$denied_code" "$denied"
  if grep -q 'sov-session' <<<"$denied" || grep -q 'forged-grant' <<<"$denied"; then
    return 1
  fi
}

port=$(free_port)
start_jar "$port" "$work/first.log"
check_http "$port"
after=$(cksum "$journal")
[[ "$before" == "$after" ]]
echo "JOURNAL_UNCHANGED $after"
stop_jar
if curl --silent --max-time 2 "http://127.0.0.1:${port}/health/live"; then
  echo "listener still answered after stop" >&2
  exit 1
fi

port=$(free_port)
start_jar "$port" "$work/second.log"
check_http "$port"
restarted=$(cksum "$journal")
[[ "$before" == "$restarted" ]]
echo "RESTART_JOURNAL_UNCHANGED $restarted"
stop_jar

refuse_log="$work/refuse.log"
java -jar "$jar_path" \
  --spring.profiles.active=dev \
  --server.address=0.0.0.0 \
  --server.port="$(free_port)" \
  --arcava.journal.path="$work/refuse.ndjson" \
  >"$refuse_log" 2>&1 &
refuse_pid=$!
refuse_done=0
for _ in $(seq 1 50); do
  if ! kill -0 "$refuse_pid" >/dev/null 2>&1; then
    refuse_done=1
    break
  fi
  sleep 0.2
done
if [[ "$refuse_done" -ne 1 ]]; then
  echo "NON_LOOPBACK_TIMEOUT bound=10s" >&2
  exit 1
fi
set +e
wait "$refuse_pid"
refuse_status=$?
set -e
refuse_pid=""
echo "NON_LOOPBACK_EXIT $refuse_status"
[[ "$refuse_status" -ne 0 ]]
grep -q 'non-loopback' "$refuse_log"
echo "PASS jar_lifecycle live_http=200 ready_http=503 denied_http=403 absent_http=401 journal=unchanged stop=terminated restart=closed nonloopback_bounded=10s"
