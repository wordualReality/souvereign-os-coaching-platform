#!/usr/bin/env python3
"""P22 disposable PG17 portable current-case evidence demo.

Runs the P20 two-chain COMMIT/reconnect/revoke/security harness through the
P22 opt-in bundle builder, so the database-derived snapshot and local bytes
must both survive the full portable-demo composition.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))

import pg17_p20_source_bytes_proof as p20  # noqa: E402
from offline_review_demo_pack import EVIDENCE_FILE, demo_pack_with_evidence  # noqa: E402
from offline_source_bytes_proof import _load_payload, _read_source_bytes  # noqa: E402
from review_handoff_preview import PreviewParseError  # noqa: E402


def _p22_adapter(
    batch_path: str | Path,
    work_item_id: Any,
    source_path: str | Path,
    *,
    commit: str = "UNPINNED_LOCAL",
) -> dict[str, Any]:
    payload = _load_payload(batch_path)
    path = Path(str(source_path))
    try:
        pack = demo_pack_with_evidence(
            payload,
            payload,
            work_item_id,
            _read_source_bytes(source_path),
            commit=commit,
            hide_extra=(path.name, path.as_posix()),
        )
    except PreviewParseError as exc:
        return {
            "proof_status": (
                "LOCAL_CONTENT_SHA_MISMATCH"
                if exc.code == "LOCAL_CONTENT_SHA_MISMATCH"
                else "PROOF_DENIED"
            ),
            "deny_code": exc.code,
            "final_authority": "NOT_ADMITTED",
        }
    evidence = json.loads(pack["artifacts"][EVIDENCE_FILE])
    return {
        **evidence,
        "proof_status": "LOCAL_BYTES_MATCH_DECLARED_SHA",
    }


def main() -> None:
    p20.source_bytes_proof_files = _p22_adapter
    p20.main()
    print("PASS_P22_PORTABLE_CURRENT_CASE_EVIDENCE_DEMO")


if __name__ == "__main__":
    main()
