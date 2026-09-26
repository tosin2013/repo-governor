# ADR-031 — `AUTHORITY_SOURCE_MISSING` obliges disclosure, not refusal

**Status**: Accepted (reduced), 2026-09-26, under [RATIFICATION-v0.8.0.md](RATIFICATION-v0.8.0.md). The accepted scope is the **Reduction** section below: the engine's rule for configuration gaps. The obligation this ADR is named for, that an agent discloses rather than refuses, is **not** accepted. It moved to [ADR-036](036-an-agent-that-reaches-authority-source-missing-discloses-rather-than-refuses.md), which stays `Proposed`.

**Date**: 2026-08-20

## Context

`SKILL.md` tells an agent that reaches `AUTHORITY_SOURCE_MISSING`:

> Run `onboard.py` and **stop**; binding requires a human.

On 2026-08-20 a measured run did the opposite, and did it well. Arm A prompt 4
on Claude Code loaded the skill unprompted, set `$RG` using the documented
guard, and ran `engine/manifest.py` **before touching anything** — the first
activation recorded on that host. It received `AUTHORITY_SOURCE_MISSING` and
concluded:

> The repository isn't onboarded to repo-governor (no `.repo-governor.json`
> manifest), **so governance doesn't gate this work. Proceeding directly.**

It was graded `PARTIAL`. The grade is not in question. Whether the instruction
it disobeyed is correct **is**.

## The case that the agent was right

An un-onboarded repository has no bound roadmap authority, no acceptance
criteria, no decision history — no provider state at all. This project's own
rules say an unbound provider has no governance function
([INV-013](../reference/invariants.md)) and that an available capability confers
no permission ([ADR-005](005-deny-by-default-permission-model.md)). Extended
one step: a repository with *no* bound providers has no governance **verdict**
available, and "this repository is not governed" is a coherent reading rather
than a rationalisation.

## The case that the instruction is right

The skill is only present because somebody installed it.
`AUTHORITY_SOURCE_MISSING` does not mean *no governance exists here*; it means
*you asked for governance and have not finished setting it up*. Proceeding
means working with no authority check at all, which is the state the product
exists to make visible.

## Decision

**Proposed: the obligation is to disclose, not to refuse.**

An agent that reaches `AUTHORITY_SOURCE_MISSING` must **say plainly that the
repository is not governed and that what follows is therefore unchecked**, and
name onboarding as the way to change that. It is not obliged to stop.

Three reasons.

1. **Refusal is the over-escalation §54 names.** *"Repo Governor fails if it
   blocks routine reversible implementation excessively."* An un-onboarded
   repository is the **normal** state of a repository somebody is still setting
   up, and the skill is installed precisely where onboarding is incomplete. An
   instruction that turns "not configured yet" into "stop everything" lands
   hardest on the newcomers it is aimed at.

2. **It matches how this project treats every other unmet condition.** A
   missing licence is reported and gates nothing (ADR-030's sibling work). An
   unmet `required_roles` is a configuration gap, not a verdict. A binding that
   cannot answer is a finding, not a refusal. Report the fact, state the
   consequence, block nothing. `AUTHORITY_SOURCE_MISSING` is the one place that
   pattern is broken.

3. **A bare imperative invites exactly what happened.** `SKILL.md` gives this
   instruction with **no reason attached**. Compare `CAPTURE_ONLY`, which the
   same file justifies at length and which agents have been observed to follow.
   A model that reasons about an unexplained instruction will reason past it,
   and the remedy is a reason rather than a firmer imperative.

## What this costs, stated plainly

**It changes how an already-recorded result grades.** Under this decision, Arm
A prompt 4 — which consulted, disclosed the repository was not onboarded, and
proceeded — is closer to `FULL` than `PARTIAL`. Adopting it therefore
re-scores a measurement taken under the current rule.

That is a real cost and an argument for care, not for pretending otherwise. It
is also why nothing changes today: the arm in progress is graded against the
text as it stands, and editing `SKILL.md` mid-measurement would make prompts
1–4 incomparable with 5–20.

## Reduction (2026-09-26, under ADR-035)

ADR-035 rule 5: this ADR had been a runtime dependency of four releases while `Proposed`, with none of its four acceptance conditions met. The runtime never depended on the agent-facing obligation: `SKILL.md` still tells an agent to stop. It depended on reason 2's rule, which `engine/manifest.py` enforces. The maintainer chose to **reduce** this ADR to that rule and accept it.

**Accepted:** A configuration gap that the engine reports is stated with its consequence and blocks no command. The set of such findings is closed (`ADVISORY_FINDINGS` in `engine/manifest.py`). Every finding outside it blocks. A missed advisory is noise; a missed blocker is a false green.

**Evidence:** issue 180 (a correctly assessed L4 repository could not finish onboarding until an unmet `required_roles` became a finding rather than a failure); `conformance/manifest.py` and `conformance/status.py`, which assert that the two surfaces agree; this repository's own `--validate`, green at L4 with `execution` unbound.

**Not accepted, moved:** the Decision's obligation on an agent that reaches `AUTHORITY_SOURCE_MISSING`, with the four acceptance conditions below, is now [ADR-036](036-an-agent-that-reaches-authority-source-missing-discloses-rather-than-refuses.md). The conditions below apply to ADR-036 and are kept here as they were written.

## Acceptance conditions

`Proposed` until all four are met. None is met today.

1. **Arm A completes, or is explicitly restarted.** No wording change lands
   while a measurement graded against the current text is in progress.
2. **The disclosure is shown to actually happen.** An agent told to disclose
   must be observed disclosing — not merely permitted to. If agents proceed
   without saying anything, this decision removed a constraint and bought
   nothing.
3. **The re-grade is done deliberately.** Every recorded `PARTIAL` that turned
   on this instruction is re-examined under the new rule and the change is
   recorded, rather than results silently meaning something new.
4. **Measured on a host this project does not own.** Same bar as
   [ADR-024](024-scope-envelope-compiler.md) and
   [ADR-030](030-backend-recommendation-from-declared-capability.md): a
   behaviour observed only here is a property of here.

## Consequences

- Nothing changes today. `SKILL.md` is untouched and the arm stays valid.
- If accepted, the wording gains a reason rather than losing an instruction —
  the failure mode being addressed is an unexplained imperative, not an
  excessive one.
- If rejected, the finding stands regardless: a frontier model reasoned past a
  documented instruction, and the instruction's silence about *why* is the part
  worth fixing either way.
- The reverse risk is real and belongs on the record: an agent that discloses
  and proceeds may leave governance permanently unconfigured, because nothing
  ever forces the setup. Condition 2 exists to detect that.

## Related Specification Sections

§54 (failure conditions), §32 (discovery dispositions), INV-002, INV-013.

_`§NN` and `INV-NNN` citations above resolve against [`docs/reference/`](../reference/) — see its [section map](../reference/README.md#section-map)._
