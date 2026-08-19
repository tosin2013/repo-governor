# Adding an integration

Repo Governor is tool-independent by thesis. That only holds if somebody other
than its author can wire in a tracker, a store, or an execution system without
touching the engine — so this is what an integration must satisfy, and how it
is checked.

Read [`providers.md`](providers.md) first for what each role answers.
[`storage-backends.md`](storage-backends.md) goes deeper on `decision_history`
specifically; everything here applies to every role.

## The rule that shapes all the others

> **An integration carries governance through. It does not reinvent it.**

Every tracker has its own notion of *ready*, *blocked*, *done*, *priority*. An
integration **normalizes that state into the closed vocabulary and stops.** It
never introduces a disposition, never asserts authority, and never resolves an
`UNKNOWN` by assuming.

This is not stylistic. The failure it prevents is the one the product exists
for:

> *"This task is marked Ready, so I should work on it."*

A task marked ready in an execution tracker is **execution state**. Whether the
work is authorized is the `roadmap_authority`'s answer, and the two are
different questions — INV-002, *admission is not authorization*. An `execution`
adapter that reported "ready" as authority would reproduce §54's failure
condition inside the adapter layer, where nothing else is looking for it.

The engine rules. Providers supply state and evidence. If your integration ever
needs to decide something, it is doing the engine's job and the answer is
almost always to report an `UNKNOWN` with a typed reason instead.

## Seven requirements

The first four come from [`storage-backends.md`](storage-backends.md) and apply
to every role, not just to stores.

**1. Probe honestly.** Missing means absent. An adapter whose backend is not
installed advertises **no capabilities** rather than an empty result — a
missing database must never read as an empty history. `_protocol.main(probe=…)`
implements the rule; supply the probe.

**2. Fail typed, never empty.** An unreachable or unreadable backend returns a
declared error type. A traceback is not a typed failure: `file-roadmap` once
raised `AttributeError` on a wrongly-shaped file, the engine reported reason
`NON_JSON`, and a reader went hunting a syntax error in valid JSON.

**3. Distinguish absence from unknown.** "This id does not exist" and "I cannot
tell" are different answers with different consequences. Absence is a fact;
unknown is a gap, and `UNKNOWN` is a valid, complete answer (INV-012).

**4. Cite every fact.** Provenance is mandatory and non-empty. A fact without a
citation cannot be argued with.

**5. Declare what you cannot supply.** Advertise `capabilities` honestly.
`github-projects` reports `scope: false` and is right to — an advertised gap is
not a failure, and Layer 2 explicitly does not score one as a divergence. Papering
over a gap by inventing a plausible answer is far worse than admitting it.

**6. Declare required configuration.** If your integration cannot answer without
an identity, an API key, or a path, report `configured: false` from
`config_probe` **and name the missing thing**. `--validate` reports it rather
than calling the binding ready. "Not configured" that does not say what is
missing is not actionable.

**7. Declare a weaker guarantee as weaker.** Where two backends fill one role,
they will differ in what they promise. `decision-history-dolt` reports
`chain_supplied_by_store: true` because the store maintains the chain;
`decision-history-file` reports `false` because it hand-rolls one, so a rewrite
is *detectable, not prevented*. **Equivalence of answers must not imply
equivalence of guarantees**, and a consumer must be able to tell which it has.

## How it is checked, mechanically

An integration is not accepted by review of its intentions.

**Layer 1** (`conformance/layer1.py`) is the contract test: C1–C10, covering
well-formed `describe`, honest capability advertisement, typed failure on an
unreachable backend, absence versus unknown, provenance, refusal of unsupported
functions, byte-identical determinism, an unreachable transport claiming
nothing, an unwritable transport advertising no writers, and a **reachable but
structurally wrong** store returning a typed error rather than a crash. Add a
`SUITE` entry and it either passes or it does not.

**Layer 2** (`conformance/layer2.py`) is the semantic bar: two backends of one
role must agree on disposition-relevant facts from equivalent state. This is
what catches an integration that quietly reinterprets meaning — the failure
that Layer 1 cannot see, because a reinterpretation can be perfectly
well-formed.

Both are runnable before you open anything: `./tools/run-conformance.sh`.

## The three integrations, concretely

| tier | role | what it guarantees |
|---|---|---|
| **filesystem** | any | The default. Zero dependencies, always available, weakest guarantees — and honest about them. `file-roadmap`, `execution-file`, `acceptance-file`, `change-signals-file`, `decision-history-file`. |
| **Dolt** | `decision_history` | The reference implementation. Supplies history natively (`dolt_log`, `dolt_history_decisions`), so it does not hand-roll a chain and says so. Recommended where the evidence chain must hold against an adversary rather than against a mistake. |
| **Beads** | `execution` | **A candidate, not admitted.** The contract below is what it would have to satisfy; documenting that is not the same as deciding to build it. |

### Why Beads is documented but not built

The `execution` role is required at `GOVERNOR_FULL` and above, and
`execution-file` fills it today. Whether a real execution tracker is *necessary*
is an open experiment, and the standing rule is deliberate:

> Do not admit building the Beads adapter merely because this test would be
> interesting. First define the experiment and show that Beads is necessary to
> answer the execution-state question.

A **no-go is a successful outcome**. A role may be required; a product may not
be recommended on the strength of anyone having enjoyed using it.

An execution integration would answer `find_execution_root`, `get_active_work`,
`get_completed_work`, `get_dependencies`, `get_discoveries`,
`get_execution_history`, `get_failures`, `get_handoff_state`, `get_tasks` — and
would be bound by the rule at the top of this page harder than any other role,
because execution trackers are where "ready" lives.

## Practical notes

- **A CLI, not a driver.** Shell out. The engine imports no provider SDK
  ([ADR-011](../docs/adrs/011-python-stdlib-only-engine-with-language-agnostic-adapters.md)),
  and an adapter that shells out keeps that guarantee intact while staying
  usable from cron and CI.
- **Any language.** The protocol is a subprocess contract — `describe`,
  `query <role> <fn> k=v`, `write` — so a Go adapter, a Python adapter and a
  shell adapter all satisfy it identically.
- **Adapters may carry dependencies; the engine may not.** That asymmetry is
  the point.
- **Refuse unsafe input rather than escaping it.** Refusing is checkable;
  escaping is a promise.
- **Licensing.** Apache-2.0 was chosen partly for its contribution terms,
  because the adapter protocol is designed to invite third-party integrations.

Start from `adapters/_protocol.py` and the smallest shipped adapter that fills
your role. Every one of them is a single file.
