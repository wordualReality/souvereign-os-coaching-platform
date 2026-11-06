#!/usr/bin/env bash
# Shared guard for the local web build. Source this file. Do not execute it.

refuse_secret() {
  local name key
  for name in DATABASE_URL SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_SERVICE_ROLE_KEY CORE_ACCESS_API_BASE CANONICAL_API_BASE; do
    if [[ -n "${!name:-}" ]]; then
      echo "REFUSED forbidden_env=$name" >&2
      exit 1
    fi
  done
  while IFS='=' read -r key _; do
    case "$key" in
      NEXT_PUBLIC_*|*PIAC*|*Piac*)
        echo "REFUSED forbidden_env=$key" >&2
        exit 1
        ;;
    esac
  done < <(env)
}

clean_build() {
  env -i \
    PATH="$PATH" \
    HOME="${HOME:-/tmp}" \
    TMPDIR="${TMPDIR:-/tmp}" \
    NEXT_TELEMETRY_DISABLED=1 \
    "$@"
}
