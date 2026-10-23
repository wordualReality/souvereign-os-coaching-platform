"""PIAC facade must reject every request. No dummy accept path."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
from facade import KdbCommandFacade
from piac import PiacVerificationError

class FailClosed(unittest.TestCase):
    def test_rejects_empty(self):
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle({})
    def test_rejects_synthetic_allow_ref(self):
        env = {
            "access_decision_ref": "SYNTHETIC_ALLOW",
            "principal_context_ref": "SYNTHETIC_PIAC",
            "payload": {"ok": True},
        }
        with self.assertRaises(PiacVerificationError):
            KdbCommandFacade().handle(env)
if __name__ == "__main__":
    unittest.main()
