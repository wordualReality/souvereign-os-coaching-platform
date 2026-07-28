# Supersession Register

Status: CURRENT for implementation entry.

| Earlier source or rule | Current controlling source | Treatment |
|---|---|---|
| README leading truth order based only on Final Dev-Handoff v1.0/v1.1 | `docs/control/CURRENT_SOURCE_MANIFEST.md`, PB-RDH-09, current gates | Superseded for implementation precedence |
| `CLAUDE.md` statement that v1.1 globally supersedes v1.0 | Current source manifest and packet-specific owner decisions | Superseded; overlays are not global authority |
| Old instruction to start directly with `PB-CURSOR-JH-001` | FPS-00C governance gate, then accepted successor | Blocked until governance acceptance |
| Historical P01 release statements | Current three-lane register and Project B gate | Superseded; no feature implementation yet |
| Static validators interpreted as implementation proof | Evidence protocol and independent gate | Superseded; validators are structural checks only |
| Existing WF-01 through WF-05 as executable workflows | Current workflow boundary | Classified `BLUEPRINT_ONLY`; no import/activation/execution authority |
| Direct n8n table reads | Restricted RPC/API/event boundary | Prohibited unless later owner-approved ADR changes it |
| AgentScope as required implementation controller | Shared conflict resolution Option (a) | Optional, non-authoritative, deferred for Project B/KDB |
| Community prompt examples as project truth | Prompt Engineering Standard | Secondary method guidance only |

## Rule

A superseded source remains historical evidence. It must not be deleted merely because it is superseded, but must not control implementation. When a new conflict is found, add the exact earlier source, current source, owner and gate before continuing.