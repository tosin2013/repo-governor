# Architecture Ratification Review: v0.8.0

**Prepared** 2026-09-26 · **Decisions taken 2026-09-26 by Tosin Akinosho (§68)**. The decision is the [acceptance line at the end](#maintainers-acceptance). Everything above it is evidence, and evidence is not a decision.

## Why this review exists

This is the first release under [ADR-035](035-a-release-may-depend-on-a-proposed-adr-only-on-declared-and-expiring-terms.md), which settled issue 223. The release condition in [RATIFICATION-v0.1.0.md](RATIFICATION-v0.1.0.md) says every decision the runtime depends on is Accepted. ADR-035 amends it: a release may depend on a `Proposed` ADR only if the release records the dependency here, a check verifies the record, and the dependency has lasted no more than two releases.

It also closes a gap. **v0.7.0 shipped with no ratification record.** The v0.6.0 record accepted that release "on the understanding that #223 settles what the condition means before v0.7.0". Issue 223 was still open when v0.7.0 was tagged. [The v0.7.0 section](#v070-recorded-after-the-fact) records that departure now, so it is not inherited by silence.

## Method

ADR-035 rule 1: a release depends on a `Proposed` ADR when code that ships, runs and governs cites it. The scope is `engine/`, the adapters this repository binds, `tools/` (excluding the measurement tools `tools/live-equivalence.py` and `tools/provider-readiness.py`), and `.claude-plugin/`.

```bash
# The derived set, the record rows, the counts and the expiry, as the check sees them
python3 conformance/skill.py | grep -E "ADR-035|RATIFICATION|expiry|Runtime-dependent"
```

The count is computed from the tags by `conformance/skill.py`, and this record must agree with it.

## Decisions for this release

Before this release, five `Proposed` ADRs were cited by code in rule 1's scope. Three were past the two-release expiry. Each was resolved before the tag:

| ADR | Releases while `Proposed` | Decision | What changed |
|---|---|---|---|
| [029](029-hooks-as-deterministic-delivery-surface.md) Hooks as a delivery surface | 11 | **Reduced, then Accepted** | Accepted: the secondary surface, its four constraints, blocking as a backstop, and the verified hosts (Claude Code; Refact in a single agent chat). Not accepted: the cross-vendor claim, which waits on calibration (issues 37, 42, 254). An `## Acceptance conditions` section was added; all four are met. |
| [031](031-authority-source-missing-obliges-disclosure-not-refusal.md) `AUTHORITY_SOURCE_MISSING` | 4 | **Reduced, then Accepted; the rest split** | Accepted: a configuration gap is reported with its consequence and blocks nothing, and `ADVISORY_FINDINGS` is a closed set (evidence: issue 180, `conformance/manifest.py`, `conformance/status.py`). The agent-disclosure obligation moved, unchanged, to [ADR-036](036-an-agent-that-reaches-authority-source-missing-discloses-rather-than-refuses.md), `Proposed`, which no runtime code cites. |
| [033](033-repo-local-providers-answer-about-the-checked-out-revision.md) Repo-local providers and revisions | 3 | **Dependency removed** | Its one runtime citation, a comment in `engine/onboard.py`, was reworded to name the open question. The behaviour was already decided by "no adapter here reads a beads database" and is unchanged. ADR-033 stays `Proposed`; issue 222 is its internal blocker. |
| [030](030-backend-recommendation-from-declared-capability.md) Backend recommendation | 7 | **Not a dependency; comment reworded** | Its only citation, in `tools/onboard-interactive.py`, stated that nothing depended on it. The comment now names the open question without the ADR number. |
| [020](020-agent-supplied-transport-with-adapter-as-normalizer.md) Agent-supplied transport | 11 | **Outside the scope** | Cited only by the measurement tools that rule 1 excludes. They govern nothing. |

ADR-020 and ADR-030 were missing from ADR-035's own measurement. The release runbook's derivation step found them, and ADR-035 carries a dated correction.

## The ledger for v0.8.0

After the decisions above, seven ADRs are `Proposed`: 020, 030, 032, 033, 034, 035, 036. **One is runtime-dependent.**

| ADR | Cited by (rule 1 scope) | Acceptance conditions and their state | Releases while `Proposed` |
|---|---|---|---|
| ADR-034 Publication is per channel | `.claude-plugin/marketplace.json`, `tools/install-skill.sh` | 1 met (compatibility enforced by `conformance/skill.py`). 2 met (the marketplace entry pins the release archive, and the pin is checked against `ENGINE_VERSION`). 3 met for the only entry (Claude Code, `docs/research/calibration/claude.json`). 4 not met: it waits on an adoption event, which is external evidence. | 2 |

**ADR-034 reaches the expiry with this release.** Before v0.9.0 it is decided, reduced or removed (ADR-035 rule 5).

ADR-035 itself is `Proposed` and is not a runtime dependency: only `conformance/` cites it, and conformance is outside rule 1's scope.

## v0.7.0, recorded after the fact

| Fact | State |
|---|---|
| Ratification record | **None was written.** |
| `Proposed` ADRs the runtime depended on (rule 1 scope) | ADR-029, ADR-031, ADR-033, ADR-034 |
| The v0.6.0 condition ("#223 settles … before v0.7.0") | Not met. Issue 223 was settled on 2026-09-26 by ADR-035, after v0.7.0. |
| Other defects in the release | `SKILL.md` shipped at `version: "0.6.0"`, and `docs/releases/v0.7.0.md` did not exist, so the release page fell back to generated notes. Both are now guarded (issue 256; the release runbook, issue 257). |

This was the third consecutive release that depended on unratified decisions, and the first with no record at all. ADR-035 and its check exist so that a fourth cannot happen silently.

## What ratification requires of the release, not only of the ADRs

- `conformance/skill.py` passes. It checks that this record exists for `ENGINE_VERSION`, that ADR-034 appears with the count the tags give, and that the count is within the expiry.
- Every version site says 0.8.0, and `python3 tools/check-version.py v0.8.0` passes.
- `docs/releases/v0.8.0.md` exists before the tag.
- The tag is created by the maintainer, following [docs/runbooks/release.md](../runbooks/release.md).

## What is left to the maintainer

- **ADR-034** before v0.9.0: decide, reduce or remove. Condition 4 cannot be met by this project, so a reduction that records it as external is the likely path.
- **ADR-036**: its condition 1 (issue 36, Arm A) is an internal blocker. ADR-035 rule 2 does not permit a runtime dependency on an ADR whose blocker is internal, so `SKILL.md` stays unchanged until Arm A completes or is restarted.
- **ADR-033**: issue 222 (`get_provenance` has no engine consumer) is internal work to settle before it can be accepted.
- **ADR-035**: its own acceptance conditions 3 and 4 are met only after this release ships under it without a bypass.

## Maintainer's acceptance

**Decided 2026-09-26 by Tosin Akinosho.** ADR-029: reduce, then accept the reduced scope. ADR-031: reduce to the engine's configuration-gap rule, accept it, and split the disclosure obligation into a new `Proposed` ADR. ADR-033: remove the runtime citation. ADR-020 and ADR-030: tighten ADR-035 rule 1 and correct its facts. ADR-034: ship its second release, recorded above.

*Recorded by the agent at the maintainer's explicit instruction in session, not authored by it. §68 makes the judgement human; the transcription is not the act. The act is the maintainer's merge of this record and the tag that follows it.*
