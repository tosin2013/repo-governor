# ADR-037 — A Spec Kit extension delivers governance at Spec Kit's steps; the engine still decides

**Status**: Proposed

**Date**: 2026-10-03

**Resolves**: [issue 264](https://github.com/tosin2013/repo-governor/issues/264)

**Extends**: [ADR-029](029-hooks-as-deterministic-delivery-surface.md) (a second delivery surface of the same kind) and [ADR-034](034-publication-is-per-channel-and-a-listing-claims-only-what-is-calibrated.md) (a new channel under its rules)

## Context

Repo Governor already *reads* Spec Kit. `adapters/speckit` answers the architecture role from `.specify/memory/constitution.md` and `specs/<feature>/`, and `engine/onboard.py` detects a Spec Kit workspace by `.specify/`. Nothing yet runs governance *inside* Spec Kit's workflow.

That leaves a Spec Kit user with a gap the tool exists to close. An agent that has run `/speckit.specify`, `/speckit.plan` and `/speckit.tasks` holds a spec, a plan and a task list. Each of those is evidence, and none is permission. Nothing in Spec Kit asks whether the work is admitted, or whether it is already done. The message this project wants to stand behind is **Spec Kit decides how to build; Repo Governor decides whether the agent may build it now, and when it has to stop.** Today that is a claim with nothing running under it.

Spec Kit has an extension system (`extensions/EXTENSION-API-REFERENCE.md` in `github/spec-kit`, read 2026-10-03):

- **Manifest.** An extension is an `extension.yml` with `schema_version: "1.0"`.
- **Commands.** Commands are markdown files named `speckit.<id>.<command>`.
- **Hooks.** A hook binds a command to `before_` or `after_` one of Spec Kit's steps: `specify`, `plan`, `tasks`, `implement`, `analyze`, `checklist`, `clarify`, `constitution` and `taskstoissues`.
- **Optional vs required.** A hook is `optional: true` by default, which means the agent shows a prompt. `optional: false` makes the agent emit `EXECUTE_COMMAND: <command>`, run it, and wait for the result before proceeding.

### What was measured, and the fact that shapes everything else

**Spec Kit hooks cannot block a step.** The core command templates are prompts, and their hook handling is an instruction to the agent:

- they read `.specify/extensions.yml`;
- they skip disabled hooks;
- they skip any hook with a non-empty `condition`;
- for `optional: false`, they run the command and wait.

There is no exit code and no structured result. A step stops only because the hook command's own text tells the agent to stop. The governance-shaped extensions already in the community catalog work exactly this way. `plan-review-gate` prints `BLOCKED:` and instructs the agent not to proceed. `spec-validate` and `arch-governance` gate `before_implement` the same way.

That puts this surface in the same class as ADR-029's `prompt` moment. It reliably makes a requirement *arrive*, and it enforces nothing on its own. An ADR that called the extension a gate without saying so would be describing a guarantee nobody can supply.

## Decision

**A Spec Kit extension is a delivery surface. It runs the engine at Spec Kit's steps and relays the engine's decision. It never decides, never infers which work it is governing, and does not claim enforcement Spec Kit cannot provide.**

1. **Hook commands deliver and never decide.** Each command runs `engine/completion.py` or `engine/envelope.py` and acts on the returned `decision` per the decision table in `AGENTS.md` and `SKILL.md`. A command file carries no governance logic of its own: no disposition is computed, restated or softened in it. This is ADR-029 constraint 1 on a second surface (ADR-002).

   The engine-calling and result-reading code is shared with `tools/hooks/governance-hook.py` rather than written again. Two interpreters of one JSON verdict are two sources of record for what a verdict means.

2. **The hook set is fixed by what each step can know.**

   | Spec Kit event | Command | `optional` | What it delivers |
   |---|---|---|---|
   | `before_implement` | `speckit.repo-governor.check` | `optional: false` | Runs `completion.py` for the mapped issue. Anything other than `CONTINUE` means stop and report, per the decision table. |
   | `after_implement` | `speckit.repo-governor.check` | `optional: false` | Re-checks for `STOP_COMPLETE`, so an agent that has finished does not continue into "improvements" (INV-009). |
   | `after_taskstoissues` | `speckit.repo-governor.status` | `optional: false` | States that the issues just filed are **not admitted**. Admission is milestone membership (ADR-018) and a human act. |
   | `before_specify`, `before_plan` | `speckit.repo-governor.status` | `optional: true` | Report only. Specifying and planning are not execution, so nothing there is stopped. |

   Discoveries made during implementation go through `speckit.repo-governor.discovery`, which wraps `envelope.py --discovery` (INV-001). No hook binds it, because a discovery has no fixed step.

3. **A Spec Kit feature maps to an issue by declaration, never by inference.**
   - **Where the mapping lives.** The link from `specs/<feature>/` to a work item is a committed file, `.repo-governor/speckit-features.json` (for example `{"001-add-auth": "142"}`), written by a human.
   - **What is never consulted.** The extension never derives an issue from a branch name, a directory name, spec text or a task list. That would be an authority id inferred from content, which ADR-029 constraint 1 and ADR-022 forbid, and an identity defaulted when it cannot be told, which ADR-028 forbids.
   - **An unmapped feature** answers `UNKNOWN` with a typed reason.
   - **No mapping file, or no manifest,** is a configuration gap. It is disclosed, per ADR-031's engine rule and ADR-036's proposal, not silently passed.
   - **Where the reader goes** is left to issue 266, between `adapters/speckit` (a new declared function) and `engine/`. Either way it is validated by `engine/manifest.py --validate`.

4. **`tasks.md` checkboxes are execution state, not completion.** A fully ticked `tasks.md` does not produce `STOP_COMPLETE`. A partly ticked one does not withhold it. Completion comes from `.repo-governor/acceptance/<id>.json` checked against repository evidence (ADR-017). This restates INV-002 for the surface where the confusion is most likely, because Spec Kit presents tasks as the shape of done.

5. **Enforcement is by instruction only, and every surface that describes the extension says so.** Spec Kit hooks cannot block a step. `optional: false` makes the check run and the result arrive. Whether the agent then stops depends on the agent following the command text.
   - **Documentation.** The extension's documentation states this and points to the ADR-029 host hooks (`write` moment, `repo_governor.enforcement: "blocking"`) for repositories that need a mechanical stop.
   - **Catalog entry.** The entry does not use the word "gate" without the qualification.

6. **The Spec Kit community catalog is a channel under ADR-034, on ADR-034's terms.**
   - **One artifact (rule 1).** `extension.yml` and `commands/` live in this repository and point at the skill directory as it is. The catalog's `download_url` is the same tagged release archive every other channel pins. The skill installer prunes them, as it prunes `.claude-plugin/`, so a skill install never carries Spec Kit files.
   - **Pinned (rule 2).** `extension.yml`'s `version` equals `ENGINE_VERSION`, and the entry pins the matching tag.
   - **Calibrated hosts only (rule 4).** The entry names only agents with a calibration record under `docs/research/calibration/`.
   - **Submission.** Submission is Spec Kit's `extension_submission.yml` issue, not a change to their catalog file, and the resulting listing is observed rather than assumed (rule 5).
   - **No self-hosted catalog.** A self-hosted catalog for `.specify/extension-catalogs.yml` would be a further channel and is not decided here.

**The runtime depends on this ADR from issue 266.** `engine/features.py` and `engine/manifest.py --validate` implement decision 3, so under ADR-035 rule 1 a release that ships them depends on ADR-037 while it is `Proposed`. That dependency is recorded in the ratification record of the first release that carries it, v0.9.0, and not earlier: `RATIFICATION-v0.8.0.md` describes a release that never depended on it.

## Consequences

**Positive**

- The message stops being a claim. A Spec Kit user installs one extension and gets the authorization check at the one step where authority matters, and the completion check right after it.
- No new vocabulary, provider role or engine decision. The extension calls the engine that exists, and every decision it relays is one the engine already produces.
- The mapping file makes the link between a spec and a work item reviewable in a pull request, where it can be wrong in public instead of being guessed in private.

**Negative**

- **The guarantee is weaker than the word "hook" suggests.** An agent that ignores the command text proceeds, and nothing in Spec Kit notices. This is the same ceiling ADR-029 found for the `prompt` moment, now on a surface whose users may reasonably expect more. The documentation can name the ceiling; it cannot lift it.
- **A second surface to keep in step.** Spec Kit's hook semantics are defined by its prompt templates, not a versioned contract. A change upstream can alter what `optional: false` does without changing any file here. `requires.speckit_version` bounds this from below only.
- **One more file a human must keep current.** A feature with no mapping is `UNKNOWN`. That is correct, and in a repository that adopts Spec Kit quickly it will be the most common answer until the mapping catches up.
- **Release coupling.** This ADR adds a channel to ADR-034, which itself must be decided, reduced or removed before v0.9.0 (`RATIFICATION-v0.8.0.md`). If ADR-034 is removed, decision 6 loses its footing and must be rewritten before any listing.

## Confirmation

| obligation | kind | how anyone would know |
|---|---|---|
| Decision 1: hook commands carry no governance logic | structural | `conformance/skill.py` checks that every `optional: false` hook names a command that calls `engine/` and restates no disposition (issue 267) |
| Decision 1: one interpreter of the verdict | structural | The command files invoke the shared code in `tools/hooks/`, checked by the same suite (issues 265, 267) |
| Decision 2: the hook set | structural | `extension.yml` is parsed by `conformance/skill.py`, and the required events are asserted by name (issue 267) |
| Decision 3: declared mapping, never inferred | structural | `engine/manifest.py --validate` validates the file, and a fixture with an unmapped feature must yield `UNKNOWN` (issue 266) |
| Decision 3: an agent does not guess the issue | substantive | Observed in the calibration run with an unmapped feature (issue 268). No mechanical confirmation. |
| Decision 4: `tasks.md` is not completion | structural | A fixture with every task ticked and no satisfied acceptance criteria does not yield `STOP_COMPLETE` (issue 266) |
| Decision 5: enforcement is stated as instruction-only | procedural | The runbook and catalog entry say so, or they do not (issues 269, 270) |
| Decision 5: agents actually stop on the instruction | substantive | Observed in the calibration run with an unadmitted issue (issue 268) |
| Decision 6: one artifact, pinned | structural | `conformance/skill.py` asserts `version` equals `ENGINE_VERSION`, and that `tools/install-skill.sh` prunes `extension.yml` and `commands/` (issue 267) |
| Decision 6: only calibrated agents listed | substantive | Human discipline at submission, as ADR-034 rule 4 (issue 270) |

## Acceptance conditions

`Proposed` until all four are met. **None is met today.**

1. **The extension exists and its structural confirmations run.** Issues 265, 266 and 267 have landed, and `./tools/run-conformance.sh --hermetic` asserts every structural row above. *(Not met.)*
2. **Calibrated on one agent, with all three outcomes observed.** An admitted feature proceeds; an unadmitted one stops; an unmapped one is disclosed as `UNKNOWN` without a guessed issue. Recorded under `docs/research/calibration/` (issue 268). *(Not met.)*
3. **ADR-034 is decided.** Decision 6 rests on it. If ADR-034 is accepted, reduced or replaced, this decision is re-read against the result before acceptance. *(Not met. Due before v0.9.0.)*
4. **Used on a Spec Kit repository this project does not own.** *(Not met. External evidence.)*

## Related Specification Sections

§37 (no manufactured authority), §40 (completion firewall), §54 (failure conditions: two sources of record, vendor bets), INV-001, INV-002, INV-009, ADR-002, ADR-017, ADR-018, ADR-022, ADR-028, ADR-029, ADR-031, ADR-033, ADR-034, ADR-035, ADR-036.
