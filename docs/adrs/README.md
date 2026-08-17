# Architectural Decision Records — Repo Governor

Generated 2026-08-17 from PRD v0.2 (provider-oriented draft) using the MCP ADR Analysis Server's PRD-to-ADR protocol, informed by the external landscape research in [`../research/2026-08-17-external-landscape.md`](../research/2026-08-17-external-landscape.md).

All ADRs are **Proposed**. None is accepted. Per §61, the project cannot reach `IMPLEMENTATION_READY` until the `RG-SIM-ONBOARDING-v0.1` simulation passes.

> **`PRD.md` no longer exists.** Its normative content was extracted into [`../reference/`](../reference/) on 2026-08-17, with original § numbering preserved so every citation below still resolves. Start at the [section map](../reference/README.md#section-map).

## Index

| # | Decision | Domain | Settles |
| --- | --- | --- | --- |
| [001](001-agent-skill-as-primary-delivery-surface.md) | Agent Skill as the primary delivery surface | Distribution | Delivery form was undecided |
| [002](002-deterministic-policy-engine-separate-from-model-judgment.md) | Deterministic policy engine separate from model judgment | Policy engine | Makes §53 metrics measurable |
| [003](003-seven-provider-roles-with-normalized-contracts.md) | Seven provider roles with normalized contracts | Provider abstraction | Adapter wire protocol; partial support |
| [004](004-governance-manifest-as-sole-binding-artifact.md) | Governance manifest as the sole binding artifact | Configuration | What `.repo-governor.json` *means* |
| [005](005-deny-by-default-permission-model.md) | Deny-by-default permission model | Security | Default for unstated permissions |
| [006](006-repository-condition-model-drives-governance-profiles.md) | Repository condition drives governance profiles | Policy scaling | How L0–L4 is assessed and who decides |
| [007](007-closed-disposition-vocabulary-with-unknown-terminal.md) | Closed disposition vocabulary, `UNKNOWN` terminal | Output contract | What `UNKNOWN` means operationally |
| [008](008-fixture-based-provider-conformance-suite.md) | Fixture-based provider conformance suite | Testing | How portability is proven |
| [009](009-append-only-evidence-chain-for-decision-provenance.md) | Append-only evidence chain for provenance | Observability | Where decision history lives |
| [010](010-provider-detection-separated-from-binding.md) | Detection strictly separated from binding | Onboarding | Makes INV-013 structural |
| [011](011-python-stdlib-only-engine-with-language-agnostic-adapters.md) | Python stdlib-only engine, any-language adapters | Runtime | Language and dependency policy |
| [012](012-provider-content-treated-as-untrusted-input.md) | Provider content treated as untrusted input | Security | **Gap in §51** — prompt injection |
| [013](013-single-canonical-authority-per-role.md) | Single canonical authority per role, halt on conflict | Conflict resolution | Role cardinality; no tie-breaking |
| [014](014-scope-envelope-as-bounded-execution-contract.md) | ScopeEnvelope as bounded contract + completion firewall | Domain model | How scope boundaries are drawn |
| [015](015-json-as-canonical-manifest-format.md) | JSON as the canonical manifest format | Configuration | Closes ADR-011's deferred choice; unblocks gate 5 |
| [016](016-mcp-as-adapter-transport-not-adapter-replacement.md) | MCP as adapter transport, not replacement | Integration | Whether providers route via MCP servers |
| [017](017-completion-evidence-from-repo-local-acceptance-artifact.md) | Completion evidence from a repo-local acceptance artifact | Domain model | Makes `STOP_COMPLETE` derivable; unblocks gate 7 |
| [018](018-admission-signal-is-declared-not-assumed.md) | Admission signal is declared, not assumed | Provider abstraction | Makes GitHub usable without a Project; **found by real-data testing** |
| [019](019-database-backed-decision-history.md) | Database-backed decision history | Storage | Closes the last unbound role; amends ADR-009 |
| [020](020-agent-supplied-transport-with-adapter-as-normalizer.md) | Agent-supplied transport, adapter as normalizer | Transport | Moves credentials out of remote adapters; amends ADR-003 and ADR-016 |

## Dependency order

```text
001 (skill)  ──┬──> 006 (profiles) ──> 008 (conformance)
               │
002 (engine) ──┼──> 007 (dispositions) ──> 014 (envelope + firewall)
               │
003 (roles)  ──┼──> 004 (manifest) ──┬──> 005 (permissions)
               │                     ├──> 010 (detection)
               │                     └──> 013 (cardinality)
               │
011 (runtime) ─┘
012 (untrusted input) — cross-cutting, constrains 003, 004, 009, 010
015 (JSON manifest) — resolves 011's deferred choice; unblocks gate 5
016 (MCP transport) — constrains 003; engine never calls MCP directly
017 (acceptance artifact) — adds 8th role; unblocks gate 7, fixes #2 root cause
009 (evidence chain) — depends on 002, 004; enables INV-005, INV-008
```

Read 001 and 002 first. They are the two decisions everything else assumes.

## What changed relative to PRD v0.2

The ADRs are not a restatement. Six things are settled, added, or contradicted — all four textual changes are now folded into [`../reference/`](../reference/):

1. **Delivery form decided (001).** PRD v0.2 listed MCP, hooks, IDE, and CI as undifferentiated future candidates. Agent Skills becoming a 26-platform open standard on 2025-12-18 makes skill-first the tool-independent choice rather than a vendor bet. §65 updated.
2. **Determinism made binding (002).** The invariants read as prose. An agent that reasons past prose is the documented April 2026 failure. Invariants become executable predicates; `SKILL.md` documents the code rather than carrying the rule.
3. **New ADR with no PRD basis (012).** §51's security model did not address prompt injection, yet every input is text third parties can write. §51 amended with the missing bullet.
4. **§21 inconsistency resolved (013).** The manifest sketch treated some roles as lists and others as scalars without saying why. ADR-013 makes cardinality a rule derived from whether a role answers "is this authorized?" §21 annotated.
5. **A live stop condition identified.** Beads issue #1150 requests plugin-based tracker integrations. If delivered, it overlaps the provider-abstraction thesis. §55 now tracks it as a concrete input rather than an abstract risk. Current assessment: Beads federating trackers makes it a better `ExecutionStateProvider`, not a competitor, because it aggregates state without ruling on authority.
6. **Differentiation confirmed.** No tool in the spec-driven-development or tracker categories answers "is this work currently authorized?" across providers. OpenSpec and Spec Kit answer *how to build*; none reconciles a spec against a withdrawn roadmap item. The §56 differentiation candidate survives the sweep.

## Open questions

These are not deferred decisions — they are things no one can answer yet without evidence.

| # | Question | Where it bites | Resolved by |
| --- | --- | --- | --- |
| ~~1~~ | ~~Manifest canonical format~~ — **resolved by [ADR-015](015-json-as-canonical-manifest-format.md)**: JSON canonical. Spike showed a 143-line YAML subset silently mis-types 7/10 realistic values. | 011, 004 | ✅ [#3](https://github.com/tosin2013/repo-governor/issues/3) closed |
| 2 | Decision-record redaction default for public repositories | 009, 012 | Design decision before v1 |
| 3 | Does cross-provider semantic normalization actually work? | 003, 008 | ADR-008 Layer 2 with two real providers — **this is the thesis test** |
| 4 | How thin are compiled ScopeEnvelopes on real roadmap items? | 014 | Measurement across real repositories |
| 5 | Skill activation reliability across hosts | 001 | 20-prompt activation test on 3 hosts |
| 6 | Monorepo / per-package governance | 004, 006 | Deliberately deferred past v1 |

Questions 3 and 4 are the ones that could invalidate the product. Both should be answered early, while changing course is still cheap.

## Path to IMPLEMENTATION_READY

[§61](../reference/onboarding.md) lists seven gate conditions. Current coverage:

| Gate condition | Status | Evidence |
| --- | --- | --- |
| 1. Onboarding simulation passes | ✅ **Met** — `completion.py GATE-1` → `STOP_COMPLETE` | [`conformance/onboarding.py`](../../conformance/onboarding.py) **29/29**, `RG-SIM-ONBOARDING-v0.1: PASS`. Fixtures A–C materialized into isolated temp repos |
| 2. Provider conflicts handled deterministically | ✅ **Met** — `completion.py GATE-2` → `STOP_COMPLETE` | Fixture C raises `PROVIDER_CONFLICT` on `roadmap_authority`, names both candidates, applies no ranking |
| 3. Low-complexity repos need no extra providers | ✅ **Met** — `completion.py GATE-3` → `STOP_COMPLETE` | Fixture A detects only `repository`; condition L0; state `AUTHORITY_SOURCE_MISSING` |
| 4. Detection does not assign authority | ✅ **Met** — `completion.py GATE-4` → `STOP_COMPLETE` | Proposal written to `.repo-governor.proposed.json`; asserted the manifest loader never reads it; binding requires human promotion |
| 5. Manifest semantics stable | ✅ **Met** — verified by `engine/completion.py GATE-5` → `STOP_COMPLETE` | `schemas/manifest-v1.json` frozen; `engine/manifest.py` fails closed; [26/26 refusal cases](../../conformance/manifest.py); `--validate` reaches `READY_FOR_GOVERNANCE`; `engine/migrate.py` stub exists per ADR-004 step 5 |
| 6. One viable adapter per required core role | ✅ **Met** — verified by `engine/completion.py GATE-6` → `STOP_COMPLETE`, not by assertion | All 9 adapters pass [Layer 1](../../conformance/layer1.py) **112/112**; [Layer 2](../../conformance/layer2.py) 9/9 EQUIVALENT across 3 roadmap providers; criteria in `.repo-governor/acceptance/GATE-6.json` |
| 7. `UNKNOWN` and failure behavior defined | ✅ **Met** — `completion.py GATE-7` → `STOP_COMPLETE` | [`engine/vocabulary.py`](../../engine/vocabulary.py) closes 12 governance + 8 onboarding dispositions and 18 reasons; [`conformance/vocabulary.py`](../../conformance/vocabulary.py) proves the sets cannot drift from the code |

**All seven gate conditions are met**, each on `engine/completion.py`'s verdict rather than assertion. Per §61 the specification may move to `IMPLEMENTATION_READY`.

Reproduce the whole thing:

```bash
for g in 1 2 3 4 5 6 7; do python3 engine/completion.py GATE-$g; done
for s in layer1 layer2 transport manifest onboarding vocabulary; do python3 conformance/$s.py; done
```

### What `IMPLEMENTATION_READY` does not mean

The gate asks whether the architecture is stable enough to build on. It does not ask whether the product is worth building, and four things remain open:

* **All 17 ADRs are still `Proposed`.** None has been accepted. The gate was met against decisions nobody has ratified.
* **#1 (cross-provider normalization) has weak evidence.** 9/9 scenarios agree, but all three adapters were written by the same author against the same map — that measures shared intent as much as portability. A third-party adapter is the real test.
* **#2 (envelope thinness) is unmeasured** on any real repository.
* **The criteria-drift weakness is unresolved.** Acceptance criteria were amended twice during implementation. Both amendments were justified and recorded, and nothing but that record distinguishes a legitimate correction from a convenient one.
