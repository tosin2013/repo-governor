# Starting work

You are about to point an assistant at a task — an issue, a request, a "can you just". The question to settle **before any code** is whether the work is authorized, and the assistant should be the one to check, not you from memory.

**Lane:** entry point to every lane. The check is identical whatever kind of work it is.

## Prompt recipes

Shape, not incantation — adapt the wording, keep the constraints.

> Using Repo Governor, determine whether this repository is governed and which roadmap provider is authoritative. Then evaluate issue N and tell me whether it is authorized to execute, and under what scope. **Do not start implementing until you have reported the disposition.**

For a session opener with no specific task:

> Review this repository with Repo Governor. Identify the admitted work and tell me what is currently authorized to execute and what is blocked, with the blocking reasons. **Do not promote discoveries, do not change roadmap state, and do not pick a task yourself — report, then wait.**

For a request that arrives outside the tracker ("can you quickly add…"):

> Before implementing this request, check it against the roadmap provider with Repo Governor. If no admitted work item covers it, say so and stop — filing or admitting it is my decision, not yours.

## What the engine will say

| Disposition | Meaning here |
|---|---|
| `CONTINUE` | authorized and unfinished — proceed within scope |
| `NO_EXECUTION_AUTHORITY` | admitted, not cleared — do not start |
| `UNKNOWN` + `NOT_ADMITTED` | not on the roadmap at all — the request needs admission first |
| `AUTHORITY_WITHDRAWN` | cancelled — stop, whatever the tracker's status column says |
| `STOP_COMPLETE` | already done — see [finishing-work](finishing-work.md) |

`AUTHORITY_SOURCE_MISSING` means the repository is not onboarded; run onboarding and stop — binding is a human act (ADR-010).

## The forbidden shortcut

**Request → implementation.** A request existing — in chat, in a TODO, in a reasonable-sounding sentence — is not admission. The lifecycle's first illegal transition, `DISCOVERED → EXECUTING`, is most often taken in the first five minutes of a session, before anyone has asked whether the work is on the roadmap at all.
