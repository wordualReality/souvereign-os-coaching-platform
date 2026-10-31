#!/usr/bin/env python3
"""P21 disposable PG17 evidence-bound review composition.

Reuses the P20 two-chain COMMIT/reconnect/revoke/security harness while routing
every proof call through the P21 combined current-case verifier.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / "services" / "kdb"))

import pg17_p20_source_bytes_proof as p20  # noqa: E402
from offline_evidence_bound_review import evidence_bound_review_files  # noqa: E402


def _p21_adapter(*args: Any, **kwargs: Any) -> dict[str, Any]:
    receipt = evidence_bound_review_files(*args, **kwargs)
    status = receipt.get("review_status")
    if status == "LOCAL_BYTES_AND_SPANS_BOUNDED":
        return {
            **receipt,
            "proof_status": "LOCAL_BYTES_MATCH_DECLARED_SHA",
        }
    deny = str(receipt.get("deny_code") or "PROOF_DENIED")
    return {
        **receipt,
        "proof_status": (
            "LOCAL_CONTENT_SHA_MISMATCH"
            if deny == "LOCAL_CONTENT_SHA_MISMATCH"
            else "PROOF_DENIED"
        ),
    }


def main() -> None:
    p20.source_bytes_proof_files = _p21_adapter
    p20.main()
    print("PASS_P21_OFFLINE_EVIDENCE_BOUND_REVIEW")


if __name__ == "__main__":
    main()
