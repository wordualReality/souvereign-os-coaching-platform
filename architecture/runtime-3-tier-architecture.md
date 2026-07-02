# Runtime 3-Tier Architecture

Date: 2026-07-01

## Architecture
Tier 1: Next.js App Router -- React Server Components -- Admin/Ops, Tenant Studio, Coach Studio, Client App
Tier 2: Java 21 / Spring Boot 3.5.x -- Tenant Workflow, Provisioning, Auth, Audit, CanonicalRefBinding
Tier 3: Supabase PostgreSQL -- Schemas: canonical | project_b | core -- RLS mandatory

## Schema Ownership
| Schema | Owner | Status |
|---|---|---|
| canonical.* | DB Architect GPT | NOT IMPLEMENTED |
| project_b.* | App Builder GPT | Migrations exist, not applied to Supabase |
| core.* | Shared | Defined in contracts/ |

## Supabase
- Ref: zobjpmyccszkabybdmsf
- dev_staging.protocol_candidate: EXISTS (intake schema, not canonical)
- project_b migrations: NOT YET APPLIED

## Not Project B Runtime
- Notion Tags DB, Notes DB, Staging DB (Ebene 1)
- n8n pipelines (Ebene 1)
- canonical.protocol modeling (DB Architect domain)
