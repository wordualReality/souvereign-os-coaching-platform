# Quality Gate Matrix

| Gate area | Required review | Minimum evidence |
|---|---|---|
| Scope and authority | Control reviewer | predecessor gate, owner lane, allowlist, forbidden actions |
| Requirements | BA/RE reviewer | requirement IDs, acceptance criteria, traceability |
| Architecture | Software architect | bounded contexts, ownership, contract and dependency conformance |
| API/events | Contract reviewer | schemas, operation/event IDs, compatibility and negative cases |
| Database | DB/RLS reviewer | migration order, reset/rebuild, grants, RLS and cross-tenant negatives |
| Security/privacy | Security/privacy reviewer | authorization negatives, secret hygiene, data minimization, audit |
| UX/accessibility | UX reviewer | loading/empty/error/denied/success states and accessibility evidence |
| Testing | Test/DevSecOps reviewer | commands, exit codes, unit/integration/E2E evidence appropriate to scope |
| Operations | SRE/release reviewer | observability, failure/recovery, rollback and runbook evidence where applicable |
| Status/evidence | Evidence manager | base/result SHA, diff, logs, hashes, no status inflation |

## Gate values

- `PASS`: all mandatory acceptance criteria and evidence satisfied.
- `PASS_WITH_BLOCKERS`: bounded result accepted; named blockers prevent later or broader work.
- `REPAIR_REQUIRED`: defects are repairable inside a specifically authorized repair packet.
- `BLOCKED`: mandatory authority, source, environment or owner dependency is missing.
- `FAILED`: execution produced unacceptable or unsafe results and must not be continued.

No reviewer may authorize work beyond the gate it issues.