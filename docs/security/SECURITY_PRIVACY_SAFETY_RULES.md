# Security, Privacy and Safety Rules

## Authorization and tenancy

- Deny by default when identity, tenant, role, assignment, consent or entitlement is missing or ambiguous.
- Every tenant-sensitive path requires positive and cross-tenant negative tests.
- Coach access is limited to assigned clients and permitted projections.
- Client access is limited to own runtime data and approved content.
- Service-role credentials never enter browser code, prompts, logs, screenshots or evidence.

## Database

- RLS is mandatory for exposed tenant-sensitive tables.
- Policies must not use unconditional `using (true)` for tenant data.
- Claims/JWT parsing must use reviewed helpers rather than copied ad hoc expressions.
- Migrations, grants, policies and restricted RPCs require Database/Canonical or Shared Database Control authority as applicable.
- Direct table access by n8n or external agents is prohibited unless an accepted ADR explicitly authorizes it.

## Privacy and data minimization

- Use synthetic data for development and demonstrations.
- Do not store raw personal, health-like or sensitive client data in evidence.
- Collect and expose only fields required for the use case.
- Reflections and progress views must respect role and assignment boundaries.
- Evidence and screenshots must be redacted.

## Content and safety

- Raw candidates, staging records and unresolved claims are not client-visible truth.
- Provenance, rights status, review and safety metadata must accompany governed knowledge candidates.
- No autonomous canonical promotion.
- High-risk claims or contraindications require the designated human review path.

## Security evidence

Security claims require executed tests, named environment, base/result SHA and reviewer evidence. Static file presence alone is not proof.