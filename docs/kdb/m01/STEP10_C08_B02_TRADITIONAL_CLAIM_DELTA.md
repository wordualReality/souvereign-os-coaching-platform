# Step 10 / C08-B02 synthetic claim semantics — draft only

Status: `SYNTHETIC_TEST_ONLY / PREVIEW_ONLY / NON_EXECUTABLE / NOT_ADMITTED / UNTRUSTED_SYNTHETIC_SNAPSHOT`. This local CAP-BL-020 fixture contains invented codes only: no actual plant, disease, treatment, assessment or recommendation. It is not an accepted cross-lane API, published ProtocolVersion or professional advice.

Run from repository root:

```text
python3 services/kdb/offline_traditional_claims.py tests/kdb/fixtures/c08_b02_synthetic_traditional_claim.json
```

The draft output schema is `contracts/kdb/c08_traditional_claim_preview.v1.schema.json`. The result for the example is `PREVIEW_CONTEXT_ONLY / SYNTHETIC_TRADITIONAL_CONTEXT`, framework `TCM`, invented statement code `SYN-TRAD-ALPHA`, `UNVERIFIED_SYNTHETIC` review, `TRADITIONAL_TEXT_SYNTHETIC` evidence and explicit `NO_BIOMEDICAL_EFFICACY_OR_DIAGNOSIS_INFERRED`. Its immutable untrusted pins include source `SYN-SRC-TRAD-ALPHA` / `SYN-VER-TRAD-ALPHA-1`, claim `SYN-CLAIM-TRAD-ALPHA` / `SYN-CLAIMVER-TRAD-ALPHA-1`, both content hashes, as-of/rights/license/lifecycle snapshot, statement ID and fixture evidence locator. A missing claim version returns `ABSTAIN / CLAIM_VERSION_UNKNOWN` with the selected synthetic source pin; it does not generate a replacement claim.

| Category | Contract boundary |
| --- | --- |
| Traditional interpretive statement | Only a fixed fictional statement code under a matching TCM or Ayurveda source/claim/query framework; no mapping between frameworks or to biomedical diagnosis. |
| Biomedical research statement | A traditional statement is not efficacy evidence. This slice does not authenticate scientific sources, verify study evidence or emit a positive biomedical research result; `BIOMEDICAL_RESEARCH` abstains `RESEARCH_EVIDENCE_NOT_VERIFIED`. A future research claim requires separately attributable scientific evidence and independent review. |
| Personal preference | Consumer-owned and outside KDB authority. Only an optional synthetic display marker is accepted and discarded; real personal data, constitution, symptoms and assessment fields are rejected. |
| Professional advice | Out of scope. Diagnosis, treatment, efficacy, health claims and asserted medical authority are not inferred or produced. |

Source and claim digests use the accepted B01 Python sorted-key compact UTF-8 JSON encoding. Hash equality checks supplied fixture consistency; source custody, genuine rights, trustworthy freshness, external authority, review and evidence-byte spans are not attested. The synthetic source and claim both pin the same framework; changing only one yields `TRADITION_MISMATCH`. Source/claim versions, tenant/purpose, rights/lifecycle, statement/evidence binding and injected authority/private fields are fail-closed. `UNAVAILABLE`, `SOURCE_PINNED_UNTRUSTED` and `CLAIM_PINNED_UNTRUSTED` describe how far validation reached, never trust or admission.

KDB owns this draft source/claim/provenance model. Arcava owns any future consumer presentation and private preference handling; SOV retains its own platform responsibilities. B01 remains accepted and unchanged. B03 acupressure and B04 controlled research remain scheduled, not executed. M01 Step10, Step6/Step9 security and hosted admission remain partial or blocked; no C04/C05 publication, LLM call, production database, n8n, real user data or merge is enabled.
