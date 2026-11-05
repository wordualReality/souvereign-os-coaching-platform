# CAP-BL-023: offline candidate extraction boundary

This local provider-neutral draft turns one synthetic structured proposal into
an untrusted, non-executable candidate preview for hypothetical human review.
It validates source bytes and version, fixture rights and candidate digests,
and reuses P21's canonical byte-span reconciliation, adding UTF-8 boundary
and local-slice SHA-256 checks. The review queue and pending state reuse the
provenance eligibility constants; this preview does not invoke or claim success
of the full eligibility chain. O1/O2/O3 remain the existing ingest, candidate
and handoff contracts: this preview writes no ingest, queue, C04, C05 or event.
It emits no source text or evidence quote.
The synthetic identifiers are not O1/O2/O3 UUID command envelopes, and this
preview neither constructs nor validates those envelopes.

Fixture hashes establish local self-consistency, not real source custody,
rights authenticity, semantic evidence, safety or human approval. User source
text is data and is never executed. Actual provider invocation is disabled:
PROVIDER_EXECUTION_NOT_AUTHORIZED. SOV would own vendor, privacy, approved
purpose, cost ceiling, redaction, rate limiting, request approval and audit;
those contracts are not verified here. Arcava is a downstream consumer and
not an owner of candidate truth.

B01-B03 have scoped owner acceptance; B04 is local only. M01 Step 10 remains
partial, and no medical truth, release, hosted or security pass is claimed.

Run: `python3 services/kdb/offline_research_extraction.py tests/kdb/fixtures/c08_b04_synthetic_research.json`.
