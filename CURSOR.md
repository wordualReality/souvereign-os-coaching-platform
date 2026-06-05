# Cursor Operating Rules

Do not implement from memory. Every change must cite or reference a repo artifact:

- `/docs/traceability` for capability/story/screen/test mapping
- `/contracts/openapi` for HTTP API
- `/contracts/events` and `/contracts/asyncapi` for event contracts
- `/database` for schema and RLS
- `/prompts/cursor` for execution prompt

Forbidden:
- inventing new capability IDs
- moving Core entitlement/consent/runtime truth into Project B
- moving Canonical taxonomy/protocol/source truth into Project B
- implementing manual bypass without reason and audit trail
- exposing cross-tenant data
