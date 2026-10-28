# KDB n8n development candidates

Source: milestone ZIP SHA-256 `74ba04934de6cb13b7f6ea9d0f983234853b26c49d404f43f2681347346944b0`.

`tenant-guard-candidate` is the version-controlled inactive classifier pack. It is not imported or activated. O4 and O5 remain inactive. No n8n runtime, HTTP, or database calls are made by the offline classifier tests.

The Fail Closed Classify nodes deny missing, blank, non-string, and oversize `tenant_scope`. That matches `contracts/kdb` O1/O2/O3 plus a stricter trim rule. The original uncorrected classifier is kept only as a test probe under `tests/kdb/fixtures`.

Reproduce:

```bash
node n8n/kdb-dev/test_workflow_regression.cjs n8n/kdb-dev/tenant-guard-candidate /tmp/kdb-tenant-guard.json .
node n8n/kdb-dev/test_replay_dlq.cjs n8n/kdb-dev/tenant-guard-candidate /tmp/kdb-replay-dlq.json
python3 tests/kdb/test_tenant_guard_source.py
```

The fourth argument is the repository root so the harness reads `contracts/kdb`. Replay/DLQ tests are offline policy checks. They are not a live n8n import.
