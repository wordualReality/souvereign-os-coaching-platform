# Operator Contract -- Project B

Date: 2026-07-01

## Who Operates What
| Operator | Scope | Channel |
|---|---|---|
| Claude | Content Pipeline, PM | claude.ai |
| DB Architect GPT | canonical.* schema, Gates A-E | Separate GPT |
| App Builder GPT | Project B runtime, P01 | Separate GPT |
| Cowork | Repo work, validation | Cowork session |
| Aydin | Product Owner, all approvals | All channels |

## Rules
1. Status lives ONLY in MASTER LIVE STATUS block
2. No new Notion pages per status update
3. DB Architect GPT and App Builder GPT do not communicate directly
4. SQL/DDL for canonical.* blocked until FX-01 + AT-05 + DDL-01 + Aydin approval
5. Stop conditions: create NEEDS_ALIGNMENT.md, do not continue

## Never Without Aydin Approval
- Write canonical.* SQL or DDL
- Push remote Supabase
- Authorize Broad UI Build
- Promote Notion candidates to Canonical Approved
- Skip Gate C, D, or E
