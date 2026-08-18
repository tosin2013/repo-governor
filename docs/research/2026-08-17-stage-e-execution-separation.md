# Stage E — execution separation: experiment design and Beads go/no-go

**Date:** 2026-08-17 · **Issue:** [#33](https://github.com/tosin2013/repo-governor/issues/33) · **Program:** [#31](https://github.com/tosin2013/repo-governor/issues/31)
**Status:** design complete. **Verdict: NO-GO on a Beads adapter, for now.**

The maintainer's standing constraint on this program:

> Do not admit building the Beads adapter merely because this test would be interesting. First define the experiment and show that Beads is necessary to answer the execution-state question. Then admit the smallest adapter required for that experiment.

This is that necessity argument. It concludes that the adapter is not the missing piece, and names what is.

## The question

> **Can execution state remain subordinate to roadmap authority?**

Three scenarios express it, and the third is close to the entire product thesis in one case:

| # | Roadmap | Execution | Decision history | Required outcome |
|---|---|---|---|---|
| 1 | `CANCELLED` | subtasks `READY` / `IN_PROGRESS` | records prior authorization | `AUTHORITY_WITHDRAWN` |
| 2 | `AUTHORIZED` | no execution state at all | — | authorized; **no work invented** |
| 3 | `AUTHORIZED` | all subtasks complete + one `DISCOVERED` | — | `STOP_COMPLETE`; discovery `CAPTURE_ONLY` |

## The finding that decides it

**No engine module consults the `execution` role.**

```console
$ grep -c 'execution' engine/completion.py engine/envelope.py
engine/completion.py:0
engine/envelope.py:1        # a comment, not a call
```

`engine/onboard.py` *proposes* an execution binding. `engine/manifest.py` validates its cardinality. Nothing ever asks it a question. The role is bindable, conformance-tested at Layer 1, and **read by nothing**.

So scenario 1 — the one that motivated the whole project — cannot fail today, because the engine never looks at the execution state that would contradict the roadmap. It also cannot *pass*: there is nothing to observe. The same is true of any execution provider, Beads included.

**Building a Beads adapter now would produce a provider nothing reads.** That is the necessity argument, and it settles the question.

## What the three scenarios actually test

Sorting them by where the property lives:

| Scenario | Property under test | Lives in |
|---|---|---|
| 1 | roadmap authority overrides execution state | **the engine's composition** |
| 2 | absent execution state is not an invitation to invent work | **the engine's composition** |
| 3 | completion firewall + discovery capture with execution present | engine — and #23 already proved the firewall half |

None of the three is a property of Beads. They are properties of how the engine composes roles, which is why `adapters/execution-file` — already bindable, already advertising eight capabilities against its fixture — can express all three.

```console
$ REPO_GOVERNOR_EXECUTION=conformance/fixtures/execution.json ./adapters/execution-file describe
{"caps":["completed_work","dependencies","discoveries","execution_history",
         "execution_root","failures","handoff_state","tasks"],"reachable":true}
```

## The honest counter-argument, and why it does not change the verdict

This session has repeatedly shown that **real providers surface defects fixtures cannot** — ADR file naming read as zero decisions, 16% status-dialect coverage, MCP payloads the adapter refused, the engine governing the wrong repository. A fixture I write cannot surprise me, and that is a real limitation of fixture-based evidence.

So a Beads adapter probably *is* worth building eventually. It is not worth building **to answer this question**, and it is worth nothing at all until the engine reads the role. Those are different claims and conflating them is how the adapter gets built for the wrong reason.

## Two facts about Beads, recorded for when it is time

**`mcp-adr-analysis-server` does not use Beads.** No `.beads` directory. Stage E cannot use the program's chosen subject repository for the execution lane without constructing execution state that does not exist — which would make it a fixture with extra steps.

**`bd` is installed (1.1.2) and exports JSONL.** `bd export` means the smallest Beads adapter is a thin normalizer over exported records — no SQLite driver, no Python dependency, consistent with ADR-011 rule 4 and the pattern in `references/storage-backends.md`. Cheap, when it is warranted.

## A third instance of a defect class

`engine/onboard.py` proposes `adapters/execution-file` on `.beads/` evidence — a **JSON-file adapter for a SQLite-backed store**. It cannot read what was detected.

This is the same over-promise [#27](https://github.com/tosin2013/repo-governor/issues/27) fixed twice: detection naming an adapter that cannot serve the provider it found (ADR status counting, then Renovate/Dependabot). Third instance, same shape, and worth stating as a general rule rather than patching case by case:

> **Detection may name an adapter only if that adapter can read the evidence that triggered the detection.**

## Recommended sequence

1. **The engine composes execution state.** New work, its own issue: `completion.py` consults the `execution` role, and scenarios 1 and 2 become expressible. Until this lands, nothing else in Stage E is testable.
2. **Prove the three scenarios with `execution-file` fixtures.** Necessary condition, and sufficient for the *property*.
3. **Then re-open the Beads question** — with the honest framing that it buys robustness evidence, not the property itself.

## Verdict

**NO-GO on the Beads adapter.** Not "not yet interesting" — *not yet readable*. The gap Stage E exposes is in the engine, and the maintainer's constraint did exactly what it was written to do: asking for the necessity argument surfaced a missing half nobody had noticed.

`no-go` was named a successful outcome when this issue was filed. It is the one that happened.
