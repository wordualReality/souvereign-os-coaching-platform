"""DF-20261029-01 evidence matrix for P11. Not a hosted or security PASS.

Twelve physical SQL001 tables are mapped. A frozen 18-object logical
inventory is not in SQL001 or O1/O2/O3, so this module does not claim 18/18.
"""
from __future__ import annotations

from typing import Any, Mapping

SQL001 = "database/migrations/kdb/20261023140000__kdb_m01_001__core_foundation.sql"
O1 = "kdb://m01/o1_source_ingest/1.0"
O2 = "kdb://m01/o2_candidate_proposal/1.0"
O3 = "kdb://m01/o3_review_handoff/1.0"

CONTRACT_MAPPINGS = (
    {
        "from": "O1.payload.source_locator",
        "to": "kdb_governance.source.external_locator",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O1.payload.rights",
        "to": "kdb_governance.source_version.rights_snapshot",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O1.payload.rights_snapshot_sha256",
        "to": "kdb_governance.source_version.rights_snapshot_sha256",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O1.payload.submission_id",
        "to": "kdb_staging.submission.submission_id",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O2.payload.evidence_spans",
        "to": "kdb_staging.candidate_revision.evidence_span_refs",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O2.payload.source_version_id",
        "to": "kdb_staging.candidate_revision.source_version_id",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O2.payload.submission_id",
        "to": "kdb_staging.candidate_revision.submission_id",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O2.payload.revision_no",
        "to": "kdb_staging.candidate_revision.revision_no",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O3.payload.candidate_revision_id",
        "to": "kdb_staging.review_work_item.candidate_revision_id",
        "kind": "TEST_ONLY_TRANSFORM",
    },
    {
        "from": "O3.payload.review_queue",
        "to": "kdb_staging.review_work_item.owner_queue",
        "kind": "TEST_ONLY_TRANSFORM",
    },
)

NONPHYSICAL_CANDIDATES_NOT_ASSERTED = (
    "DerivationVersion",
    "EvidenceVersion",
    "SemanticDescriptorVersion",
    "TaxonomyVersion",
    "SemanticRuleVersion",
    "EffectClaimVersion",
)


def _row(
    *,
    object_id: str,
    name: str,
    schema_path: str,
    state_command: str,
    origin_rights_version: str,
    consumer_contract: str,
    specified: str,
    implemented: str,
    local_verified: str,
    hosted_verified: str,
    tests: list[str],
    gap: str,
    next_step: str,
) -> dict[str, Any]:
    return {
        "id": object_id,
        "object": name,
        "owner": "KDB",
        "schema_path": schema_path,
        "sql_file": SQL001,
        "state_command": state_command,
        "origin_rights_version": origin_rights_version,
        "consumer_contract": consumer_contract,
        "specified": specified,
        "implemented": implemented,
        "local_verified": local_verified,
        "hosted_verified": hosted_verified,
        "tests": tests,
        "gap": gap,
        "next_step": next_step,
    }


def verify_contract_mappings(snapshot: Mapping[str, Any]) -> list[dict[str, str]]:
    source = snapshot.get("source") or {}
    version = snapshot.get("source_version") or {}
    submission = snapshot.get("submission") or {}
    candidate = snapshot.get("candidate_revision") or {}
    work = snapshot.get("review_work_item") or {}
    checks = (
        ("O1.payload.source_locator", "kdb_governance.source.external_locator", bool(source.get("external_locator"))),
        ("O1.payload.rights", "kdb_governance.source_version.rights_snapshot", isinstance(version.get("rights_snapshot"), dict)),
        (
            "O1.payload.rights_snapshot_sha256",
            "kdb_governance.source_version.rights_snapshot_sha256",
            isinstance(version.get("rights_snapshot_sha256"), str)
            and len(str(version.get("rights_snapshot_sha256"))) == 64,
        ),
        ("O1.payload.submission_id", "kdb_staging.submission.submission_id", bool(submission.get("submission_id"))),
        (
            "O2.payload.evidence_spans",
            "kdb_staging.candidate_revision.evidence_span_refs",
            isinstance(candidate.get("evidence_span_refs"), list)
            and len(candidate.get("evidence_span_refs") or []) > 0,
        ),
        (
            "O2.payload.source_version_id",
            "kdb_staging.candidate_revision.source_version_id",
            candidate.get("source_version_id") == version.get("source_version_id"),
        ),
        (
            "O2.payload.submission_id",
            "kdb_staging.candidate_revision.submission_id",
            candidate.get("submission_id") == submission.get("submission_id"),
        ),
        (
            "O2.payload.revision_no",
            "kdb_staging.candidate_revision.revision_no",
            int(candidate.get("revision_no") or 0) >= 1,
        ),
        (
            "O3.payload.candidate_revision_id",
            "kdb_staging.review_work_item.candidate_revision_id",
            work.get("candidate_revision_id") == candidate.get("candidate_revision_id"),
        ),
        (
            "O3.payload.review_queue",
            "kdb_staging.review_work_item.owner_queue",
            work.get("owner_queue") == "KDB_HUMAN_REVIEW",
        ),
    )
    out = []
    for src, dest, ok in checks:
        out.append(
            {
                "from": src,
                "to": dest,
                "kind": "TEST_ONLY_TRANSFORM",
                "status": "BOUND" if ok else "UNBOUND",
            }
        )
    if any(item["status"] != "BOUND" for item in out):
        raise AssertionError("P11_CONTRACT_MAPPING_UNBOUND")
    return out


def build_matrix(
    *,
    commit: str,
    environment: str,
    run: Mapping[str, Any],
    packet: str | None = None,
    restart_replay: str | None = None,
    restart_replay_next: str | None = None,
) -> dict[str, Any]:
    local_slice = "LOCAL_VERIFIED" if run.get("slice_pass") else "NOT_EXECUTED"
    denial = "LOCAL_VERIFIED" if run.get("denials_pass") else "NOT_EXECUTED"
    zero_ops = "LOCAL_VERIFIED" if run.get("zero_ops") else "NOT_EXECUTED"
    tests_common = list(run.get("tests") or [])
    rows = [
        _row(
            object_id="M1",
            name="source",
            schema_path="kdb_governance.source",
            state_command="O1 SOURCE_INTAKE rights_status PENDING|ADMITTED|BLOCKED|REVOKED",
            origin_rights_version="owner_namespace KDB; declared rights pin only",
            consumer_contract=O1,
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=local_slice,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=tests_common,
            gap="trusted rights provenance and digest recomputation absent",
            next_step="keep P11 fixture rights mutation; no hosted apply",
        ),
        _row(
            object_id="M2",
            name="source_version",
            schema_path="kdb_governance.source_version",
            state_command="O1 source_version_no>0; immutable content_sha256 pin",
            origin_rights_version="rights_snapshot_sha256 DECLARED_PIN_ONLY",
            consumer_contract=O1,
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=local_slice,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=tests_common,
            gap="authoritative source bytes not recomputed",
            next_step="retain opaque digest; Owner KDB",
        ),
        _row(
            object_id="M3",
            name="submission",
            schema_path="kdb_staging.submission",
            state_command="O1 SOURCE_INTAKE RECORDED|QUARANTINED",
            origin_rights_version="request_sha256 pin; PIAC refs are strings",
            consumer_contract=O1,
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=local_slice,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=tests_common,
            gap="no live PIAC or positive ingest",
            next_step="idempotency and conflicting-hash negatives stay local",
        ),
        _row(
            object_id="M4",
            name="candidate_revision",
            schema_path="kdb_staging.candidate_revision",
            state_command="O2 MAP04-C02 PENDING_REVIEW",
            origin_rights_version="evidence_span_refs; candidate content_sha256 pin",
            consumer_contract=O2,
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=local_slice,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=tests_common,
            gap="EvidenceVersion and SemanticDescriptorVersion pins absent from SQL001",
            next_step="do not invent semantic tables",
        ),
        _row(
            object_id="M5",
            name="review_work_item",
            schema_path="kdb_staging.review_work_item",
            state_command="O3 MAP04-C03 REQUESTED KDB_HUMAN_REVIEW",
            origin_rights_version="no C04 decision",
            consumer_contract=O3,
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=local_slice,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=tests_common,
            gap="C04 writer absent",
            next_step="runtime SELECT/INSERT remain denied",
        ),
        _row(
            object_id="M6",
            name="human_review_decision",
            schema_path="kdb_governance.human_review_decision",
            state_command="C04 NEVER from n8n or fixture authority",
            origin_rights_version="C04_NOT_WRITTEN",
            consumer_contract="C04_LOGICAL_NO_WRITER",
            specified="SPECIFIED",
            implemented="SQL_DEFINITION_ONLY",
            local_verified=denial,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=["c04_insert_denied"],
            gap="no admitted C04 writer",
            next_step="future separately admitted C04; P11 must not insert",
        ),
        _row(
            object_id="M7",
            name="protocol",
            schema_path="kdb_canonical.protocol",
            state_command="C05 canonical parent; O4/O5 RPC UNKNOWN",
            origin_rights_version="C05_NOT_WRITTEN",
            consumer_contract="C05_LOGICAL_NO_WRITER",
            specified="SPECIFIED",
            implemented="SQL_DEFINITION_ONLY",
            local_verified="SYNTHETIC_P09_ONLY",
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=["protected_zero"],
            gap="no C05 writer or event watermark",
            next_step="keep independent P09 fixture; do not persist publication",
        ),
        _row(
            object_id="M8",
            name="protocol_version",
            schema_path="kdb_canonical.protocol_version",
            state_command="C05 immutable ProtocolVersion",
            origin_rights_version="content_sha256 OPAQUE_SHA_UNPROVEN",
            consumer_contract="C05_LOGICAL_NO_WRITER",
            specified="SPECIFIED",
            implemented="SQL_DEFINITION_ONLY",
            local_verified="SYNTHETIC_P09_ONLY",
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=["protected_zero"],
            gap="human_decision_id is an untrusted pin",
            next_step="do not concatenate P09 into a DB publication proof",
        ),
        _row(
            object_id="M9",
            name="lifecycle_event",
            schema_path="kdb_canonical.lifecycle_event",
            state_command="C06-C08 PUBLISHED|REVALIDATION_REQUIRED|WITHDRAWN|SUPERSEDED",
            origin_rights_version="EVENT_WATERMARK_UNTRUSTED",
            consumer_contract="LOGICAL_C06_C08_ONLY",
            specified="SPECIFIED",
            implemented="SQL_DEFINITION_ONLY",
            local_verified="SYNTHETIC_P09_ONLY",
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=["protected_zero"],
            gap="no trusted event order",
            next_step="P09 synthetic fixture only",
        ),
        _row(
            object_id="M10",
            name="command_receipt",
            schema_path="kdb_ops.command_receipt",
            state_command="O1-O3 receipt; runtime EXECUTE denied",
            origin_rights_version="no positive command receipt in P11",
            consumer_contract=O1,
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=zero_ops,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=["zero_ops_rows"],
            gap="positive ingest blocked",
            next_step="prove zero new receipt rows, not a publisher",
        ),
        _row(
            object_id="M11",
            name="outbox_event",
            schema_path="kdb_ops.outbox_event",
            state_command="INACTIVE_M01",
            origin_rights_version="OUTBOX_NOT_EMITTED",
            consumer_contract="OUTBOX_NOT_LIVE",
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=zero_ops,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=["zero_ops_rows"],
            gap="outbox inactive",
            next_step="keep zero outbox rows",
        ),
        _row(
            object_id="M12",
            name="audit_event",
            schema_path="kdb_ops.audit_event",
            state_command="O1-O3 audit; no P11 writer",
            origin_rights_version="no P11 audit insert",
            consumer_contract=O1,
            specified="SPECIFIED",
            implemented="IMPLEMENTED",
            local_verified=zero_ops,
            hosted_verified="HOSTED_VERIFIED_NO",
            tests=["zero_ops_rows"],
            gap="no live audit admission",
            next_step="prove zero new audit rows",
        ),
    ]
    return {
        "df_adoption": "DF-20261029-01",
        "packet": packet or "KDB-M01-P11-DISPOSABLE-PG17-SOURCE-TO-REVIEW-READBACK-01",
        "source_commit": commit,
        "environment": environment,
        "final_authority": "NOT_ADMITTED",
        "physical_sql001_tables": 12,
        "logical_objects_claimed": "NOT_18_OF_18",
        "inventory_source": "INVENTORY_SOURCE_GAP",
        "inventory_gap": (
            "frozen 18-object logical inventory is not in SQL001 or O1/O2/O3; "
            "inactive n8n candidate pack names six non-physical objects without canonical numbering"
        ),
        "named_nonphysical_candidates_not_asserted": list(NONPHYSICAL_CANDIDATES_NOT_ASSERTED),
        "inventory_next_step": "Owner KDB recover frozen 18-object inventory; do not adopt 17-table ZIP",
        "hosted_verified": "HOSTED_VERIFIED_NO",
        "restart_replay": restart_replay or "NOT_TESTED",
        "restart_replay_next": restart_replay_next
        or "existing P2 replay/DLQ classifier is not a PostgreSQL restart proof",
        "contract_mappings": list(run.get("contract_mappings") or CONTRACT_MAPPINGS),
        "cardinality": dict(run.get("cardinality") or {}),
        "objects": rows,
    }
