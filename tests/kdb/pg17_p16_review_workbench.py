#!/usr/bin/env python3
"""P16 unique disposable PG17 static review-workbench readback.

Reuses the P14/P15 TEST_FIXTURE_ADMIN two linked Source-to-Review chains.
COMMITs both, SELECTs on a new connection, renders two-case static HTML, then
COMMITs REVOKED on one source. Fresh snapshot HTML contains only the unrelated
source. No new SQL grants. Unique target is dropped. FINAL stays NOT_ADMITTED.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))
from offline_review_workbench import PACKET, workbench  # noqa: E402
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

CASE_ID = "P16-SYNTH-PG17-WORKBENCH"


def fail(message: str) -> None:
    raise SystemExit(message)


def ensure_protected_zero(row_counts: dict[str, int], label: str) -> None:
    for key in PROTECTED_ZERO:
        if int(row_counts.get(key, 0)) != 0:
            fail(f"P16_{label}_PROTECTED_NONEMPTY {key}={row_counts[key]}")


def main() -> None:
    refuse_hosted_env()
    target = Target("kdb_p12_" + uuid.uuid4().hex[:12])
    print("P16_IDENTITY", target.identity)
    print("P16_MODE", target.mode)
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
            fail("P16_NOT_POSTGRES_17")
        apply_stack(target)
        setup_fixture_admin(target)
        before = {key: int(value) for key, value in target.json_row(USER_SUPER, COUNT_SQL).items()}
        ensure_protected_zero(before, "BEFORE")

        commit_a = target.psql(FIXTURE_ADMIN, INSERT_SQL)
        if commit_a.returncode != 0:
            fail("P16_COMMIT_A_FAILED " + commit_a.stdout + commit_a.stderr)
        commit_b = target.psql(FIXTURE_ADMIN, INSERT_B_SQL)
        if commit_b.returncode != 0:
            fail("P16_COMMIT_B_FAILED " + commit_b.stdout + commit_b.stderr)

        snapshot_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        snapshot_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if snapshot_a.get("review_work_item") is None or snapshot_b.get("review_work_item") is None:
            fail("P16_INCOMPLETE_SNAPSHOT")

        commit = source_commit()
        payload = inbox_payload(
            [map_candidate_chain(snapshot_a), map_candidate_chain(snapshot_b)],
            case_id=CASE_ID,
        )
        admitted = workbench(payload, commit=commit)
        if admitted["workbench_status"] != "PREVIEW_ONLY":
            fail("P16_EXPECTED_PREVIEW " + json.dumps({k: admitted[k] for k in admitted if k != "html"}))
        if admitted["card_count"] != 2 or admitted["detail_count"] != 2:
            fail("P16_EXPECTED_TWO_CASES")
        html_page = admitted["html"]
        if WORK_ITEM_ID not in html_page or WORK_ITEM_ID_B not in html_page:
            fail("P16_MISSING_WORK_ITEM")
        if html_page.find(WORK_ITEM_ID) > html_page.find(WORK_ITEM_ID_B):
            fail("P16_UNSORTED")
        if "<script" in html_page or "<form" in html_page or "javascript:" in html_page:
            fail("P16_UNSAFE_HTML")
        reversed_payload = inbox_payload(
            [map_candidate_chain(snapshot_b), map_candidate_chain(snapshot_a)],
            case_id=CASE_ID,
        )
        if html_page != workbench(reversed_payload, commit=commit)["html"]:
            fail("P16_ORDER_NOT_INVARIANT")

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
            fail("P16_REVOKE_FAILED " + revoke.stdout + revoke.stderr)
        revoked_a = target.json_row(FIXTURE_ADMIN, SELECT_SQL)
        fresh_b = target.json_row(FIXTURE_ADMIN, SELECT_B_SQL)
        if revoked_a["source"]["rights_status"] != "REVOKED":
            fail("P16_REVOKE_NOT_COMMITTED")
        revoked_payload = inbox_payload(
            [map_candidate_chain(revoked_a), map_candidate_chain(fresh_b)],
            case_id=CASE_ID,
        )
        revoked = workbench(revoked_payload, commit=commit)
        if revoked["card_count"] != 1 or revoked["detail_count"] != 1:
            fail("P16_EXPECTED_ONE_CASE " + str(revoked["card_count"]))
        if WORK_ITEM_ID in revoked["html"]:
            fail("P16_REVOKED_STILL_RENDERED")
        if WORK_ITEM_ID_B not in revoked["html"]:
            fail("P16_UNRELATED_SOURCE_MISSING")
        if SOURCE_ID_B not in revoked["html"]:
            fail("P16_UNRELATED_SOURCE_ID_MISSING")

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
            "admitted_card_count": admitted["card_count"],
            "revoked_card_count": revoked["card_count"],
            "workbench_status": admitted["workbench_status"],
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
            fail("P16_FORBIDDEN_TOKEN")
        print(text)
        print("PASS_P16_STATIC_OFFLINE_REVIEW_WORKBENCH")
    finally:
        if created:
            teardown(target)
            print("P16_TEARDOWN", target.identity, "ZERO_RESIDUAL")


if __name__ == "__main__":
    main()
