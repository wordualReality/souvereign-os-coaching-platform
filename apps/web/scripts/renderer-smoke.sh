#!/usr/bin/env bash
# Builds the local Next.js shell and checks the four existing routes on loopback.
set -euo pipefail

root=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$root"

if [[ ! -x node_modules/.bin/next ]]; then
  echo "next is not installed. Run npm ci from the repository root." >&2
  exit 2
fi

node_version=$(node -v)
echo "NODE $node_version"
node -e 'const p=require("./package.json"); const l=require("./package-lock.json"); const n=p.dependencies.next; if(l.packages["node_modules/next"].version!==n) process.exit(1); console.log("LOCK next="+n+" react="+p.dependencies.react)'

npm run web:build

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

port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
env -u DATABASE_URL -u SUPABASE_SERVICE_ROLE_KEY -u SUPABASE_ANON_KEY -u SUPABASE_URL \
  npm run web:start -- --port "$port" >"$work/server.log" 2>&1 &
pid=$!
echo "PID $pid PORT $port"

ready=0
for _ in $(seq 1 50); do
  if curl --silent --max-time 1 "http://127.0.0.1:${port}/" >/dev/null; then
    ready=1
    break
  fi
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "renderer exited before listen" >&2
    cat "$work/server.log" >&2
    exit 1
  fi
  sleep 0.2
done
if [[ "$ready" -ne 1 ]]; then
  echo "renderer listen timeout" >&2
  cat "$work/server.log" >&2
  exit 1
fi
if ! grep -q "127.0.0.1:${port}" "$work/server.log"; then
  echo "renderer log does not show the loopback bind" >&2
  cat "$work/server.log" >&2
  exit 1
fi

check() {
  local path=$1
  local text=$2
  local body
  local code
  code=$(curl --silent --show-error --output "$work/body" --write-out '%{http_code}' --max-time 5 "http://127.0.0.1:${port}${path}")
  body=$(cat "$work/body")
  echo "HTTP $code $path"
  [[ "$code" == "200" ]]
  grep -q "$text" <<<"$body"
}

check / "Project B Offer Surface"
check /coach/journeys "Journey Builder"
check /client/member-home "Member Home"
check /admin/provisioning "Manual Client Provisioning"

if grep -R -q "SUPABASE_SERVICE_ROLE_KEY" apps/web/.next; then
  echo "service role name leaked into the renderer output" >&2
  exit 1
fi

kill -TERM "$pid"
set +e
wait "$pid"
status=$?
set -e
pid=""
echo "STOP_EXIT $status"
if curl --silent --max-time 2 "http://127.0.0.1:${port}/" >/dev/null; then
  echo "renderer still answered after stop" >&2
  exit 1
fi
echo "PASS web_renderer routes=4 http=200 bind=127.0.0.1 stop=$status service_role=absent"
