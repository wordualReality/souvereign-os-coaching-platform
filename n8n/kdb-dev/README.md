# KDB n8n development candidates

Source: milestone ZIP SHA-256 `74ba04934de6cb13b7f6ea9d0f983234853b26c49d404f43f2681347346944b0`.

`tenant-guard-candidate` is a source/test copy. It is not an imported or activated workflow pack. O4 and O5 remain inactive. No n8n runtime, HTTP, or database calls are made by the offline classifier tests.

Reproduce:

```bash
node n8n/kdb-dev/test_workflow_regression.cjs n8n/kdb-dev/tenant-guard-candidate /tmp/kdb-tenant-guard.json kit
node n8n/kdb-dev/test_replay_dlq.cjs n8n/kdb-dev/tenant-guard-candidate /tmp/kdb-replay-dlq.json
```

`kit` may be omitted. For contract cross-check use the original kit_clean contracts directory.
Replay/DLQ tests are offline policy checks. They are not a live n8n import.
