#!/usr/bin/env python3
"""P13 unique disposable PG17 review-handoff preview readback.

Reuses the P12 TEST_FIXTURE_ADMIN unique PostgreSQL 17 target. COMMITs the
synthetic Source-to-Review chain, maps it into the offline preview service,
then COMMITs rights_status=REVOKED and proves the preview is denied. No new
SQL grants. Unique target is dropped. FINAL stays NOT_ADMITTED.
"""
from __future__ import annotations

import json
import sys
import uuid
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
from p11_snapshot_map import assert_redacted, map_candidate_chain  # noqa: E402
from pg17_p12_commit_reconnect_replay import (  # noqa: E402
    ADMIN_DB,
    COUNT_SQL,
    FIXTURE_ADMIN,
    INSERT_SQL,
    PROTECTED_ZERO,
    SELECT_SQL,
    SOURCE_ID,
    TENANT,
    Target,
    USER_SUPER,
    apply_stack,
    create_unique_database,
    refuse_hosted_env,
    setup_fixture_admin,
    source_commit,
    start_unique_container,
    teardown,
)
from review_handoff_preview import PACKET, preview  # noqa: E402

CASE_ID = "P13-SYNTH-PG17-PREVIEW"


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if int(row_counts.get(key, 0)) != 0:
            fail(f"P13_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


def preview_payload(chain: dict) -> dict:
    return {
        "case_id": CASE_ID,
        "expected_tenant_scope": TENANT,
        "candidate_chain": chain,
    }


def main() -> None:
    refuse_hosted_env()
    target = Target("kdb_p12_" + uuid.uuid4().hex[:12])
    print("P13_IDENTITY", target.identity)
    print("P13_MODE", target.mode)
    created = False
    try:
        if target.mode == "docker":
            start_unique_container(target)
        else:
            create_unique_database(target)
        created = True
        ver = target.must(USER_SUPER, "SHOW server_version;")
        print("server_version", ver)
        if "17." not in ver:
            fail("P13_NOT_POSTGRES_17")
        apply_stack(target)
        setup_fixture_admin(target)
        before = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(before, "BEFORE")

        commit_proc = target.psql(FIXTURE_ADMIN, INSERT_SQL)
        if commit_proc.returncode != 0:
            fail("P13_COMMIT_FAILED " + commit_proc.stdout + commit_proc.stderr)
        snapshot = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        if snapshot.get("source") is None or snapshot.get("review_work_item") is None:
            fail("P13_INCOMPLETE_SNAPSHOT")
        if snapshot["source"]["rights_status"] != "ADMITTED":
            fail("P13_SOURCE_NOT_COMMITTED")

        commit = source_commit()
        admitted = map_candidate_chain(snapshot)
        admitted_receipt = preview(preview_payload(admitted), commit=commit)
        if admitted_receipt["preview_status"] != "PREVIEW_ONLY":
            fail("P13_EXPECTED_PREVIEW " + json.dumps(admitted_receipt, sort_keys=True))
        if admitted_receipt["review_queue"] != "KDB_HUMAN_REVIEW":
            fail("P13_QUEUE_MISSING")
        if admitted_receipt["final_authority"] != "NOT_ADMITTED":
            fail("P13_FALSE_ADMIT")
        if admitted_receipt["queue_card"] is None:
            fail("P13_MISSING_CARD")

        stale = deepcopy(admitted)
        stale["source_versions"] = snapshot["source_versions"]
        stale_receipt = preview(preview_payload(stale), commit=commit)
        if stale_receipt["deny_code"] != "STALE_SOURCE_VERSION":
            fail("P13_EXPECTED_STALE " + str(stale_receipt.get("deny_code")))
        if stale_receipt["queue_card"] is not None:
            fail("P13_STALE_STILL_HAS_CARD")

        revoke = target.psql(
            FIXTURE_ADMIN,
            f"""
BEGIN;
UPDATE kdb_governance.source
SET rights_status = 'REVOKED'
WHERE source_id = '{SOURCE_ID}';
COMMIT;
SELECT rights_status FROM kdb_governance.source WHERE source_id = '{SOURCE_ID}';
""",
        )
        if revoke.returncode != 0:
            fail("P13_REVOKE_FAILED " + revoke.stdout + revoke.stderr)
        revoked_snapshot = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        if revoked_snapshot["source"]["rights_status"] != "REVOKED":
            fail("P13_REVOKE_NOT_COMMITTED")
        revoked_receipt = preview(
            preview_payload(map_candidate_chain(revoked_snapshot)), commit=commit
        )
        if revoked_receipt["deny_code"] != "REVOKED_SOURCE":
            fail("P13_EXPECTED_REVOKED " + str(revoked_receipt.get("deny_code")))
        if revoked_receipt["queue_card"] is not None:
            fail("P13_REVOKED_STILL_HAS_CARD")
        if revoked_receipt["preview_status"] != "PREVIEW_DENIED":
            fail("P13_REVOKED_NOT_DENIED")

        after = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(after, "AFTER")
        wrapper = {
            "packet": PACKET,
            "df_adoption": "DF-20261029-01",
            "gate": "INACTIVE_VERSION_CONTROLLED_CANDIDATE",
            "final_authority": "NOT_ADMITTED",
            "execution": "NON_EXECUTABLE",
            "db_write": "NOT_ADMITTED",
            "assignment": "NOT_ASSIGNED",
            "publication": "NOT_PUBLISHED",
            "c04_human_decision": "NOT_WRITTEN",
            "c05_canonical_admission": "NOT_WRITTEN",
            "outbox": "NOT_EMITTED",
            "fixture_admin_is_runtime_principal": False,
            "admitted_preview": admitted_receipt["preview_status"],
            "stale_deny": stale_receipt["deny_code"],
            "revoked_deny": revoked_receipt["deny_code"],
            "inventory_source": admitted_receipt["inventory_source"],
            "logical_objects_claimed": admitted_receipt["logical_objects_claimed"],
            "hosted_verified": "HOSTED_VERIFIED_NO",
            "admin_db_untouched": ADMIN_DB,
            "source_commit": commit,
        }
        text = json.dumps(wrapper, sort_keys=True)
        assert_redacted(text)
        if "ALLOW" in text or "DB_COMMAND_ADMITTED" in text or "18/18" in text:
            fail("P13_FORBIDDEN_TOKEN")
        print(text)
        print("PASS_P13_OFFLINE_REVIEW_HANDOFF_PREVIEW")
    finally:
        if created:
            teardown(target)
            print("P13_TEARDOWN", target.identity, "ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
