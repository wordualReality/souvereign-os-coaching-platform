#!/usr/bin/env python3
"""P15 unique disposable PG17 review case-detail readback.

Reuses the P14 TEST_FIXTURE_ADMIN two linked Source-to-Review chains. COMMITs
both, SELECTs on a new connection, opens one eligible work item as DETAIL_ONLY,
then COMMITs REVOKED on that source. Fresh snapshot: that work item is not
selectable; the unrelated source still yields DETAIL_ONLY. No new SQL grants.
Unique target is dropped. FINAL stays NOT_ADMITTED.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_review_case_detail import PACKET, case_detail  # noqa: E402
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
    USER_RUNTIME,
    USER_SUPER,
    WORK_ITEM_ID,
    apply_stack,
    capture_sqlstate,
    create_unique_database,
    refuse_hosted_env,
    setup_fixture_admin,
    source_commit,
    start_unique_container,
    teardown,
)
from pg17_p14_review_inbox import (  # noqa: E402
    CAND_SHA_B,
    INSERT_B_SQL,
    REVISION_ID_B,
    RIGHTS_SHA_B,
    SELECT_B_SQL,
    SOURCE_ID_B,
    WORK_ITEM_ID_B,
    inbox_payload,
)

CASE_ID = "P15-SYNTH-PG17-DETAIL"


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if int(row_counts.get(key, 0)) != 0:
            fail(f"P15_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


def main() -> None:
    refuse_hosted_env()
    target = Target("kdb_p12_" + uuid.uuid4().hex[:12])
    print("P15_IDENTITY", target.identity)
    print("P15_MODE", target.mode)
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
            fail("P15_NOT_POSTGRES_17")
        apply_stack(target)
        setup_fixture_admin(target)
        before = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(before, "BEFORE")

        commit_a = target.psql(FIXTURE_ADMIN, INSERT_SQL)
        if commit_a.returncode != 0:
            fail("P15_COMMIT_A_FAILED " + commit_a.stdout + commit_a.stderr)
        commit_b = target.psql(FIXTURE_ADMIN, INSERT_B_SQL)
        if commit_b.returncode != 0:
            fail("P15_COMMIT_B_FAILED " + commit_b.stdout + commit_b.stderr)

        snapshot_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        snapshot_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if snapshot_a.get("review_work_item") is None or snapshot_b.get("review_work_item") is None:
            fail("P15_INCOMPLETE_SNAPSHOT")

        commit = source_commit()
        payload = inbox_payload(
            [map_candidate_chain(snapshot_a), map_candidate_chain(snapshot_b)],
            case_id=CASE_ID,
        )
        admitted = case_detail(payload, WORK_ITEM_ID, commit=commit)
        if admitted["detail_status"] != "DETAIL_ONLY":
            fail("P15_EXPECTED_DETAIL " + json.dumps(admitted, sort_keys=True))
        if admitted["detail"]["review_work_item_id"] != WORK_ITEM_ID:
            fail("P15_WRONG_WORK_ITEM")
        if admitted["detail"]["source_id"] != SOURCE_ID:
            fail("P15_WRONG_SOURCE")
        if admitted["final_authority"] != "NOT_ADMITTED":
            fail("P15_FALSE_ADMIT")
        if admitted["assignment"] != "NOT_ASSIGNED":
            fail("P15_FALSE_ASSIGN")
        if admitted["detail"]["provenance_trace"]["event_watermark"] != "UNKNOWN":
            fail("P15_FALSE_WATERMARK")
        other = case_detail(payload, WORK_ITEM_ID_B, commit=commit)
        if other["detail"]["source_id"] != SOURCE_ID_B:
            fail("P15_WRONG_OTHER_SOURCE")
        reversed_payload = inbox_payload(
            [map_candidate_chain(snapshot_b), map_candidate_chain(snapshot_a)],
            case_id=CASE_ID,
        )
        if json.dumps(admitted, sort_keys=True, separators=(",", ":")) != json.dumps(
            case_detail(reversed_payload, WORK_ITEM_ID, commit=commit),
            sort_keys=True,
            separators=(",", ":"),
        ):
            fail("P15_ORDER_NOT_INVARIANT")

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
            fail("P15_REVOKE_FAILED " + revoke.stdout + revoke.stderr)
        revoked_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        fresh_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if revoked_a["source"]["rights_status"] != "REVOKED":
            fail("P15_REVOKE_NOT_COMMITTED")
        revoked_payload = inbox_payload(
            [map_candidate_chain(revoked_a), map_candidate_chain(fresh_b)],
            case_id=CASE_ID,
        )
        denied = case_detail(revoked_payload, WORK_ITEM_ID, commit=commit)
        if denied["detail_status"] != "DETAIL_DENIED":
            fail("P15_REVOKED_STILL_DETAIL")
        if denied["deny_code"] != "WORK_ITEM_NOT_SELECTABLE":
            fail("P15_REVOKE_DENY_MISMATCH " + str(denied.get("deny_code")))
        if denied["detail"] is not None:
            fail("P15_REVOKED_HAS_DETAIL")
        if WORK_ITEM_ID in json.dumps(denied):
            fail("P15_REVOKED_ID_ECHO")
        still = case_detail(revoked_payload, WORK_ITEM_ID_B, commit=commit)
        if still["detail_status"] != "DETAIL_ONLY":
            fail("P15_UNRELATED_SOURCE_BLOCKED")
        if still["detail"]["source_id"] != SOURCE_ID_B:
            fail("P15_WRONG_REMAINING_SOURCE")

        capture_sqlstate(
            target,
            USER_RUNTIME,
            "PERFORM 1 FROM kdb_governance.source;",
            "42501",
            "runtime_select_denied",
        )
        capture_sqlstate(
            target,
            FIXTURE_ADMIN,
            f"""
INSERT INTO kdb_governance.human_review_decision (
  candidate_revision_id, candidate_content_sha256, reviewer_principal_ref,
  access_decision_ref, decision, source_rights_digest, review_evidence_sha256
) VALUES (
  '{REVISION_ID_B}', '{CAND_SHA_B}', 'reviewer-untrusted',
  'access-ref-untrusted-string', 'APPROVED_FOR_PROMOTION', '{RIGHTS_SHA_B}', '{CAND_SHA_B}'
);
""",
            "42501",
            "c04_insert_denied",
        )

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
            "physical_scope": "TWO_LINKED_SOURCE_TO_REVIEW_CHAINS",
            "admitted_detail": admitted["detail_status"],
            "revoked_deny": denied["deny_code"],
            "unrelated_detail": still["detail_status"],
            "snapshot_authority": admitted["snapshot_authority"],
            "inventory_source": admitted["inventory_source"],
            "logical_objects_claimed": admitted["logical_objects_claimed"],
            "hosted_verified": "HOSTED_VERIFIED_NO",
            "admin_db_untouched": ADMIN_DB,
            "tenant": TENANT,
            "source_commit": commit,
        }
        text = json.dumps(wrapper, sort_keys=True)
        assert_redacted(text)
        if "ALLOW" in text or "DB_COMMAND_ADMITTED" in text or "18/18" in text:
            fail("P15_FORBIDDEN_TOKEN")
        print(text)
        print("PASS_P15_OFFLINE_REVIEW_CASE_DETAIL")
    finally:
        if created:
            teardown(target)
            print("P15_TEARDOWN", target.identity, "ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
