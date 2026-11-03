# Claude / Codex Repository Context

Use `AGENTS.md` and repository-local governance as the controlling context. Historical v1.0/v1.1 handoff overlays are supporting history and do not globally supersede current gates, source manifests or repository evidence.

## Product boundary

Project B is a multi-tenant coaching/journey delivery platform. The bounded parking sprint targets one complete path from client provisioning through journey publication, enrollment, member completion/reflection and assigned-coach progress, with audit/outbox evidence.

## Current authorization

FPS-00C governance only. Do not implement features, SQL/migrations, workflows, deployment or production access until the governance gate is accepted.

## Mandatory controls

- Read `docs/control/READ_FIRST.md` and the exact packet prompt.
- Respect Project B versus Database/Canonical owner boundaries.
- Apply scoped `.cursor/rules` and the prompt engineering standard.
- State assumptions and concise rationale; do not request or store private chain of thought.
- Provide exact outputs, tests, evidence, deviations and blockers.
- Stop on missing authority or source conflict.
- Generate exactly one successor after independent review and gate.

A model response is not proof of implementation, security, compliance, deployment or production readiness.