# ADR-034 — Publication is per-channel, and a listing claims only what is calibrated

**Status**: Proposed

**Date**: 2026-09-09

**Extends**: [ADR-001](001-agent-skill-as-primary-delivery-surface.md) — which says *what* ships; this says *where it is published and what a listing is allowed to claim*

## Context

v0.6.0 shipped on 2026-09-04. The question that followed was whether the skill is
ready to publish in more than one place, and the honest answer split in two:
conformance to the format is settled, and entitlement to claim broad support is not.

**Measured 2026-09-09, not asserted.** The reference validator that the standard
publishes passes:

```
$ skills-ref validate ./repo-governor
Valid skill: repo-governor
```

`SKILL.md` is 191 lines against a recommended ceiling of 500, and roughly 2,957 body
tokens against a recommended 5,000. `name` is valid and matches the directory. The
description is 325 characters of an allowed 1,024.

**The channel landscape has three shapes, and they behave differently.** Several large
directories index public GitHub *automatically*, without being asked. A smaller number
curate by submission. At least one vendor channel — the Claude Code plugin marketplace —
cannot accept a bare skill directory at all: the unit of distribution there is a plugin,
so a skill must either be wrapped in one or referenced by a marketplace entry.

**Against that stands this project's own record.** `references/harnesses.md` states the
rule and the cautionary version in the same breath: *"Headless is not known to be the
same instrument as interactive until somebody shows it is, on that host"*, and *"five
hook templates shipped and exactly one was ever verified, and the Codex one was wrong
because it was written from a documentation summary rather than a run."*

Five hook templates ship. One calibration record exists. ADR-029 says so plainly:
*"Only the Claude Code payload schema is verified… The Codex template is a best guess —
no Codex host has ever been available to this project."*

And until this ADR, `SKILL.md` declared **no** `compatibility` while
`docs/installation.md` said that without `python3` 3.11+ and `git`, *"nothing works"*.

Publishing multiplies a claim surface. A governance tool that fails silently on a host
does not read as a missing feature; it reads as a repository that is governed when it is
not.

## Decision

**Publication is a per-channel act, and no channel entry may claim more than the project
has measured.**

1. **The published artifact is the skill directory, unchanged.** A vendor channel may add
   a manifest that *points at* the tree. It may not move `SKILL.md`, rename directories to
   suit a host, or introduce a second copy of the skill. Reshaping the repository for one
   vendor is the bet ADR-001 refuses, and a parallel copy is §54's oldest failure
   condition — two sources of record — arriving through the distribution door.

   The precedent is already in this repository: `CLAUDE.md` is a one-line pointer to
   `AGENTS.md` precisely so the content stays vendor-neutral. A vendor manifest is the same
   move and is bounded the same way.

2. **Every channel entry pins a released tag.** A source with no version resolves to
   whatever the branch holds at that moment, so every push becomes a release nobody cut.
   An unpinned entry is not publishing a release; it is publishing `HEAD`.

3. **`compatibility` is declared, and derived from the dependency table rather than from
   aspiration.** Discovery under this standard carries only `name`, `description` and
   metadata, so a host lacking the runtime does not find out until after activation —
   where it reads as the skill declining rather than as a missing binary. What the skill
   requires belongs in frontmatter, and it must agree with `docs/installation.md`.

4. **A channel entry names a host only where a calibration record exists.** This is
   `references/harnesses.md`'s rule applied to distribution. Appearing in a directory is
   discovery, and **discovery confers no authority** (INV-001). A listing that implies
   support for hosts nobody has run is the five-hook-templates defect at distribution
   scale.

5. **Automatic aggregators are observed, not consented to.** Several of the largest
   directories index public repositories without asking. The project cannot prevent that
   and must not mistake it for publication: a scraped listing can carry a stale copy and
   make a claim nobody made. What this project controls is the tag a curated entry points
   at, and the compatibility it declares — not who indexes it.

## Consequences

**Positive**

- The vendor-neutral tree stays the single source of the skill; channels become pointers
  rather than forks.
- A host missing `python3` or `git` learns why from frontmatter instead of from a
  confusing activation failure.
- The number of hosts claimed is bounded by the number calibrated, which is a number this
  project already tracks and can raise deliberately.
- Rule 2 makes "what version is installed" answerable for curated channels, which is
  [issue 197](https://github.com/tosin2013/repo-governor/issues/197)'s problem appearing in
  a place the installer does not reach.

**Negative**

- **Reach is deliberately traded for honesty.** Rule 4 keeps this out of channels that
  want a long host list, and the honest list is currently short.
- **Rule 5 admits an uncontrolled surface.** Scraped listings will exist, may be stale,
  and this ADR does not fix them — it only refuses to count them as publication.
- **A vendor manifest is still a vendor artifact.** Rule 1 bounds it rather than
  forbidding it, and a reader may reasonably ask why a tool-independent project carries
  one at all. The answer is the `CLAUDE.md` answer, and it is a judgement rather than a
  proof.
- Rule 2 adds a release step: a channel entry must be updated when a tag is cut, or it
  pins a version that ages.

## Confirmation

| obligation | kind | how anyone would know |
|---|---|---|
| Decision 3 — `compatibility` is declared and agrees with the dependency table | structural | `conformance/skill.py` asserts `SKILL.md` carries `compatibility` and that it names every tool `docs/installation.md` marks as *nothing works* without. **Written and run in the change that introduced this ADR** |
| Decision 1 — no second copy of the skill | structural | the same suite: exactly one `SKILL.md` is tracked at the repository root, and no vendor manifest directory contains another |
| Decision 2 — channel entries pin a tag | structural | **not yet mechanical.** No channel manifest exists in this repository today; when one lands, the assertion is that its source carries a `ref` or `version` matching a released tag |
| Decision 4 — hosts claimed are hosts calibrated | **substantive** | a check can compare a manifest's host list against `docs/research/calibration/`. It cannot see a claim made in a directory's web form, which is where most of this risk lives. Human discipline at submission time |
| Decision 5 — aggregators are observed | **substantive** | no mechanical confirmation. A periodic look at what is indexed, and nothing else |

Two of the five clauses cannot be confirmed by anything but a person, and this table says
which two rather than implying the whole is enforced.

## Acceptance conditions

`Proposed` until all four are met. **One is met today.**

1. **The compatibility declaration is enforced, not merely written.** `conformance/skill.py`
   asserts that `SKILL.md` declares `compatibility` and that it names the tools the
   installation guide calls load-bearing, so the two cannot drift. *(Met — added and proved
   by mutation in the change that introduced this ADR.)*

2. **A channel entry exists and is pinned.** At least one curated channel carries an entry
   for this skill, pinned to a released tag, and updating that pin is part of cutting a
   release. Until then rules 2 and 4 are a convention with nothing under them. *(Not met.)*

3. **A host claimed in a listing has been run.** Whatever host list a published entry
   carries is backed by a calibration record under `docs/research/calibration/`. There is
   one such record today, for one host, so any listing claiming more is currently
   unearned. *(Not met.)*

4. **The trade in rule 4 survives contact with wanting reach.** If the short honest host
   list proves to cost adoption badly enough that someone wants to widen it, this ADR is
   the thing to argue with — and widening it by calibrating hosts is the intended path,
   while widening it by claiming uncalibrated ones means this decision was wrong and should
   be superseded rather than quietly ignored. *(Not met, and not met until it is tested.)*

## Related Specification Sections

- **§54** — failure conditions; a second source of record, and vendor lock
- **INV-001** — discovery confers no authority
- **ADR-001** — agent skill as the primary delivery surface
- **ADR-029** — hooks, and the record of which templates are verified
- **ADR-032** — a decision declares how it will be confirmed
