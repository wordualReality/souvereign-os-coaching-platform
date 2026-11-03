# Sovereign OS Prompt Engineering Standard

Status: CURRENT / METHOD STANDARD / NON-AUTHORITATIVE FOR ARCHITECTURE

This file governs how masterprompts, implementation packets, reviews, returns, gates and successors are written. It does not override accepted requirements, architecture, owner boundaries, repository reality, contracts, security controls or execution evidence.

## Source order

1. Accepted execution evidence and gates.
2. Accepted owner decisions, ADRs and producer-owned contracts.
3. Exact repository, database, workflow and runtime reality.
4. Current system documentation and source manifests.
5. Current official technical and model-provider documentation.
6. Secondary prompt-method references.

Secondary reference:

- PromptGenius, Technical Prompts for ChatGPT: https://promptgenius.net/prompts/chatgpt/technical
- Classification: community-derived prompting guidance only.

Official supporting references:

- https://help.openai.com/en/articles/6654000-playground-and-prompt-engineering
- https://help.openai.com/en/articles/4936848-how-do-i-create-a-good-prompt-for-an-ai-model-like-gpt4
- https://docs.cursor.com/context/rules
- https://docs.cursor.com/en/guides/working-with-context

## Adopted patterns

Every prompt must, where applicable:

- state the exact role and bounded authority;
- provide relevant system, stack, environment and dependency context;
- separate functional requirements, non-functional requirements and constraints;
- state in-scope and explicit non-goals;
- define exact outputs and return format;
- include examples or schemas when format ambiguity exists;
- include exact debugging context: error, expected behavior, actual behavior, environment, recent changes and reproduction steps;
- require relevant unit, integration, E2E, security and negative tests;
- split unrelated work into separate bounded packets;
- derive the next prompt from actual evidence, defects and lessons learned.

## Required adaptations

Do not request or store private chain of thought. Request instead:

- concise assessment;
- assumptions;
- options and trade-offs;
- selected decision and brief justification;
- evidence and source references;
- unresolved uncertainties.

Never accept `production-ready`, `secure`, `compliant`, `implemented` or similar claims from a prompt response alone. Use the controlled status vocabulary and executed evidence.

Expert-role wording selects a review lens. It does not create credentials, certification, legal authority or owner rights.

## Masterprompt anatomy

Every masterprompt must include:

1. Prompt ID, version, date and owner lane.
2. Identity, bounded roles and authority.
3. Mission and measurable outcome.
4. Current verified state and predecessor gate.
5. Source precedence and exact required context.
6. Definition of Ready.
7. Scope, non-goals, allowed paths/tools and forbidden actions.
8. Functional, non-functional, security, privacy, tenant and data-owner constraints.
9. Ordered execution sequence.
10. Exact output and return schema.
11. Required tests and evidence.
12. Independent review and allowed gate values.
13. Lessons learned and exactly one successor.
14. One small operator-facing next action.

## Packet dispatch gate

A packet is not dispatch-ready if any of these is missing:

- objective and bounded scope;
- current source precedence;
- owner authority;
- repository/base state;
- explicit non-goals;
- allowed and forbidden paths/actions;
- acceptance criteria;
- tests and evidence requirements;
- return format;
- stop conditions;
- gate and successor rule.

## Recursive successor rule

Generate the next prompt from:

- predecessor prompt and version;
- actual return;
- commands, tests and evidence;
- independent reviews;
- gate decision;
- deviations, blockers and lessons learned;
- current source manifest and repository SHA;
- next highest-value authorized dependency.

Never generate the successor solely from the original calendar or expected result.
