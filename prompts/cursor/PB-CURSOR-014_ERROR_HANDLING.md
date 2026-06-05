# PB-CURSOR-014 — Error Handling

## Mission
Implement standard error envelope, codes, user/admin messages and tests.

## Context
You are implementing Project B: Coach Studio + Tenant Journey Platform + Governed Commerce + Branded Client App. Project B owns tenant/coach delivery and commercial workflow. Shared Core owns entitlement, consent, runtime access and deterministic routing truth. DB/Canonical owns protocol/taxonomy/source/canonical validation truth.

## Allowed source artifacts
- `docs/project-b/00-current-truth/`
- `docs/project-b/02-capability-map/ProjectB_Capability_Traceability_Matrix_v1_0.csv`
- `docs/project-b/03-user-stories/ProjectB_Complete_User_Story_Map_v1_0.csv`
- `docs/project-b/04-ui/ProjectB_Screen_Inventory_and_State_Matrix_v1_0.csv`
- `docs/project-b/05-admin/ProjectB_Admin_Web_Screen_Inventory_v1_0.csv`
- `docs/project-b/06-backend-flows/ProjectB_Backend_Flow_Catalog_v1_0.csv`
- `docs/project-b/07-contract-reconciliation/ProjectB_Contract_Gap_Register_v1_0.csv`
- `docs/project-b/08-errors/ProjectB_Error_Catalog_v1_0.csv`
- `docs/project-b/09-incidents/ProjectB_Incident_Runbook_Matrix_v1_0.csv`
- `contracts/openapi/project-b-v1.yaml`
- `contracts/events/`
- `database/migrations/`

## Hard constraints
- Do not create new product scope.
- Do not move Core entitlement/consent/routing truth into Project B.
- Do not move DB/Canonical taxonomy/protocol/source truth into Project B.
- Do not bypass tenant isolation, role guards, audit or outbox.
- Do not use the superseded empty Data Model v1.0.

## Required output
- Files created/changed list.
- Implementation notes.
- Tests added.
- Contract gaps detected.
- Security/tenant assumptions.
- Final status: PASS / BLOCKED / NEEDS_ALIGNMENT.

## Required tests
- At least one happy path.
- At least one denied/forbidden path.
- At least one tenant-isolation assertion if data is tenant-scoped.
- At least one error-envelope assertion if API is touched.

## Stop conditions
Stop and report instead of coding if:
- the relevant API endpoint is missing or contradicts the capability matrix;
- event or data ownership is ambiguous;
- role/tenant boundary is unclear;
- implementation would require creating a new canonical truth store inside Project B.
