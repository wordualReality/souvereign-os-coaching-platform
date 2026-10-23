# KDB-M01-03 repository materialization

Source ZIP: `KDB-M01-CURSOR-HANDOVER-2026-10-23.zip`  
SHA-256: `2dd1235c5da117ff732d06f77904c4358785da4c6a6807d5bdc9deefc58c4518`  
Drive: https://drive.google.com/file/d/1QLf98qLvtC884ShZhcj6ZOodbY9CRlSI/view

This packet copies the handover into the existing `database/migrations/kdb` tree. It does not apply SQL, does not link a remote Supabase project, and does not rewrite existing migrations.

## Split map

| File | Scope |
| --- | --- |
| `database/migrations/kdb/20261023140000__kdb_m01_001__core_foundation.sql` | schemas and tables |
| `database/migrations/kdb/20261023140100__kdb_m01_002__security_boundary.sql` | roles, immutability, RLS, grants, policies |
| `database/migrations/kdb/20261023140200__kdb_m01_003__api_boundary.sql` | `kdb_api` functions |
| `database/migrations/kdb/20261023140300__kdb_m01_004__indexes_idempotency.sql` | indexes including unique/idempotency indexes |
| `tests/kdb/kdb_m01_verification.sql` | post-apply catalog checks |
| `database/fixtures/kdb/kdb_m01_synthetic.sql` | synthetic fixture |
| `database/rollback/kdb/kdb_m01_rollback.sql` | bounded rollback, not a forward migration |

`supabase/migrations` was not used. The local `supabase/` tree currently holds only CLI `.temp` linkage. Putting forward SQL there would risk a remote apply.

Existing untracked B03 files under `database/migrations/kdb/` were left untouched and are not part of this commit.
