# ADR-035: A release may depend on a Proposed ADR only on declared and expiring terms

**Status**: Proposed

**Date**: 2026-09-26

**Resolves**: [issue 223](https://github.com/tosin2013/repo-governor/issues/223), `RATIFICATION-v0.5.0.md` finding F3

**Amends**: the release condition in [RATIFICATION-v0.1.0.md](RATIFICATION-v0.1.0.md). This ADR does not ratify, reject or reword ADR-029, ADR-031, ADR-033 or ADR-034. It decides what a release must do while it depends on them.

## Context

`RATIFICATION-v0.1.0.md` states the release condition:

> **Every architecture decision the runtime depends on is Accepted**, and no Proposed ADR is silently treated as normative by that release.

The condition held at v0.1.0 because no held ADR was referenced by the runtime. Every release since v0.2.0 has broken it:

| Release | Proposed ADRs the runtime depended on | What was recorded |
|---|---|---|
| v0.2.0 to v0.4.0 (seven releases) | ADR-029 (the hook script and templates) | Nothing. No check looked in `tools/`. |
| v0.4.1 | ADR-029, ADR-031 | Nothing |
| v0.5.0 | ADR-029, ADR-031, ADR-033 | A departure, in `RATIFICATION-v0.5.0.md` (F3) |
| v0.6.0 | ADR-029, ADR-031, ADR-033 | A departure, "on the understanding that #223 settles what the condition means before v0.7.0" |
| v0.7.0 | ADR-029, ADR-031, ADR-033, ADR-034 | **Nothing.** No ratification record exists. |

Measured on 2026-09-26 by searching each tag's `engine/`, `adapters/`, `tools/` and `.claude-plugin/` for `ADR-0NN`. The index and `conformance/skill.py` name only ADR-031 and ADR-033, because the check reads `engine/*.py` and bound adapters. The hook surface (ADR-029) and the plugin channel (ADR-034) ship from `tools/` and `.claude-plugin/`, which the check never reads.

`RATIFICATION-v0.5.0.md` predicted this: *"A departure recorded once is an exception; recorded every release, it is the condition being repealed by habit."* v0.7.0 went one step further and did not record it at all.

Issue 223 set out three readings:

1. **Remove the dependency.** Gate or strip runtime behaviour until each ADR is Accepted. For ADR-029 alone, this removes the only surface in this project that can stop a write.
2. **Record a departure each release.** This is the habit the v0.5.0 review warned about, and v0.7.0 shows that the record gets skipped.
3. **Amend the condition.** The review warned: *"A condition amended the first time it binds is a condition that never binds."*

The warning in reading 3 is about using an amendment to escape. The condition has bound in every release since v0.2.0 and has been broken each time, mostly without a record. Amending it now does not escape a first binding. It replaces an unenforced rule with one that a check can enforce.

## Decision

**A release may depend on a Proposed ADR only on terms that the ADR declares, that the release records, that a check verifies, and that expire.**

1. **What counts as a dependency.** A release depends on a Proposed ADR when anything it ships and runs cites the ADR: `engine/`, an adapter this repository binds, `tools/` (the hook script, the hook templates, the installer), or a publication channel file (`.claude-plugin/`). The scope follows what ships, not where the engine lives.

2. **The blocker is declared.** A Proposed ADR that a release depends on names, in its `## Acceptance conditions`, what evidence it waits for. It also says whether that evidence is external: produced on repositories, hosts or users this project does not control. A dependency on an ADR whose blocker is internal work is not permitted. Do the work, or remove the dependency.

3. **The release records it.** A release that depends on a Proposed ADR has a ratification record, `docs/adrs/RATIFICATION-vX.Y.Z.md`, written before the tag. For each such ADR, the record lists every acceptance condition and its state (met, not met, or cannot be met by this project), and the number of releases that have depended on it while Proposed, this one included.

4. **A check enforces the record.** `conformance/skill.py` derives the dependency set with the scope in rule 1. It fails when the ratification record for the version in `engine/version.py` is missing, or omits a dependent ADR, or gives a count that disagrees with the tags. The index line "Runtime-dependent and still `Proposed`" is derived with the same scope.

5. **The dependency expires after two releases.** A Proposed ADR may be depended on by at most two releases. Before a third release can depend on it, the maintainer does one of three things:
   - **decides it**: Accepted, or superseded by an ADR that can be;
   - **reduces it**: amends it to the part its evidence already supports, and accepts that part;
   - **removes it**: takes the dependency out of the runtime.

   Counting uses rule 1's scope from the first release that shipped the dependency. The count includes releases made before this ADR. No transition period applies.

6. **Recording is not ratifying.** A record under rule 3 states facts about a dependency. It does not make the ADR normative (§68). Acceptance stays a human act.

## Consequences

**Positive**

- A dependency on an unratified decision becomes visible, counted and bounded. A skipped record, like v0.7.0's, fails a check instead of passing silence.
- The scope gap closes. ADR-029 and ADR-034 enter the list that ADR-031 and ADR-033 are already on.
- The expiry turns "awaiting external evidence" from a permanent state into a decision with a date.

**Negative**

- **v0.8.0 cannot ship until ADR-029, ADR-031 and ADR-033 are each decided, reduced or removed.** By rule 5's count they have been depended on by eleven, four and three releases. This is the direct result of choosing an expiry of two releases with no transition, and this ADR states it rather than hiding it. ADR-034 has one release and may ship once more.
- "Reduce" needs judgement: which part of an ADR its evidence supports. A check cannot make that call.
- The ratification record becomes part of every release that has a dependency, which adds work to each release.

**Neutral**

- A release with no Proposed dependency needs no record under this ADR. The original condition then holds as written.
- Rule 1's scope can grow. A new shipped surface that cites ADRs joins the scope in the same change that adds it.

## Confirmation

| Obligation | Kind | How anyone would know |
|---|---|---|
| Rule 1: the dependency scope | structural | `conformance/skill.py` derives the set from `engine/`, bound adapters, `tools/` and `.claude-plugin/`. **Not yet mechanical.** Today it reads `engine/` and bound adapters only. |
| Rule 2: the blocker is declared | structural (presence), substantive (truth) | A check can confirm an `## Acceptance conditions` section exists. Whether the evidence is really external is a human judgement at review. |
| Rule 3: the release records it | structural | the check in rule 4 |
| Rule 4: the check | structural | `conformance/skill.py`, mutation-tested: delete a dependent ADR from a record, and the suite fails. **Not yet written.** |
| Rule 5: the expiry | structural (count), substantive (the decision) | The check computes the count from tags. Deciding, reducing or removing is a human act. |
| Rule 6: recording is not ratifying | substantive | No mechanical confirmation. Review discipline. |

## Acceptance conditions

`Proposed` until all four are met. **None is met today.**

1. **The check exists and bites.** `conformance/skill.py` implements rules 1, 3, 4 and 5, and fails by mutation on each of these: a missing record, an omitted ADR, a wrong count, and a scope that excludes `tools/`. *(Not met.)*
2. **The index agrees.** The index line derives the dependency set with rule 1's scope and names ADR-029 and ADR-034 alongside ADR-031 and ADR-033. *(Not met.)*
3. **One release has passed under it.** v0.8.0, or the first release after this ADR is merged, ships with a record that the check accepts, and with each expired ADR decided, reduced or removed. *(Not met.)*
4. **The expiry was applied and not bypassed.** Nothing amends rule 5 to let an expired ADR ship one more release. If rule 5 proves wrong, a superseding ADR says why. Quiet non-application does not count. *(Not met, and cannot be met before condition 3.)*

## Related Specification Sections

- §68 (acceptance is a human act)
- [RATIFICATION-v0.1.0.md](RATIFICATION-v0.1.0.md) (the condition), [RATIFICATION-v0.5.0.md](RATIFICATION-v0.5.0.md) (F3), [RATIFICATION-v0.6.0.md](RATIFICATION-v0.6.0.md)
- [ADR-029](029-hooks-as-deterministic-delivery-surface.md), [ADR-031](031-authority-source-missing-obliges-disclosure-not-refusal.md), [ADR-033](033-repo-local-providers-answer-about-the-checked-out-revision.md), [ADR-034](034-publication-is-per-channel-and-a-listing-claims-only-what-is-calibrated.md): the current dependencies
- [ADR-032](032-a-decision-declares-how-it-will-be-confirmed.md): the confirmation and acceptance sections this ADR carries
