# PB-CURSOR-JH-003 Journey Template Model

Implement journey template lifecycle and clone-to-draft semantics.

Required behavior:
- template versions immutable after publish
- clone creates tenant-owned draft
- canonical refs revalidated on clone/publish
- deprecated templates warn or block based policy
