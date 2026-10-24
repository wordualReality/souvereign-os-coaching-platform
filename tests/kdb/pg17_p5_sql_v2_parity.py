#!/usr/bin/env python3
"""SQL-v2 golden vectors vs KDB producer adapter. Disposable PostgreSQL 17.

Fails CI on digest mismatch. JSON.stringify is proved not equal. Does not
GRANT producer EXECUTE. Does not connect to Supabase.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
import pg17_disposable_command_path as cmd  # noqa: E402
from digest_v2 import (  # noqa: E402
    digest_hex_from_jsonb_text,
    local_digest,
    o1_fields,
    o2_fields,
    o3_fields,
    pg_jsonb_array_text,
    sql_jsonb_build_array,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "p5_sql_v2_golden.json"


def sql_text_and_digest(values) -> tuple[str, str]:
    arr = sql_jsonb_build_array(values)
    text = cmd.must(cmd.USER_SUPER, f"SELECT {arr}::text;")
    digest = cmd.must(cmd.USER_SUPER, f"SELECT kdb_ops.canonical_digest_v2({arr});")
    return text, digest


def case(label: str, values: list) -> dict:
    text, digest = sql_text_and_digest(values)
    local_text = pg_jsonb_array_text(values)
    local_hex = local_digest(values)
    if local_text != text:
        raise SystemExit(f"{label} jsonb text mismatch local vs sql")
    if local_hex != digest or digest_hex_from_jsonb_text(text) != digest:
        raise SystemExit(f"{label} digest mismatch local={local_hex} sql={digest}")
    print("PARITY", label, digest[:16])
    return {"id": label, "jsonb_text": text, "digest": digest, "values": values}


def main() -> None:
    cmd.ensure_container()
    cmd.ensure_schema()
    ver = cmd.must(cmd.USER_SUPER, "SHOW server_version;")
    if "17." not in ver:
        raise SystemExit(f"not PostgreSQL 17: {ver}")
    cid = "00000000-0000-4000-8000-000000000001"
    sid = "00000000-0000-4000-8000-000000000002"
    svid = "00000000-0000-4000-8000-000000000003"
    cand = "00000000-0000-4000-8000-000000000004"
    rev = "00000000-0000-4000-8000-000000000005"
    digest64 = "ab" * 32
    rights = {"b": 1, "a": 2, "rights_status": "ADMITTED"}
    spans_a = [{"path": "p1", "n": 1}]
    spans_b = [{"n": 1, "path": "p1"}]
    spans_changed = [{"path": "p9", "n": 1}]
    payload = {"z": "q", "a": "p"}
    rights_digest = cmd.must(
        cmd.USER_SUPER,
        f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(json.dumps(rights))}::jsonb);",
    )
    payload_digest = cmd.must(
        cmd.USER_SUPER,
        f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(json.dumps(payload))}::jsonb);",
    )
    spans_a_digest = cmd.must(
        cmd.USER_SUPER,
        f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(json.dumps(spans_a))}::jsonb);",
    )
    spans_b_digest = cmd.must(
        cmd.USER_SUPER,
        f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(json.dumps(spans_b))}::jsonb);",
    )
    spans_changed_digest = cmd.must(
        cmd.USER_SUPER,
        f"SELECT kdb_ops.jsonb_sha256({cmd.psql_str(json.dumps(spans_changed))}::jsonb);",
    )
    if spans_a_digest != spans_b_digest:
        raise SystemExit("jsonb key-order spans digests must match")

    records = []
    records.append(case("o1_ascii", o1_fields(cid, "TENANT_SYNTH_A", "KDB", "kdb_knowledge_intake", "LICENSED_DOCUMENT", "synthetic://kdb/p5/a", digest64, rights_digest, "PRINCIPAL_REF_SYNTH_PIPELINE", "ACCESS_SYNTH_OK", "idem-p5", sid)))
    records.append(case("o1_null_tenant", o1_fields(cid, None, "KDB", "kdb_knowledge_intake", "LICENSED_DOCUMENT", "synthetic://kdb/p5/a", digest64, rights_digest, "P", "A", "idem-p5", sid)))
    records.append(case("o1_empty_tenant", o1_fields(cid, "", "KDB", "kdb_knowledge_intake", "LICENSED_DOCUMENT", "synthetic://kdb/p5/a", digest64, rights_digest, "P", "A", "idem-p5", sid)))
    records.append(case("o1_newline_locator", o1_fields(cid, "TENANT_SYNTH_A", "KDB", "kdb_knowledge_intake", "LICENSED_DOCUMENT", "synthetic://kdb/p5/a\nb", digest64, rights_digest, "P", "A", "idem-p5", sid)))
    records.append(case("o1_quotes_backslash", o1_fields(cid, "TENANT_SYNTH_A", "KDB", "kdb_knowledge_intake", "LICENSED_DOCUMENT", 'loc\\and"quote', digest64, rights_digest, "P", "A", "idem-p5", sid)))
    records.append(case("o1_unicode", o1_fields(cid, "TENANT_SYNTH_A", "KDB", "kdb_knowledge_intake", "LICENSED_DOCUMENT", "cafe\u0301", digest64, rights_digest, "P", "A", "idem-p5", sid)))
    records.append(case("o2_with_spans", o2_fields(cid, "TENANT_SYNTH_A", sid, svid, cand, 1, digest64, payload_digest, spans_a_digest, "ACTOR", "ACCESS")))
    records.append(case("o2_changed_spans", o2_fields(cid, "TENANT_SYNTH_A", sid, svid, cand, 1, digest64, payload_digest, spans_changed_digest, "ACTOR", "ACCESS")))
    records.append(case("o2_revision_two", o2_fields(cid, "TENANT_SYNTH_A", sid, svid, cand, 2, digest64, payload_digest, spans_a_digest, "ACTOR", "ACCESS")))
    records.append(case("o3_handoff", o3_fields(cid, "TENANT_SYNTH_A", rev, "ACTOR", "ACCESS")))

    if records[0]["digest"] == records[1]["digest"]:
        raise SystemExit("NULL tenant must not match populated tenant")
    if records[1]["digest"] == records[2]["digest"]:
        raise SystemExit("NULL tenant must not match empty string")
    if records[6]["digest"] == records[7]["digest"]:
        raise SystemExit("changed evidence spans must change O2 digest")

    cmd.must_fail(
        cmd.USER_SUPER,
        "SELECT kdb_ops.canonical_digest_v2(jsonb_build_array('v1','SOURCE_INTAKE'));",
        "CANONICAL_DIGEST_CONTRACT_UNRESOLVED",
    )
    print("UNRESOLVED wrong_version")

    stringify = json.dumps(["v2", "a\nb"], ensure_ascii=False, separators=(",", ":"))
    pg_text, _digest = sql_text_and_digest(["v2", "a\nb"])
    if stringify == pg_text:
        raise SystemExit("JSON compact stringify unexpectedly matched PostgreSQL jsonb text")
    print("NEGATIVE_JSON_STRINGIFY_NOT_PG")

    live = {
        "postgres_version": ver,
        "adapter": "services/kdb/digest_v2.py",
        "contract": "SHA-256 UTF-8 PostgreSQL jsonb_build_array(...)::text",
        "cases": [{"id": row["id"], "digest": row["digest"], "jsonb_text": row["jsonb_text"]} for row in records],
    }
    if FIXTURE.exists():
        pinned = json.loads(FIXTURE.read_text())
        live_digests = {row["id"]: row["digest"] for row in live["cases"]}
        for row in pinned["cases"]:
            if live_digests.get(row["id"]) != row["digest"]:
                raise SystemExit(f"golden digest drift {row['id']}")
        print("GOLDEN_PIN_MATCH", FIXTURE.name)
    else:
        FIXTURE.write_text(json.dumps(live, indent=2) + "\n")
        print("GOLDEN_PIN_WRITTEN", FIXTURE)

    print("SQL_V2_PARITY_PASS")
    print("NOTE_CROSS_LANGUAGE_JSON_STRINGIFY_IS_NOT_THE_CONTRACT")


if __name__ == "__main__":
    main()
