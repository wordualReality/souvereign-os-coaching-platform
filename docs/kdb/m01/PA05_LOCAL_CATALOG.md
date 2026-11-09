# PA-05 local synthetic catalog contract

This is a disposable PostgreSQL 17 experiment, not a hosted endpoint, PIAC
authority, real human approval, publication or consumer integration. The test
creates a new container with Docker network mode `none`, applies SQL001 to
that isolated database, uses only synthetic data, and removes the container.
The KDB-owned test reader executes a SQL function under a fixture-only reader
role. That role has no direct access to the underlying canonical tables.

The function reads the same database for the source, source-version bytes and
rights snapshot, submission, candidate, review work item, synthetic human
decision, protocol version, lifecycle, and test taxonomy chain. It recomputes
the source, rights and canonical-snapshot digests. It denies missing or invalid
context, rights, source, provenance, taxonomy, decision, lifecycle or digest.
The source's newest version and candidate's newest revision are required; a
different explicit protocol-version reference is denied. These are test-only
rules, not a proof of database-enforced production authority or race safety.

The JSON printed as `PA05_RECEIPT` is a bounded test contract. Its immutable
identity and content pins are:

| Field | Value |
| --- | --- |
| protocolId | `05000000-0000-4000-8000-000000000009` |
| protocolVersionId | `05000000-0000-4000-8000-000000000010` |
| owningModuleId | `05000000-0000-4000-8000-000000000013` |
| taxonomyVersionId | `05000000-0000-4000-8000-000000000014` |
| sourceVersionId | `05000000-0000-4000-8000-000000000002` |
| candidateRevisionId | `05000000-0000-4000-8000-000000000005` |
| versionNo | `1` |
| contentHash | `f1a8594e8976c89f1e5c028870c3d3764a7a5423473cd8635448d7f6d8cc6574` |
| relationIds | `[]` |

For later SOV mapping, the first four IDs and `relationIds` map in order to
`KdbProtocolSource(protocolId, protocolVersionId, owningModuleId,
taxonomyVersionId, relationIds)`. Lifecycle, rights, synthetic safety,
purpose, hash, ruleVersion, observedAt and validUntil are preview evidence,
not a complete SOV Candidate or a consumer adapter. Those timestamps are
generated on each disposable run and are never an enduring authority.
SOV and Arcava have not consumed this result. The synthetic taxonomy IDs do
not assert D06 authority. Independently reported F-P25-01 HIGH, transitive
role membership, remains open; this fixture does not use that admission code.

Run `python3 tests/kdb/pg17_pa05_catalog.py` with a local Docker daemon and
the PostgreSQL 17 image available. SQL001 is applied only inside the
newly-created, network-isolated container.
