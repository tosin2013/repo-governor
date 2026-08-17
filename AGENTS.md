# Working in this repository

**This repository is governed by Repo Governor, which is also what it builds.** Governance applies to you while you work here.

The rule everything rests on:

> **Information may justify a decision. Information does not acquire authority merely by existing.**

A TODO, an open issue, a `READY` task, a green build — each is *evidence*. None is permission.

## Before acting on anything

The skill lives at [`SKILL.md`](SKILL.md) in this repository, so the engine is right here:

```bash
python3 engine/manifest.py                 # is this repository governed?  -> MANIFEST VALID
python3 engine/completion.py <issue-number>  # may I work on it, and is it done?
```

Work items are **GitHub issue numbers** — the roadmap of record is GitHub Issues, not any file in this repository (ADR-022). Admission is **milestone membership** (ADR-018): an issue with no milestone reads `NOT_ADMITTED` and is not authorized work, however reasonable it looks.

| Decision | What you do |
|---|---|
| `CONTINUE` | Authorized and unfinished. Proceed within scope. |
| `STOP_COMPLETE` | Acceptance conditions satisfied. **Stop.** |
| `NO_EXECUTION_AUTHORITY` | Admitted, not cleared to execute. Do not start. |
| `AUTHORITY_WITHDRAWN` | Cancelled. Stop. |
| `UNKNOWN` | Read `unknowns[]`. Any `blocking: true` means stop and report. |

## Two things the engine cannot enforce, so they are on you

**Discovery confers no authority (INV-001).** Anything you notice that is not the authorized work is a discovery: record it, do not act on it. The discovery path is specified ([ADR-024](docs/adrs/024-scope-envelope-compiler.md), held `Proposed`) and **not implemented** — no engine module emits `CAPTURE_ONLY`. A clean `completion.py` run is not clearance to act on something you found along the way.

**Admission is a human act.** Filing an issue is not admitting it. Putting it in a milestone is. Do not milestone your own findings to unblock yourself.

## Before deleting anything

```bash
python3 engine/retirement.py <path>
```

`REMOVAL_READY` requires every obligation dimension resolved and clear. Static analysis alone can never reach it, so a `RETIREMENT_REVIEW` on an asset with zero references is the correct result, not a false positive.

## House rules that have cost us

- **Never put a closing verb next to a `#` reference in a commit message**, even quoted. GitHub parses it anyway. This closed the same issue twice, the second time in the commit documenting the trap.
- **Adapters resolve paths relative to the working directory**, never relative to their own location. The engine pinning `cwd` to its own install directory made every repo-local provider read this repository whatever it was pointed at ([ADR-027](docs/adrs/027-the-governed-repository-is-not-the-install-directory.md)).
- **Provider identity is never defaulted** ([ADR-028](docs/adrs/028-provider-identity-is-never-defaulted.md)). An adapter that cannot tell which system it is reading must fail, not guess.
- **Fixtures live under `conformance/`, never under `.repo-governor/`**, and fixture ids name the state they demonstrate, never a real work item. Binding a fixture as a provider of record is how this project reproduced §54's oldest failure condition inside itself ([ADR-022](docs/adrs/022-repo-governor-does-not-own-roadmap-state.md)).

## What to actually ask

[`docs/workflows/`](docs/workflows/README.md) carries prompt recipes per situation — starting work, discoveries, dependency updates, bugs, architecture changes, retirement, finishing, roadmap maintenance. Shapes to adapt, each with an explicit "do not" clause.

## Before you commit

```bash
for s in layer1 layer2 transport manifest onboarding vocabulary bindings skill; do python3 conformance/$s.py; done
python3 engine/manifest.py --validate
```

All suites pass on `main`. A suite that fails is a defect in your change, not a flaky test — none of them touch the network except by explicit fixture.

## Decisions

`docs/adrs/` is the decision ledger. **A `Proposed` ADR is not architecture you may rely on** — the ratification review ([`RATIFICATION-v0.1.0.md`](docs/adrs/RATIFICATION-v0.1.0.md)) records what is Accepted, what is held, and why. No count is repeated here on purpose: this file once said "21 of 26" after the ledger said 23, and a duplicated derivable fact eventually disagrees with its source. Read the ledger. Changing an ADR's status means re-reading `SKILL.md` and `references/` for instructions that now contradict it.
