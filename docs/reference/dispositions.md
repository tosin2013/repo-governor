# Governance Dispositions

> Extracted from PRD v0.2 §41–§42 on 2026-08-17. Original section numbering preserved.
> **Normative.** ADR-007 closes this vocabulary at nineteen values, engine-owned. Profiles select which are *reachable*; they cannot define new ones. Providers never emit dispositions.

---

## §41 — Governance Dispositions

### Execution

```text
EXECUTE
CONTINUE
STOP_COMPLETE
```

### Capture / Review

```text
CAPTURE_ONLY
ROADMAP_REVIEW
ARCHITECTURE_REVIEW
MAINTENANCE_REVIEW
RETIREMENT_REVIEW
```

### Refusal / Uncertainty

```text
NO_EXECUTION_AUTHORITY
AUTHORITY_WITHDRAWN
CONFLICT
UNKNOWN
```

## §42 — Onboarding Dispositions

A **separate alphabet** with a different state machine and a different consumer (a human running onboarding, not an agent mid-task). These never appear in a governance decision, and the two sets never mix.

```text
PROVIDER_DETECTED
PROVIDER_UNCONFIRMED
PROVIDER_CONFIGURED
PROVIDER_UNAVAILABLE
PROVIDER_CONFLICT
AUTHORITY_SOURCE_MISSING
READY_FOR_GOVERNANCE
```

---

## Semantics (ADR-007)

**Exactly one disposition per evaluation.** The top-level decision is singular; per-discovery dispositions nest beneath it.

**`UNKNOWN` must be actionable.** An `UNKNOWN` carrying only "unknown" is a defect. Required payload:

```yaml
decision: UNKNOWN
unknowns:
  - dimension: authority          # which of the seven questions failed
    reason: PROVIDER_UNREACHABLE  # typed, enumerated
    provider: linear
    resolution: |                 # what a human can do about it
      Verify LINEAR_API_KEY is set, or bind a manual roadmap provider.
    blocking: true                # does this prevent EXECUTE?
```

The engine distinguishes **unresolvable** (evidence genuinely absent) from **unavailable** (provider down). Both yield `UNKNOWN`; the resolution differs.

**Non-blocking unknowns do not force review.** Only unknowns on the evaluation's critical path block. This is what keeps INV-012 from colliding with the over-escalation failure condition ([criteria.md §54](criteria.md)).

**`STOP_COMPLETE` is terminal and non-overridable** (INV-009).

**Tie-break is conservative.** Where the engine cannot determine whether a disposition should be `EXECUTE` or something more conservative, it resolves conservatively. The asymmetry is real: a wrongly-blocked change costs a human a minute; a wrongly-permitted deletion can cost a release.
