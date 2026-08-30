# Live cross-provider equivalence, including withdrawal

**Issue:** [41](https://github.com/tosin2013/repo-governor/issues/41) · **Answers the last gap in:** [1](https://github.com/tosin2013/repo-governor/issues/1)
**Status: COMPLETE. 5 of 5 EQUIVALENT across two live providers, 0 divergences.**

## Result

```
live scenarios: 5   agree: 5   diverge: 0   wrong: 0   skipped: 0   errors: 0

LIVE EQUIVALENCE: EQUIVALENT across 5 of 5 scenarios
```

| semantic state | Linear `statusType` | GitHub | both normalized to | |
|---|---|---|---|---|
| admitted, not cleared to execute | `backlog` | milestoned, unassigned | `ADMITTED`, admitted true | AGREE + CORRECT |
| authorized and executing | `started` | milestoned + assigned | `AUTHORIZED`, admitted true | AGREE + CORRECT |
| finished; authority is a separate axis | `completed` | closed | `AUTHORIZED`, admitted true | AGREE + CORRECT |
| not admitted at all | `triage` | no milestone | blocking unknown, `NOT_ADMITTED` | AGREE + CORRECT |
| **authority withdrawn** | `canceled` | closed `NOT_PLANNED` | `CANCELLED`, admitted **false** | AGREE + CORRECT |

**Run:** 2026-08-30. Roadmap providers `adapters/linear` (MCP transport, payload supplied on stdin) and `adapters/github-projects` against `tosin2013/repo-governor`. Instrument `tools/live-equivalence.py`; prerequisite check `tools/provider-readiness.py`.

## Why this is not the same as Layer 2

`conformance/layer2.py` reports EQUIVALENT across 12 scenarios and has done for months. It runs on **recorded fixtures**, because ADR-008 rule 1 requires fixed inputs for determinism, and `docs/reference/criteria.md` records the consequence in the same row that reports the 9/9: *"Evidence still weak."* Fixtures written by one author against one mental model measure shared intent as much as portability.

This run replaces the fixtures with two real trackers. Nothing else changed: the same five semantic states, the same projection over `authority`, `admitted`, `__unknown__` and `blocking`, and `reason` deliberately excluded so a more specific code is not scored as a divergence.

**Agreement without correctness is not success.** Two adapters both mapping withdrawal to `ADMITTED` would have printed AGREE. Every row above is AGREE **+ CORRECT** — checked against the expected map, not merely against each other.

## The withdrawal row is the point

`authority withdrawn` is the scenario that motivated the project: a roadmap item cancelled while work continues beneath it. Until this run it had **never been compared on two live providers** — Linear had no cancelled issue in the workspace under test, so the row scored SKIP and no amount of re-running would have changed that.

Both providers reduce it to `authority: CANCELLED, admitted: false`, from two unrelated representations: a Linear workflow state of type `canceled`, and a GitHub issue closed with `stateReason: NOT_PLANNED`. Neither adapter knows what the other calls it.

## What had to exist first, and what that cost

The equivalence question can only be asked about states **both** providers hold. The workspace under test could express three of the five:

| | before | fix | who |
|---|---|---|---|
| `canceled` | status declared, **zero issues** | create an issue, set that state | scripted |
| `triage` | **no such status** — the team feature was disabled | Team settings → Triage → enable | **human only** |

`provider-readiness.py` reports those as different answers on purpose. A status that does not exist and a status with nothing in it need different fixes, and collapsing them into "missing" is the absence-versus-unknown failure `references/providers.md` requires every adapter to avoid.

Two throwaway issues were created to hold the two states. They carry no work, say so in their own descriptions, and are disposable once this file exists.

**The instrument found its own prerequisite.** Before it existed, the only way to learn that this run could not reach 5 of 5 was to attempt it and read `skipped: 2`.

## What this establishes, and what it does not

**Establishes.** Five semantic states, expressed in two unrelated vocabularies by two real trackers, reduce to identical governance facts. §55's stop condition — *"cross-provider semantic normalization is not reliable"* — is **not triggered**, now on live evidence rather than on fixtures.

**Does not establish.** Both adapters were written by one author against one reading of the roles. Live data removes the fixture weakness; it does not remove that one. `criteria.md`'s *"evidence still weak"* note is **weakened, not lifted** — a third-party adapter remains the stronger test, and issue 1 says so in its own body.

Nor does it establish anything about providers not tested. Five states in two trackers is not a claim about a third.

**One state pair is untested by construction.** Linear's `unstarted` (Todo) maps to `AUTHORIZED`, and no scenario exercises it — `started` covers that row. Whether "Todo means cleared to execute" is the right reading is a separate question this run does not touch.

## Reproducing it

```sh
python3 tools/provider-readiness.py --github <owner/repo> < <mcp payload>   # expect 5 of 5
python3 tools/live-equivalence.py  --github <owner/repo> < <mcp payload>
python3 tools/live-equivalence.py  --self-test    # the instrument, offline
```

The Linear payload arrives on stdin as an MCP response, so no Linear credential is needed by the tool or the adapter (ADR-020, ADR-028). It is never written to disk.

## §51 clearance

This file records **counts, semantic state names and status type names only**. No issue identifier, title, description or assignee from the workspace under test appears here, and none was written to this repository at any point during the run. Issue 41's criteria enforce that mechanically rather than by reminder: one criterion fails this file if a workspace identifier pattern appears in it.

The GitHub side is this repository's own public issues and is not restricted.
