# ADR-036: An agent that reaches AUTHORITY_SOURCE_MISSING discloses rather than refuses

**Status**: Proposed

**Date**: 2026-09-26

**Split from**: [ADR-031](031-authority-source-missing-obliges-disclosure-not-refusal.md), when ADR-031 was reduced to its engine rule under [ADR-035](035-a-release-may-depend-on-a-proposed-adr-only-on-declared-and-expiring-terms.md) (see [RATIFICATION-v0.8.0.md](RATIFICATION-v0.8.0.md))

## Context

ADR-031 held two decisions under one title. The engine rule (a configuration gap is reported and blocks nothing) had evidence, and the runtime depended on it. The agent obligation had none of its four acceptance conditions met, and nothing in the runtime depended on it. ADR-035 does not let a release depend on a `Proposed` ADR past two releases. Splitting the two lets the evidenced part be accepted and leaves the unevidenced part `Proposed`, where it belongs.

The full argument, both cases and the cost, is in ADR-031's Context and in its sections "The case that the agent was right" and "The case that the instruction is right". This ADR does not repeat them.

## Decision

**Proposed:** an agent that reaches `AUTHORITY_SOURCE_MISSING` says plainly that the repository is not governed and that what follows is therefore unchecked, and names onboarding as the way to change that. It is not obliged to stop.

**The runtime does not depend on this ADR.** `SKILL.md` still tells an agent to run onboarding and stop. Changing that text is the act that would create the dependency, and it waits for condition 1.

## Confirmation

| Obligation | Kind | How anyone would know |
|---|---|---|
| An agent discloses | substantive | Observed in graded agent runs. No mechanical confirmation. |
| An agent does not stop | substantive | The same runs |
| No runtime dependency while `Proposed` | structural | The ADR-035 check in `conformance/skill.py` lists no citation of ADR-036 in code that governs |

## Acceptance conditions

`Proposed` until all four are met. **None is met today.** These are ADR-031's conditions, unchanged.

1. **Arm A completes, or is explicitly restarted.** No wording change to `SKILL.md` lands while a measurement graded against the current text is in progress (issue 36). *(Not met. The blocker is internal: restarting is the maintainer's choice.)*
2. **The disclosure is shown to actually happen.** An agent told to disclose must be observed disclosing, not merely permitted to. *(Not met.)*
3. **The re-grade is done deliberately.** Every recorded `PARTIAL` that turned on this instruction is re-examined under the new rule, and the change is recorded (issue 93). *(Not met.)*
4. **Measured on a host this project does not own.** *(Not met. External evidence.)*

## Related Specification Sections

§54 (failure conditions), §32 (discovery dispositions), INV-002, INV-013.
