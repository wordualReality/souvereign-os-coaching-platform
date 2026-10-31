# P23 reproducible offline demo acceptance kit

Packet: `KDB-M01-P23-REPRODUCIBLE-OFFLINE-DEMO-ACCEPTANCE-KIT-01`

This kit is a local synthetic preview. It is `PREVIEW_ONLY`,
`SNAPSHOT_UNTRUSTED`, `NOT_ADMITTED`, `NON_EXECUTABLE`, `NOT_ASSIGNED`, and
`NOT_SECURITY_PASS`. Its hashes prove only local file integrity, not custody,
rights, licence, issuer, semantics, event order, hosted admission, or release.

## Build, verify, and view

Use two different local snapshot paths. The copy is only a build input.

```sh
mkdir -p tests/kdb/demo-artifacts
cp tests/kdb/fixtures/p20_inbox_byte_spans.json tests/kdb/demo-artifacts/p23-current.json
python3 services/kdb/offline_demo_acceptance_kit.py build \
  tests/kdb/fixtures/p20_inbox_byte_spans.json \
  tests/kdb/demo-artifacts/p23-current.json \
  --work-item-id aaaaaaaa-bbbb-4ccc-8ddd-777777777777 \
  --source-file tests/kdb/fixtures/p20_source_a.bin \
  --output tests/kdb/demo-artifacts/kdb-p23-offline-demo.zip \
  --commit "$(git rev-parse HEAD)"
python3 services/kdb/offline_demo_acceptance_kit.py verify tests/kdb/demo-artifacts/kdb-p23-offline-demo.zip
python3 services/kdb/offline_demo_acceptance_kit.py smoke tests/kdb/demo-artifacts/kdb-p23-offline-demo.zip
python3 services/kdb/offline_demo_acceptance_kit.py extract tests/kdb/demo-artifacts/kdb-p23-offline-demo.zip tests/kdb/demo-artifacts/kdb-p23-offline-demo
```

Open `index.html` after extraction. Navigation is `index.html` →
`current.html` → `current-case-evidence.json`.

```text
index.html
current.html
changes.html
review-viewmodel.json
manifest.json
README.txt
current-case-evidence.json
```

The verifier requires this exact stable order, rejects unsafe, duplicate,
extra or missing members, and recomputes every manifest-declared checksum.
Explicit extraction occurs only after verification and only in a new bounded
directory below `tests/kdb/demo-artifacts/`.

## KDB-M01 local Steps 2–9 evidence ledger

| Step | Physical evidence | State | Remaining delta / owner |
|---|---|---|---|
| 2 | `20261023140000__kdb_m01_001__core_foundation.sql`; disposable PG17 apply/reapply | LOCAL_VERIFIED | Hosted apply prohibited; KDB admission |
| 3 | `20261023140100__kdb_m01_002__security_boundary.sql`; ACL/RLS negatives | LOCAL_VERIFIED | Independent security and hosted verification absent |
| 4 | `20261023140200__kdb_m01_003__api_boundary.sql`; runtime denials | LOCAL_VERIFIED | Positive O1–O3 and production command admission prohibited |
| 5 | P3/P4/P5 fail-closed migrations and static/PG17 oracles | LOCAL_VERIFIED | Issuer/custody and durable live replay unverified |
| 6 | P07 tenant guard, P08 provenance, P09 lifecycle source tests | LOCAL_VERIFIED | Live rights/licence and external issuer evidence absent |
| 7 | P11/P12 committed chains, reconnect/replay/revocation PG17 | LOCAL_VERIFIED | No C04/C05 write, outbox, hosted persistence, or live PIAC |
| 8 | P13–P22 offline review and byte/span evidence paths | LOCAL_VERIFIED | Snapshot watermark/order and semantic correctness untrusted |
| 9 | P23 deterministic ZIP, verifier, bounded extraction, browser smoke and CI artifact | PARTIAL | Owner QS pending; no security/hosted/product acceptance; canonical schema incomplete |

The evidence covers 12 physical SQL001 tables. The historical 18 ATC10
logical objects remain `UNCONFIRMED`; this kit does not claim 18/18.
