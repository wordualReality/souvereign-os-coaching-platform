# Cross-Lane Impact Matrix

Status: CURRENT GOVERNANCE CONTROL

Every packet that changes behavior, contracts, schemas, events, workflows, identity/access, observability or deployment must complete the relevant row before execution.

| Change area | Project A impact | Project B impact | Database/Canonical impact | Shared/support impact | Required owner return |
|---|---|---|---|---|---|
| Identity, tenant, role or entitlement | runtime/routing access | admin/coach/client access and projections | RLS/RPC claims and grants | auth/config/monitoring | shared access owner + affected lane |
| Canonical taxonomy, protocol, program or reference envelope | approved runtime references | journey authoring/delivery references | authoritative semantics, provenance and publication | workflow/revalidation | Database/Canonical producer return |
| Project-B journey/client/assignment model | possible operator projection | primary behavior and contracts | project_b schema/RLS/RPC implications | API/events/workflows | Project B owner + DB owner for persistence changes |
| Shared migration, role, RLS helper or audit/outbox convention | shared persistence impact | shared persistence impact | migration/DB authority | CI/reset/recovery | Shared Database Control |
| API/RPC/event change | consumer compatibility | producer/consumer compatibility | producer/consumer compatibility | n8n/agents/integrations | contract owner and all affected consumers |
| Workflow/n8n change | support event effects | support event effects | restricted interface/load effects | credentials, retry, DLQ, observability | workflow owner + producer interface owner |
| UI/UX or user-facing state change | operator experience | admin/coach/member experience | data exposure and status semantics | telemetry/accessibility | owning product lane; privacy/security if material |
| Agentic orchestration or tooling | repository/process effects | repository/process effects | migration/data safety effects | tool permissions and evidence | Implementation Control; no architecture authority |

## Required packet fields

- affected lanes and exact sources;
- producer/consumer contracts;
- ownership and one-writer path;
- data/state changes;
- positive and negative cross-lane tests;
- failure propagation and blast radius;
- rollout/rollback or parking impact;
- unresolved conflicts with exact source locations.

## Conflict rule

Do not decide another lane's semantics. Record `CONFLICT`, stop the affected path and use the shared alignment register. Work may continue only on demonstrably independent paths.
