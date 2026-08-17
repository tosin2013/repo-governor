# Dispositions and unknowns — operational reference

Closed sets, enforced by [`engine/vocabulary.py`](../engine/vocabulary.py).
Normative semantics: [`docs/reference/dispositions.md`](../docs/reference/dispositions.md).

## Governance dispositions (12)

**Execution** — `EXECUTE` · `CONTINUE` · `STOP_COMPLETE`
**Capture / review** — `CAPTURE_ONLY` · `ROADMAP_REVIEW` · `ARCHITECTURE_REVIEW` · `MAINTENANCE_REVIEW` · `RETIREMENT_REVIEW`
**Refusal / uncertainty** — `NO_EXECUTION_AUTHORITY` · `AUTHORITY_WITHDRAWN` · `CONFLICT` · `UNKNOWN`

Exactly one per evaluation. Per-discovery dispositions nest beneath it.

## Onboarding dispositions (8) — a separate alphabet

`PROVIDER_DETECTED` · `PROVIDER_UNCONFIRMED` · `PROVIDER_CONFIGURED` · `PROVIDER_UNAVAILABLE` · `PROVIDER_CONFLICT` · `AUTHORITY_SOURCE_MISSING` · `READY_FOR_GOVERNANCE` · `PROPOSAL_READY`

These never appear in a governance decision. Different state machine, different consumer.

## Handling `UNKNOWN`

Read `unknowns[]`. Each entry carries:

```json
{ "reason": "NO_CRITERIA_DECLARED", "dimension": "acceptance",
  "blocking": false, "resolution": "Declare criteria in ..., or accept no completion bar." }
```

- **`blocking: true`** → stop and report the `resolution`.
- **`blocking: false`** → real uncertainty that does not gate this decision. Note it; continue.

The split is *"does the current decision depend on it"*, **not** *"how serious is it"*. That distinction is what keeps `UNKNOWN` from turning every discovery into human review.

## Blocking reasons (7)

`AUTHORITY_UNSTATED` · `NOT_ADMITTED` · `NOT_ON_BOARD` · `CHECK_TIMED_OUT` · `NOT_VISIBLE_TO_STATIC_ANALYSIS` · `PROVIDER_UNREACHABLE` · `TRANSPORT_UNCONFIGURED`

Everything else is non-blocking by default. A profile may **escalate** a non-blocking reason; nothing may loosen a blocking one.

Adapters name a reason; the **engine** classifies it. A reason outside the closed set raises.
