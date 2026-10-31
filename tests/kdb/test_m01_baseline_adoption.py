"""P24 historical baseline adoption and ADR mapping invariants. No network."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "database/baselines/kdb"
INTEGRATION = ROOT / "integration_main_2026-10-22.json"
DEV = ROOT / "kdb_dev_2026-10-23.json"
MANIFEST = ROOT / "MANIFEST_SHA256.json"
MAPPING = ROOT / "M01_KEEP_ADAPT_SUPERSEDE_CREATE.md"
ADR = REPO / "docs/kdb/m01/02_PHYSICAL_ARCHITECTURE_ADR.md"
CORE = REPO / "database/migrations/kdb/20261023140000__kdb_m01_001__core_foundation.sql"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


class M01BaselineAdoption(unittest.TestCase):
    def test_manifest_hashes_every_adopted_file_and_records_external_only(self) -> None:
        manifest = load(MANIFEST)
        self.assertEqual(manifest["repo_head_at_adoption_start"], "366fb7d6db01b09d21c74d3c40cd3d30d13b281d")
        self.assertEqual(manifest["manifest_policy"], "SELF_HASH_EXCLUDED")
        self.assertEqual(manifest["external_original_status"], "EXTERNAL_ORIGINAL_ARCHIVE_SHA_RECORDED")
        self.assertEqual(set(manifest["files"]), {INTEGRATION.name, DEV.name, MAPPING.name})
        for name, expected in manifest["files"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)
        self.assertNotIn(MANIFEST.name, manifest["files"])
        for source in manifest["external_sources"].values():
            self.assertRegex(source["sha256"], r"^[0-9a-f]{64}$")
            self.assertIn("RECORDED", source["verification_scope"])

    def test_projects_dates_and_environment_classes_cannot_be_conflated(self) -> None:
        integration, dev = load(INTEGRATION), load(DEV)
        self.assertEqual(integration["project_id"], "zobjpmyccszkabybdmsf")
        self.assertEqual(integration["observed_at"], "2026-10-22")
        self.assertEqual(integration["environment_class"], "KDB_INTEGRATION_MAIN")
        self.assertEqual(integration["database_version_observed"], "17.6")
        self.assertEqual(dev["project_id"], "ujdzahwlximlmndexgmx")
        self.assertEqual(dev["observed_at"], "2026-10-23")
        self.assertEqual(dev["environment_class"], "DEDICATED_KDB_DEV")
        self.assertEqual(dev["database_version_observed"], "17.11")
        self.assertNotEqual(integration["project_id"], dev["project_id"])
        self.assertEqual(dev["catalog_scope"]["row_provenance"], "UNKNOWN")
        self.assertIn("DEV_NOT_INTEGRATION_BASELINE_SUBSTITUTE", dev["limits_and_unknowns"])

    def test_snapshots_are_historical_nonsecret_and_not_promoted(self) -> None:
        forbidden_keys = {"password", "token", "secret", "dsn", "email", "user_id"}
        for path in (INTEGRATION, DEV):
            value = load(path)
            self.assertEqual(value["source_capture_status"], "SOURCE_CAPTURE_HISTORICAL")
            self.assertEqual(value["currency"], "NOT_CURRENTLY_REVERIFIED")
            self.assertEqual(value["final_authority"], "NOT_ADMITTED")
            self.assertEqual(value["security_status"], "NOT_SECURITY_PASS")
            self.assertTrue(value["evidence_uri"].startswith("https://docs.google.com/"))
            self.assertFalse(forbidden_keys & set(value))
            blob = json.dumps(value, sort_keys=True).lower()
            self.assertNotIn("postgresql://", blob)
            self.assertNotIn("service_role_key", blob)

    def test_object_mapping_covers_legacy_relations_rpcs_and_dispositions(self) -> None:
        integration = load(INTEGRATION)
        mapping = MAPPING.read_text()
        for relation in integration["catalog_scope"]["relations"]:
            self.assertIn(f"`{relation}`", mapping)
        for routine in integration["catalog_scope"]["legacy_public_security_definer_functions"]:
            self.assertIn(f"`{routine}`", mapping)
        for disposition in (
            "KEEP_LEGACY_NO_MUTATION",
            "ADAPT_ONLY_AFTER_SEPARATE_OWNER_GRANT",
            "SUPERSEDE_ARCHIVED_17_TABLE_LAYOUT_NO_DEPLOY",
            "CREATE_CANDIDATE_ONLY_NEW_KDB_12_TABLES",
            "UNRESOLVED_MAPPING",
        ):
            self.assertIn(disposition, mapping)
        self.assertIn("NO_DEFAULT_ACL_CREATOR_PROOF", json.dumps(integration))
        self.assertIn("NOT_18_OF_18", mapping)

    def test_mapping_matches_current_twelve_table_migration_and_adr(self) -> None:
        sql = CORE.read_text()
        tables = re.findall(r"CREATE TABLE\s+([a-z_]+\.[a-z_]+)", sql)
        self.assertEqual(len(tables), 12)
        self.assertEqual(len(set(tables)), 12)
        self.assertFalse(any(name.startswith("canonical.") or name.startswith("dev_staging.") for name in tables))
        mapping, adr = MAPPING.read_text(), ADR.read_text()
        for table in tables:
            self.assertIn(f"`{table}`", mapping)
        for schema in ("kdb_governance", "kdb_staging", "kdb_canonical", "kdb_ops"):
            self.assertIn(f"`{schema}`", adr)
        self.assertNotIn("HOSTED_VERIFIED_YES", mapping)
        self.assertNotIn("SECURITY_PASS_SCOPED", mapping)


if __name__ == "__main__":
    unittest.main()
