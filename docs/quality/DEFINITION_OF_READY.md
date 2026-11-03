# Definition of Ready

A packet is ready only when every mandatory item is true.

## Control

- [ ] Packet ID, version, owner lane and active roles are stated.
- [ ] Accepted predecessor and required gate are linked.
- [ ] Repository, branch and immutable base SHA are stated.
- [ ] Worktree is clean or every existing change is explained and accepted.
- [ ] Objective and measurable outcome are singular and bounded.
- [ ] In-scope and explicit non-goals are stated.

## Sources and ownership

- [ ] Exact input documents, contracts, ADRs and repository paths are named.
- [ ] Source precedence and supersession rules are clear.
- [ ] Cross-lane dependencies are resolved or explicitly independent.
- [ ] The active writer owns every path to be changed.

## Execution

- [ ] Allowed paths and forbidden paths/actions are explicit.
- [ ] Toolchain/environment requirements are known.
- [ ] Functional requirements, NFRs, constraints and invariants are stated.
- [ ] Required positive and negative tests are specified.
- [ ] Evidence destination and return schema are specified.
- [ ] Stop conditions, reviewers, gate values and successor rule are specified.

If any mandatory item is false, do not start implementation. Return `BLOCKED` or generate one minimal readiness repair packet.