"""PIAC must remain fail-closed. Not a verifier. No test-allow path."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
from facade import KdbCommandFacade
from piac import PiacVerificationError
from tenant_scope import TenantScopeError


def assert_piac_fail_closed() -> None:
    facade = KdbCommandFacade()
    try:
        facade.handle({})
    except TenantScopeError:
        pass
    else:
        raise SystemExit("EMPTY_ENVELOPE_ACCEPTED")

    envelopes = [
        {
            "tenant_scope": "TENANT_SYNTH_B",
            "access_decision_ref": "SYNTHETIC_ALLOW",
            "principal_context_ref": "SYNTHETIC_PIAC",
            "purpose": "kdb_knowledge_intake",
        },
        {
            "tenant_scope": "TENANT_SYNTH_A",
            "access_decision_ref": "ACCESS_SYNTH_OK",
            "principal_context_ref": "PRINCIPAL_REF_SYNTH_PIPELINE",
            "payload": {"ok": True},
        },
    ]
    for envelope in envelopes:
        try:
            facade.handle(envelope)
        except PiacVerificationError:
            continue
        except TenantScopeError:
            raise SystemExit("VALID_TENANT_STOPPED_BEFORE_PIAC")
        raise SystemExit("PIAC_ACCEPT_PATH_REACHED")
