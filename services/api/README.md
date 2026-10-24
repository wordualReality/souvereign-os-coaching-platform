# Arcava Backend — Source-Locked Spring Boot Bootstrap Candidate

This is an **unapplied, unbuilt candidate** for `ARC-36/ARC-P25`, `ARC10-T150`.
The original `Project B API Skeleton` was an uncompiled Java console placeholder.

Proposed toolchain: Spring Boot **4.1.1**, Java **25** and Apache Maven **3.9.16**.
The Maven parent BOM governs framework/plugin dependency versions. An actual
Maven wrapper or pinned distribution integrity check, resolved dependency
checksums, Java compilation and test receipts are **not yet available**.

The new application class explicitly starts in **non-web mode**. No controllers
are registered as HTTP endpoints; all pre-existing controller placeholders
remain unchanged. No database driver, external provider, broker or worker is
added. No application network service is enabled by this slice.

No Maven build, startup, dependency download, security scan, G01/PIAC read,
A09-T01/T44/T48 runtime test or T150 acceptance is claimed. Do not run `mvn`
or download dependencies without a separately admitted owner-scoped build gate.

After owner admission and verification of Maven distribution integrity, the
future build step may verify real `mvn -B test` and `mvn -B package` in a
network-restricted environment and add test evidence without enabling
external calls. Until then treat all code as a candidate only, not active
runtime or implementation acceptance.

Canonical contracts remain `/contracts/openapi/project-b-v1.json` and
`/contracts/openapi/project-b-v1.1-overlay.json`. The candidate does not
implement or replace these contracts.
