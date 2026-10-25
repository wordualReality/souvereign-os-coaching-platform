#!/usr/bin/env python3
"""Prove that tests/kdb/test_p4_digest_static.py fails the job on a red assertion.

Runs the committed unittest entry, then a disposable scratch copy with one
deliberate broken assertion. The scratch file is never committed.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tests" / "kdb" / "test_p4_digest_static.py"
WORKFLOW = ROOT / ".github" / "workflows" / "kdb-m01-pg17.yml"
CI_ENTRY = "python3 tests/kdb/test_p4_digest_static.py"
MUTANT_BODY = """\
import sys
import unittest
from pathlib import Path

sys.path.insert(0, {kdb_tests!r})
import test_p4_digest_static as orig


class MutantP4DigestStatic(orig.P4DigestStatic):
    def test_v2_array_digest(self):
        self.assertIn("THIS_MUTANT_MUST_FAIL_THE_JOB", orig.P4)


if __name__ == "__main__":
    unittest.main()
"""


def run_script(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )


def main() -> int:
    src = SRC.read_text()
    if 'if __name__ == "__main__":' not in src or "unittest.main()" not in src:
        print("RED P4_STATIC_NOT_UNITTEST_ENTRY")
        return 1
    print("CLOSED P4_STATIC_UNITTEST_ENTRY unittest.main()")

    workflow = WORKFLOW.read_text()
    if CI_ENTRY not in workflow:
        print("RED P4_STATIC_CI_ENTRY_MISSING")
        return 1
    print("CLOSED P4_STATIC_CI_ENTRY", CI_ENTRY)

    clean = run_script(SRC)
    print("P4_STATIC_CLEAN_PSQL_RC_NA")
    print("P4_STATIC_CLEAN_PROCESS_RC", clean.returncode)
    if clean.returncode != 0:
        sys.stdout.write(clean.stdout)
        sys.stderr.write(clean.stderr)
        print("RED P4_STATIC_CLEAN_FAILED")
        return 1
    print("CLOSED P4_STATIC_CLEAN_PASS")

    mutant = MUTANT_BODY.format(kdb_tests=str(SRC.parent))
    if "THIS_MUTANT_MUST_FAIL_THE_JOB" not in mutant:
        print("RED P4_STATIC_MUTANT_NOT_APPLIED")
        return 1
    with tempfile.TemporaryDirectory(prefix="kdb-p4-static-mutant-") as tmp:
        path = Path(tmp) / "test_p4_digest_static_mutant.py"
        path.write_text(mutant)
        broken = run_script(path)
    print("P4_STATIC_MUTANT_PROCESS_RC", broken.returncode)
    if broken.returncode == 0:
        sys.stdout.write(broken.stdout)
        sys.stderr.write(broken.stderr)
        print("RED P4_STATIC_MUTANT_DID_NOT_FAIL")
        return 1
    if "FAIL" not in broken.stderr and "FAIL" not in broken.stdout:
        sys.stdout.write(broken.stdout)
        sys.stderr.write(broken.stderr)
        print("RED P4_STATIC_MUTANT_NO_FAIL_OUTPUT")
        return 1
    print("CLOSED P4_STATIC_FAIL_PROPAGATION")
    print("NOTE_SCRATCH_MUTANT_NOT_COMMITTED")
    print("PASS_P4_STATIC_FAIL_PROPAGATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
