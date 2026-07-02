# Deploy Checklist -- P01 Manual Client Provisioning

Date: 2026-07-01 | Decision: PARALLEL START ALLOWED

## Before Starting
- [ ] git status clean
- [ ] npm run validate:all PASS -- record output
- [ ] Read CLAUDE.md (v1.1 overlay)
- [ ] Read prompts/cursor/PB-CURSOR-MASTER-RULES.md
- [ ] Read architecture/p01-decoupling-decision.md
- [ ] Confirm: no canonical dependency in planned work

## P01 Implementation
First command:
git status && npm run validate:all

Then:
cat prompts/cursor/PB-CURSOR-JH-001-MANUAL-CLIENT-PROVISIONING.md

Prepend gate instruction: see architecture/p01-decoupling-decision.md

## After Implementation
- [ ] npm run validate:all PASS -- record output
- [ ] python scripts/validate_mvp_slice_01.py PASS
- [ ] Tester smoke test passes
- [ ] Update MASTER LIVE STATUS block (no new Notion pages)
