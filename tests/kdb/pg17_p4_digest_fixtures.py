#!/usr/bin/env python3
"""SQL-side v2 digest uniqueness fixtures on disposable PostgreSQL 17.

Python json.dumps is not the contract. All comparisons run in PostgreSQL
jsonb_build_array / jsonb::text. Cross-language parity is unresolved.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pg17_disposable_command_path as cmd  # noqa: E402


def distinct(sql: str, label: str) -> None:
    out = cmd.must(cmd.USER_SUPER, sql)
    if out not in {"t", "true"}:
        raise SystemExit(f"{label} not distinct: {out}")
    print("DISTINCT", label)


def unresolved(sql: str, label: str) -> None:
    cmd.must_fail(cmd.USER_SUPER, sql, "CANONICAL_DIGEST_CONTRACT_UNRESOLVED")
    print("UNRESOLVED", label)


def main() -> None:
    cmd.ensure_container()
    cmd.ensure_schema()
    distinct(
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v2','K',NULL,'P')) "
        "IS DISTINCT FROM kdb_ops.canonical_digest_v2(jsonb_build_array('v2','K','P'));",
        "null_vs_dropped_field",
    )
    distinct(
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v2','')) "
        "IS DISTINCT FROM kdb_ops.canonical_digest_v2(jsonb_build_array('v2', NULL));",
        "empty_string_vs_null",
    )
    distinct(
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v2', E'a\\nb')) "
        "IS DISTINCT FROM kdb_ops.canonical_digest_v2(jsonb_build_array('v2','a','b'));",
        "embedded_newline_vs_two_fields",
    )
    distinct(
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v2','café')) "
        "IS DISTINCT FROM kdb_ops.canonical_digest_v2(jsonb_build_array('v2','cafe'));",
        "unicode",
    )
    distinct(
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v2', 1)) "
        "IS DISTINCT FROM kdb_ops.canonical_digest_v2(jsonb_build_array('v2', '1'));",
        "numeric_vs_text",
    )
    same = cmd.must(
        cmd.USER_SUPER,
        "SELECT kdb_ops.jsonb_sha256('{\"b\":1,\"a\":2}'::jsonb) "
        "= kdb_ops.jsonb_sha256('{\"a\":2,\"b\":1}'::jsonb);",
    )
    if same not in {"t", "true"}:
        raise SystemExit(f"jsonb_key_order_canonical not equal: {same}")
    print("SAME jsonb_key_order_canonical")
    distinct(
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v2','A','B')) "
        "IS DISTINCT FROM kdb_ops.canonical_digest_v2(jsonb_build_array('v2','A','B','C'));",
        "field_count",
    )
    unresolved("SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v1','SOURCE_INTAKE'));", "wrong_version")
    unresolved("SELECT kdb_ops.canonical_digest_v2('{\"k\":\"v\"}'::jsonb);", "object_not_array")
    unresolved("SELECT kdb_ops.canonical_digest_v2(NULL);", "null_document")
    unresolved(
        "SELECT kdb_ops.canonical_command_digest("
        "'SOURCE_INTAKE'::text, gen_random_uuid(), 'T', 'KDB', 'p', 'C', 'L',"
        " repeat('a',64), repeat('b',64), 'P', 'A', 'I', gen_random_uuid());",
        "v1_helper_retired",
    )
    print("PASS_P4_DIGEST_FIXTURES")
    print("NOTE_CROSS_LANGUAGE_PARITY_UNRESOLVED")


if __name__ == "__main__":
    main()
