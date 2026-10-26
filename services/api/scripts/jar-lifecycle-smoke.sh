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
cleanup() {
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill -TERM "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
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

check_http() {
  local port=$1
  local live ready denied absent
  live=$(curl --silent --show-error --max-time 3 "http://127.0.0.1:${port}/health/live")
  echo "LIVE $live"
  grep -q 'ACTIVE_DEV_HTTP' <<<"$live"
  grep -q '"live_authority":"closed"' <<<"$live"
  if grep -q 'NON_WEB_INACTIVE_BOOTSTRAP' <<<"$live"; then
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
  denied=$(curl --silent --show-error --max-time 3 \
    -X POST "http://127.0.0.1:${port}/project-b/v1/tenants/11111111-1111-4111-8111-111111111111/producers/CT-ARC-004" \
    -H 'authorization: Bearer coach-a' \
    -H 'content-type: application/json' \
    --data '{"consent_verified":true,"publication_state":"PUBLISHED","runtime_session_refs":["sov-session"],"forged-grant":true}')
  echo "DENIED $denied"
  grep -q 'LIVE_AUTHORITY_CLOSED' <<<"$denied"
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
set +e
java -jar "$jar_path" \
  --spring.profiles.active=dev \
  --server.address=0.0.0.0 \
  --server.port="$(free_port)" \
  --arcava.journal.path="$work/refuse.ndjson" \
  >"$refuse_log" 2>&1
refuse_status=$?
set -e
echo "NON_LOOPBACK_EXIT $refuse_status"
[[ "$refuse_status" -ne 0 ]]
grep -q 'non-loopback' "$refuse_log"
echo "PASS jar_lifecycle live=200 ready=503 denied=closed journal=unchanged stop=terminated restart=closed"
