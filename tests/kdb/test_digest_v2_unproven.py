"""Unproven SQL-v2 adapter types must fail closed. Golden scalars stay legal."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "kdb"))
from digest_v2 import (  # noqa: E402
    UNRESOLVED,
    DigestContractError,
    local_digest,
    o1_fields,
    o2_fields,
    pg_jsonb_array_text,
    sql_jsonb_build_array,
)


class UnprovenDigestTypes(unittest.TestCase):
    def test_proven_o1_scalars_still_hash(self):
        fields = o1_fields(
            "00000000-0000-4000-8000-000000000001",
            "TENANT_SYNTH_A",
            "KDB",
            "kdb_knowledge_intake",
            "LICENSED_DOCUMENT",
            "synthetic://kdb/p5/a",
            "ab" * 32,
            "cd" * 32,
            "P",
            "A",
            "idem-p5",
            "00000000-0000-4000-8000-000000000002",
        )
        digest = local_digest(fields)
        self.assertEqual(len(digest), 64)

    def test_proven_o2_int_revision(self):
        fields = o2_fields(
            "00000000-0000-4000-8000-000000000001",
            "TENANT_SYNTH_A",
            "00000000-0000-4000-8000-000000000002",
            "00000000-0000-4000-8000-000000000003",
            "00000000-0000-4000-8000-000000000004",
            1,
            "ab" * 32,
            "cd" * 32,
            "ef" * 32,
            "ACTOR",
            "ACCESS",
        )
        self.assertEqual(len(local_digest(fields)), 64)

    def test_nested_dict_unresolved(self):
        with self.assertRaises(DigestContractError) as ctx:
            local_digest(["v2", {"nested": True}])
        self.assertEqual(ctx.exception.code, UNRESOLVED)

    def test_nested_list_unresolved(self):
        with self.assertRaises(DigestContractError) as ctx:
            pg_jsonb_array_text(["v2", ["a"]])
        self.assertEqual(ctx.exception.code, UNRESOLVED)

    def test_float_unresolved(self):
        with self.assertRaises(DigestContractError) as ctx:
            local_digest(["v2", 1.5])
        self.assertEqual(ctx.exception.code, UNRESOLVED)

    def test_bool_unresolved(self):
        with self.assertRaises(DigestContractError) as ctx:
            sql_jsonb_build_array(["v2", True])
        self.assertEqual(ctx.exception.code, UNRESOLVED)

    def test_bytes_unresolved(self):
        with self.assertRaises(DigestContractError) as ctx:
            local_digest(["v2", b"nope"])
        self.assertEqual(ctx.exception.code, UNRESOLVED)

    def test_lone_surrogate_unresolved(self):
        with self.assertRaises(DigestContractError) as ctx:
            local_digest(["v2", "\ud800"])
        self.assertEqual(ctx.exception.code, UNRESOLVED)

    def test_backspace_formfeed_use_short_escapes(self):
        text = pg_jsonb_array_text(["v2", "a\bb", "c\fd"])
        self.assertIn(r"\b", text)
        self.assertIn(r"\f", text)
        self.assertNotIn(r"\u0008", text)
        self.assertNotIn(r"\u000c", text)


if __name__ == "__main__":
    unittest.main()
