"""PIAC facade must reject every request. No dummy accept path."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
from facade import KdbCommandFacade
from piac import PiacVerificationError
from tenant_scope import TenantScopeError

class FailClosed(unittest.TestCase):
    def test_rejects_empty_tenant_first(self):
        with self.assertRaises(TenantScopeError):
            KdbCommandFacade().handle({})
    def test_rejects_synthetic_allow_without_tenant(self):
        env = {
            "access_decision_ref": "SYNTHETIC_ALLOW",
            "principal_context_ref": "SYNTHETIC_PIAC",
            "payload": {"ok": True},
        }
        with self.assertRaises(TenantScopeError):
            KdbCommandFacade().handle(env)
    def test_rejects_synthetic_allow_with_tenant(self):
        env = {
            "tenant_scope": "TENANT_SYNTH_A",
            "access_decision_ref": "SYNTHETIC_ALLOW",
            "principal_context_ref": "SYNTHETIC_PIAC",
            "payload": {"ok": True},
        }
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle(env)
if __name__ == "__main__":
    unittest.main()
