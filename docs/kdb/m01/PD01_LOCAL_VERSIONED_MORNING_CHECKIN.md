# PD01 local synthetic versioned morning check-in detail

This is a disposable PostgreSQL 17 experiment, not a hosted endpoint, PIAC
authority, real human approval, publication or consumer integration. The test
creates a new container with Docker network mode `none`, applies SQL001 to
that isolated database, uses only synthetic data, and removes the container.
A KDB-owned test reader executes a SQL function under a fixture-only reader
role. That role has no direct access to the underlying canonical tables.

PD01 is the local producer proof that an app can retrieve the readable title
and instruction of exactly the requested ProtocolVersion, together with
source/provenance, content hash, taxonomy/module IDs and TEST_ONLY
rights/review/lifecycle. It does not admit a SOV UI consumer, D06 authority,
hosted apply, merge or live publication.

The frozen editorial protocol is named `Morgen-Check-in`. The single
proposal-only instruction is `Notiere eine Priorität für heute.` There is no
medical or clinical claim and no KDB DurationSpecification.

PA-05 v1 remains a separate immutable fixture. Its protocolVersionId,
contentHash and canonicalSnapshot `{"synthetic": true}` stay byte-identical.
PD01 uses a distinct synthetic version ID and digest. A refusal returns no
detail and never substitutes latest or another version.

The JSON printed as `PD01_RECEIPT` is a bounded test contract. Its immutable
identity and content pins are:

| Field | Value |
| --- | --- |
| protocolId | `0d010000-0000-4000-8000-000000000009` |
| protocolVersionId | `0d010000-0000-4000-8000-000000000010` |
| owningModuleId | `0d010000-0000-4000-8000-000000000013` |
| taxonomyVersionId | `0d010000-0000-4000-8000-000000000014` |
| sourceVersionId | `0d010000-0000-4000-8000-000000000002` |
| candidateRevisionId | `0d010000-0000-4000-8000-000000000005` |
| versionNo | `1` |
| title | `Morgen-Check-in` |
| instruction | `Notiere eine Priorität für heute.` |
| contentHash | `5393b2bdb7e8af010b795f740cd79d2adc419ab734d745d03a09db066c23eae8` |
| relationIds | `[]` |

Run `python3 tests/kdb/pg17_pd01_morning_checkin.py` with a local Docker
daemon and the PostgreSQL 17 image available. SQL001 is applied only inside
the newly-created, network-isolated container.
