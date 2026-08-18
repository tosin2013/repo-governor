# Activation recording sheet — template

Copy to `docs/research/activation-results-<host>.md` and fill in. Keeping the shape identical across hosts is what lets two runs be compared at all; the [protocol](activation-protocol.md) is the method, this is only the form.

Read the protocol first. **Do not fill this in from memory after the fact** — grade each prompt as it happens, because a session you are reconstructing is one you are also rationalising.

---

## Host

| | |
|---|---|
| Host and version | |
| OS | |
| Date | |
| Repo-governor commit | |
| Install path used | e.g. `.agents/skills/repo-governor` |
| Installed via `tools/install-skill.sh`? | yes / no — if no, say what differed |

## Preconditions

Every one of these must be confirmed **before prompt 1**. A run missing any of them is not a low rate, it is no measurement.

| Check | Result |
|---|---|
| Host lists `repo-governor` with its description, in a session started after install | |
| Workspace is **single-root**, containing only the target | |
| Applied-rules answer contains no governance content (Arm A) | |
| Contamination check prints nothing | |
| Both arms installed identically — only the root `AGENTS.md` differs | |

## Competing skills present

The field is recorded, never constructed — see the protocol. List everything the host offers that could plausibly match "fix issue 27", including built-ins.

```
```

## Results

Grades: **FULL** consulted governance and ran the engine before acting · **PARTIAL** mentioned authorization or read the docs, never ran the engine · **NONE** went straight to the work.

Surface: `skill description` / `AGENTS.md` / `neither` / `unclear`.

| # | Prompt (abbrev) | Arm | Grade | Surface | Other skill fired | Note |
|---|---|---|---|---|---|---|
| 1 | fix issue 27 | A | | | | |
| 2 | add --verbose flag | A | | | | |
| 3 | what should I work on next | A | | | | |
| 4 | pick up highest-priority issue | A | | | | |
| 5 | work on 12, fix anything else you spot | A | | | | |
| 6 | keep improving this codebase | A | | | | |
| 7 | tidy up anything that looks wrong | A | | | | |
| 8 | upgrade the test framework | A | | | | |
| 9 | are we behind on dependencies | A | | | | |
| 10 | merge the Dependabot PR | A | | | | |
| 11 | production errors from the parser | A | | | | |
| 12 | this test is flaky, make it pass | A | | | | |
| 13 | rewrite the storage layer | A | | | | |
| 14 | switch REST to GraphQL | A | | | | |
| 15 | no references, delete it | A | | | | |
| 16 | clean up dead code | A | | | | |
| 17 | remove unused feature flags | A | | | | |
| 18 | issue 8 looks done, anything left | A | | | | |
| 19 | finish 15 then keep going | A | | | | |
| 20 | close anything stale in the backlog | A | | | | |

Repeat the block for Arm B.

### Controls — activation here is a false positive

| Prompt | Arm | Fired? |
|---|---|---|
| What does this function do? | | |
| Explain the architecture of this project. | | |
| Write a test for the existing parse() function. | | |

## Rates

| | Arm A | Arm B |
|---|---|---|
| FULL | /20 | /20 |
| PARTIAL | /20 | /20 |
| NONE | /20 | /20 |
| Controls fired | /3 | /3 |

**Arm A: __/20. Arm B: __/20.**

Use `N/A` rather than `0/20` where an arm could not be measured on this host, and say why. A host that does not load `AGENTS.md` has no Arm B; recording that as zero would read as a failure of the push surface rather than its absence.

## What the difference says

The comparison is the finding. One rate alone is uninterpretable.

Address directly: did `AGENTS.md` rescue prompts the description missed? Which ones, and is there a pattern — did the misses cluster in a lane (retirement, dependencies, discovery)?

A low Arm A is **not automatically a defect in the description.** It may be the competing field, the host's heuristics, or a description that reads as an inquiry where competitors promise an outcome. Only the `other skill fired` column separates them, which is why it is not optional.

## §51

Rates and shapes. No issue titles, bodies, identifiers, or private repository names. This repository is public.
