# Repo Governor

**A tool-independent governance skill for AI-assisted software development.**

Repo Governor determines what an AI coding agent is authorized to create, change, maintain, or retire in a repository — what it must capture or escalate instead, and when it must stop.

It does not replace your existing tools. It connects to them through provider interfaces and evaluates their state under a consistent governance protocol.

> **Providers supply state and evidence. Repo Governor determines what that state permits.**

---

## Status: pre-implementation

This repository currently contains **specification and research only**. There is no implementation yet.

| | |
| --- | --- |
| Product state | Specification complete; 14 ADRs, all **Proposed**, none accepted |
| Gate | `RG-SIM-ONBOARDING-v0.1` must pass before `IMPLEMENTATION_READY` |
| Gate progress | 0 of 7 conditions validated ([§61](docs/reference/onboarding.md)) |

---

## The problem

AI coding agents work across repositories full of overlapping information — roadmaps, issues, task graphs, ADRs, specs, source, TODOs, feature flags, dead branches, execution memory. **These artifacts do not have equal authority.** But an agent will infer permission from information merely because it exists:

> "This TODO exists, so I should implement it."
> "This task is marked Ready, so I should work on it."
> "A new major version was released, so I should upgrade."
> "This module has no static references, so I should delete it."
> "The feature is complete, but I found three improvements, so I should continue."

The result is unauthorized feature expansion, roadmap drift, unsafe retirement, and agents that don't stop when the work is done.

The governing principle:

> **Information may justify a decision. Information does not acquire authority merely by existing.**

## How it works

Seven pluggable provider roles, each answering a different governance question:

| Role | Question | Example implementations |
| --- | --- | --- |
| `RoadmapAuthorityProvider` | Is this work admitted and still authorized? | Linear, Jira, GitHub Projects, file |
| `ArchitectureEvidenceProvider` | What constrains how it must be built? | ADRs, OpenSpec, Spec Kit, Mneme |
| `ExecutionStateProvider` | What is the state of work beneath it? | Beads, Amber, GAAI, Backlog.md |
| `RepositoryEvidenceProvider` | What is actually in the repository? | Git |
| `ChangeSignalProvider` | What changed outside the repository? | Renovate, Dependabot |
| `RetirementEvidenceProvider` | What obligations block removal? | static analysis, telemetry |
| `DecisionHistoryProvider` | What was already decided about this? | built-in decision log |

Keeping these separate is the point — it's what stops *"the task says READY"* from implying *"the work is authorized."*

A deterministic engine reconciles their state and returns one bounded disposition: `EXECUTE`, `CONTINUE`, `STOP_COMPLETE`, `CAPTURE_ONLY`, `AUTHORITY_WITHDRAWN`, `UNKNOWN`, and thirteen others. It returns a verdict; it never performs the action.

Governance depth scales with repository condition (L0 greenfield → L4 mature/high-assurance), so a two-file repository needs Git, a ten-line manifest, and four invariants — nothing more.

## Repository layout

```text
docs/
  adrs/        14 architectural decisions (all Proposed) + index
  reference/   normative specification, §1–§70, INV-001…INV-014
  research/    external landscape sweep, 2026-08-17
```

**Start here:**

- [ADR index](docs/adrs/README.md) — the decisions, dependency order, and open questions
- [ADR-001](docs/adrs/001-agent-skill-as-primary-delivery-surface.md) and [ADR-002](docs/adrs/002-deterministic-policy-engine-separate-from-model-judgment.md) — the two decisions everything else assumes
- [Invariants](docs/reference/invariants.md) — INV-001 … INV-014, the irreducible rules
- [Section map](docs/reference/README.md#section-map) — where any `§NN` citation resolves

## Design commitments

- **Ships as an [Agent Skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)** — an open standard adopted by 26+ platforms. Clone it into a skills directory; no install, no service, no vendor lock. ([ADR-001](docs/adrs/001-agent-skill-as-primary-delivery-surface.md))
- **Deterministic, not model-judged** — invariants are executable predicates, not prose an agent is asked to honor. Same inputs, same disposition, always. ([ADR-002](docs/adrs/002-deterministic-policy-engine-separate-from-model-judgment.md))
- **Zero dependencies** — Python stdlib only. A tool that rules on what agents may change shouldn't drag in a transitive dependency tree. Adapters may be written in any language. ([ADR-011](docs/adrs/011-python-stdlib-only-engine-with-language-agnostic-adapters.md))
- **Deny by default** — no permission is inferred from an available credential. ([ADR-005](docs/adrs/005-deny-by-default-permission-model.md))
- **Provider content is untrusted input** — roadmap text and issue bodies become typed facts and cited evidence, never instructions. ([ADR-012](docs/adrs/012-provider-content-treated-as-untrusted-input.md))
- **`UNKNOWN` is a valid answer** — carrying a typed reason and a resolution path. ([ADR-007](docs/adrs/007-closed-disposition-vocabulary-with-unknown-terminal.md))

## What this is not

Not a project-management system, roadmap database, issue tracker, execution tracker, spec system, ADR system, dependency updater, CI/CD engine, static-analysis engine, autonomous architect, or hosted service. It reuses existing tools rather than rebuilding mature functionality. ([§8](docs/reference/product-scope.md))

## Open questions

Two could invalidate the product, and both are being answered early while changing course is still cheap:

1. **Does cross-provider semantic normalization actually work?** If Linear and GitHub Projects produce different dispositions from equivalent state, the abstraction has failed. Tested by [ADR-008](docs/adrs/008-fixture-based-provider-conformance-suite.md) Layer 2.
2. **How thin are compiled scope envelopes on real roadmap items?** Most trackers lack explicit non-goals, and a thin envelope governs weakly.

Full list, plus the standing [stop conditions](docs/reference/criteria.md), in the [ADR index](docs/adrs/README.md#open-questions).

## Ownership

Public open-source under **Tosin Open Source**. Human owner and final acceptance authority: Tosin Akinosho.

Decision Crafters retains research provenance, reference-application provenance, and nonexclusive upstream use, subject to this project's future license and separately accepted relationships. ([§68](docs/reference/product-scope.md))

---

> **Tools tell us what they know. Governance determines what that knowledge allows an agent to do.**
>
> **AI may discover broadly, but it may execute only within explicitly resolved authority.**
