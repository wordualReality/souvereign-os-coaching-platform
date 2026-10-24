# KDB-M01-04 local architecture alignment

Parent commit (immutable): `d2a236bfd83e041bff8d785ef763d2c0f5079beb`
Branch: `kdb/m01-03-repository-materialization`
Source kit ZIP SHA-256: `306ed8b6f75883d11b3f6785def8c95608dfc62848b8cff99be4aa32db4528cd`
P03 Cursor ZIP SHA-256: `2dd1235c5da117ff732d06f77904c4358785da4c6a6807d5bdc9deefc58c4518`

P03 used `canonical` / `dev_staging` / `kdb_api` / `kdb_audit`. That layout is withdrawn in this repair commit. Physical namespaces are `kdb_canonical`, `kdb_staging`, `kdb_governance`, `kdb_ops`.

`20261023140300__kdb_m01_004__indexes_idempotency.sql` is `NOT_AUTHORIZED_FOR_APPLY`.
No SQL apply. No push. Untracked B03 files are not part of this change.
