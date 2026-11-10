# F-P25-01: disposable membership-graph repair

The R1 guard and v2 catalog evidence traverse the full undirected connected
component of postgres, kdb_schema_owner, kdb_command_owner,
kdb_ingest_runtime, and kdb_migrator. Every edge preserves role, member,
grantor, and PG17 ADMIN, INHERIT and SET flags. Unknown edges and missing seed
roles deny admission. The only accepted edges are the three synthetic A04
preimage grants of kdb_ingest_writer, kdb_reviewer, and kdb_runtime to
postgres, granted by postgres with ADMIN true, INHERIT false and SET false.
These are specifically required by the pre-existing fixture; they are not
assertions about a hosted environment.

The original A04 P3 candidate creates the migrator after the R1 guard. To
inspect the migrator before any derivative function is created, the disposable
R1 harness creates it immediately before the guard and uses the separately
versioned 202611100001__a04_r1_p3_precreated_disposable.sql derivative,
which verifies that exact role instead of creating it again. The historical
A04 files and their manifest remain untouched; the derivative is pinned in
the R1 manifest. The R1 guard rejects a missing migrator.

The independent PG17 test oracle fetches all raw membership edges, traverses
them in Python and compares the result with the recursive SQL export. Physical
negative cases run in rolled-back transactions in a container with no network.
An output-only graph or an asserted empty array is not independent evidence of
completeness. None of these results authenticates a provider, runner, human
operator, PIAC decision, backup or post-commit restore. The independent
non-author security re-review and hosted gates remain open.
