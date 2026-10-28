# SOV PIAC decision proof v1 pin

Pinned producer SHA: `f68760d799831ff260f99eb5b02358a1a3bda979`
Producer: wordualReality/souvereign-os PR #16
KDB packet: KDB-P5-SOV-PROOF-CONSUMER-OFFLINE-01

This directory is a read-only contract pin. It is not a live issuer, not a
trust anchor, and not normative adoption by KDB. The producer is OPEN/DRAFT
and has known authorization findings at pin time. `NEEDS_SOV_SECURITY_QS`
remains a named dependency.

Observed producer HEAD `0ad4516ee819684f5ce1ce381c688400e800700b` was compared
on 2026-10-27. The eight schema, vector, and sidecar-hash files are
byte-identical to this pin. The pin is not advanced. SOV security QS is still
pending. Entitlement-tenant and consent subject/recipient binding remain
producer findings.

A later repaired SOV contract must be compared by SHA, schema hashes, and
golden vectors before any pin change. Silent updates are forbidden.

Synthetic proofs may exercise local parsing and signature checks only.
They must not yield `DB_COMMAND_ADMITTED`.
