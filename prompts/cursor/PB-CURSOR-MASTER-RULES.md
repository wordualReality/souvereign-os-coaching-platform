# Project B Cursor Master Rules

1. Implement only from leading truth artifacts.
2. Treat every generated file as subordinate to architecture contracts.
3. Never invent API endpoints, event names, table ownership, roles or tenant behavior.
4. Patch registers are work queues, not optional notes.
5. Every command path must preserve guard -> mutation -> audit -> outbox -> projection where applicable.
6. Every admin/support action requires reason, scope, audit and tenant isolation.
7. If a prompt hits a stop condition, create a `NEEDS_ALIGNMENT.md` note and do not continue.
