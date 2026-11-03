# Authority and Stop Conditions

## Authority model

A block may perform only the actions explicitly named by an accepted predecessor gate. Roles, prompts, plans and expected outcomes do not create authority.

Current FPS-00C authority is limited to governance, documentation, repository rules, source indexes, quality controls and evidence controls.

## Founder-reserved actions

Require explicit founder approval when applicable:

- production deployment or production database mutation;
- credential creation/disclosure or external account authorization;
- irreversible data deletion;
- legal/compliance representation;
- commercial spending or binding third-party service activation;
- release/publication claims beyond accepted evidence.

## Mandatory stop conditions

Stop the affected packet when any of the following occurs:

- predecessor gate is missing, contradictory or does not authorize the action;
- repository, branch or base SHA differs from the packet;
- worktree contains unexplained changes;
- required owner lane is not the active writer;
- requested path is outside the allowlist;
- architecture, contract or source precedence conflict is discovered;
- a secret, production identifier or personal data would enter evidence;
- a migration/RLS/RPC change lacks DB-owner authority;
- an n8n workflow would require direct table access or unapproved credentials;
- required tests cannot run or produce ambiguous results;
- the agent proposes broader work than the packet;
- evidence is incomplete, unverifiable or status-inflated.

## Stop response

1. Make no further changes.
2. Preserve git state and evidence.
3. Record the exact blocker and source references.
4. Issue `BLOCKED` or `REPAIR_REQUIRED`.
5. Generate exactly one minimal repair/owner-return successor.

Never work around a stop condition to maintain a schedule.