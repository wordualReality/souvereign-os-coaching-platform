# KDB-M01 — PHYSICAL FOUNDATION AND MVP INGESTION / OFFLINE GATE A KIT v1.0


**BUILDER status:** `STEP1_TO_STEP4_OFFLINE_COMPLETE / FIRST_MUTATION_NOT_EXECUTED / KDB-M01-MUTATION-GATE-A_OPEN_FOR_EXPLICIT_FOUNDER_DECISION`.


The complete design, candidate migrations, proposed owner contract schemas, synthetic tests and bounded Cursor/Supabase executor prompt are produced in this bundle. **Nothing from this ZIP was applied to GitHub, Supabase, Docker or live n8n.** The chosen shared Supabase project remains undecided, and a material preimage/role/TLS/PIAC security boundary remains prior to physical execution.


## Read order


1. `01_AUTHORITY_ENVIRONMENT_FREEZE.md` — primary source hierarchy, live read-only PostgreSQL 17.6 catalog and repo HEAD (remote main SHA), environment ownership and legacy freeze.
2. `02_PHYSICAL_ARCHITECTURE_ADR.md` — new KDB schema namespace and anti-corruption/legacy compatibility decision.
3. `03_CONTRACT_FIRST_MVP.md` — Source, SourceVersion, CandidateRevision, HumanReviewDecision, ProtocolVersion, Lifecycle, Outbox, Audit and O1/O2/O3 vs O4/O5 authority.
4. `04_OFFLINE_TEST_AND_ACCEPTANCE.md` — what was and was NOT executed, physical acceptance oracles.
5. `sql/000_readonly_target_preflight.sql`, then SQL proposals `001`, `002`, `003`. `098` must stay NOT EXECUTED; `099` is an explicit nonexecuting rollback/forward-fix strategy.
6. `contracts/` and `tests/`; `runbooks/PIAC_AND_API_BOUNDARY.md`.
7. `runbooks/GATE_A_CURSOR_SUPABASE.md` — **the single exact execution order and STOP boundary**. It requires an explicit Founder bounded grant before even one repo or database mutation.


## Governance non-negotiables


- n8n transport/coordinator only. No direct KDB table DML, no service_role, no automatic HumanReviewDecision or Canonical Admission.
- Physical MVP capability scope O1–O3; O4/O5 inactive until separate successful physical signed promotion test and later activation gate.
- Cross-owner references typed; KDB ProtocolVersion immutable; rights/provenance and the human review owner stay KDB truth.
- Founder C1/C3/C4 remain binding. C2_PHYSICAL / B03 / RC1B remain OPEN, QS02 remains UNAUTHORIZED.
- New schema names are physical ADR choices to preserve historical `canonical`/`dev_staging` unchanged. No code in this pack applies to those legacy schemas.
- Requirement baseline stays 86 = 47 P0 + 39 P1.


## Validation and artifact integrity


Run offline: `python -m unittest discover -s tests -p 'test*.py' -v` using Python3 plus `jsonschema`. Test suite covers 32 cases (15 JSON-schema/security cases + 10 promotion-model cases + 7 SQL static checks). `MANIFEST_SHA256.json` pins all member bytes; `MANIFEST_SHA256.txt` enables `sha256sum -c` from bundle root; both exclude self-referential manifest and any ZIP metadata. ZIP assembly reproducibility check must PASS before delivery.


## Scope limitation


This is executable-looking **candidate DDL**, not executed production SQL nor an endorsed security-definer deployment. An approved grantor must confirm role and policy semantics in a disposable PG17 test database and ensure PIAC signature verification exists at an independent KDB facade. Full physical tests are not representable by static checks. No repository mutation, DB mutation, activation, promotion or new Cursor instance was performed by this Builder.
