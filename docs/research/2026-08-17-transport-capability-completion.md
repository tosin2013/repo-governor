# Research: transport, capability, and completion evidence

**Date:** 2026-08-17
**Questions:** [#15](https://github.com/tosin2013/repo-governor/issues/15), [#16](https://github.com/tosin2013/repo-governor/issues/16), [#17](https://github.com/tosin2013/repo-governor/issues/17), [#18](https://github.com/tosin2013/repo-governor/issues/18)
**Status:** Research complete; each question ends with a recommendation, none is decided.

All four came out of building adapters, not planning. #16–#18 are one knot — where Repo Governor sits, what it advertises, and who fetches. #15 is independent and the most urgent.

---

## 1. #17 — Capabilities are per (provider × transport)

### Prior art: LSP solved this exactly

The Language Server Protocol has the identical problem — arbitrary clients, arbitrary servers, wildly varying feature coverage — and settled it with **bidirectional capability negotiation** at `initialize`:

- The client sends `ClientCapabilities`; the server replies with `ServerCapabilities`. Neither assumes anything about the other.
- **A missing property means absence of the capability.** Not "unknown", not "default true" — absent. Sub-properties inherit the same rule.
- Unknown properties are ignored, so a newer peer talking to an older one degrades rather than breaks.
- `client/registerCapability` and `client/unregisterCapability` let capabilities change *after* initialize, so a server can react to configuration changes without a restart.
- An `experimental` section carries features not every client has adopted.

### What transfers

| LSP mechanism | Repo Governor equivalent |
| --- | --- |
| `initialize` handshake | `describe`, but taking the bound transport as input |
| missing property = absent | fixes the demonstrated defect directly |
| dynamic (un)registration | answers #17 Q5 (modality drift) without a restart |
| `experimental` section | lets an adapter expose a capability before it is contractual |

The "missing means absent" rule is the important one, and it is a *stronger* claim than what Repo Governor does today. Right now `adapters/linear` emits a module-level `CAPABILITIES` dict whether or not a transport is configured — an unconfigured adapter advertises five capabilities and serves none. Under the LSP rule, an adapter that cannot reach its backend advertises nothing.

### Recommendation

Adopt the LSP posture in three steps, cheapest first:

1. **Now, no design debt:** `describe` returns capabilities computed from actual transport state. Unconfigured or unreachable → empty capability set. Add a conformance check asserting it.
2. **With ADR-016's `transport` field:** `describe --transport=mcp` returns the capability set for *that* transport. Capabilities become a function of the pair, which is what they always were.
3. **Later, if drift proves real:** a re-probe on `validate` rather than full dynamic registration. LSP needs live registration because sessions are long; Repo Governor's are short.

Note this makes conformance run per (adapter, transport) pair — #17 Q4 answered yes, and the matrix multiplies. That is the honest cost.

---

## 2. #16 — Middleware position, middleware mandate

### Prior art: the OpenTelemetry Collector

The closest structural analogue. The Collector is a vendor-agnostic pipeline of **receivers → processors → exporters**: receivers ingest in many formats, processors transform centrally (scrubbing attributes, batching), exporters fan out to many backends.

The decisive property: **it is explicitly not a backend.** It sits in the path of all telemetry and declines to be the system of record. Its stated value is decoupling instrumentation from vendors, central processing, and buffering during backend outages — all things you can only do *from* the middle, none of which require owning the data.

That is precisely "middleware position, no middleware mandate", already proven at scale.

### What transfers, and what does not

Transfers:
- Occupying the middle is legitimate and does not oblige you to become the systems you front.
- Central processing is the *justification* for the position — for OTel, scrubbing and fan-out; for Repo Governor, authority resolution. If the middle does nothing valuable, it is just latency.
- The receiver/processor/exporter split is a clean separation between *transport* and *semantics*, which is exactly the boundary #18 is asking about.

Does not transfer:
- OTel is always in the data path and must be operationally reliable; a governance skill is advisory and can be absent. Repo Governor's failure mode is "advice missing", not "telemetry lost".
- OTel's positioning is unambiguous because telemetry has no authority semantics. Repo Governor is easily mistaken for the roadmap itself, which §54 names as a failure condition. Adopting "middleware" language raises that risk, not lowers it.

### Recommendation

**Accept the position; refuse the mandate; do not lead with the word.**

Amend §9's architecture diagram to show access modality explicitly — it currently implies providers are uniform peers, which the adapter work disproved. Leave §66's public positioning as governance-first. Internally, "middleware" is an accurate description of where it sits; externally it invites the expectation of an integration product, which is the failure mode.

Add to §54 the failure conditions the middle brings, which are absent today:

- becomes a bottleneck on every agent action;
- is blamed for provider outages it merely relays;
- accretes integration surface until it competes with iPaaS tooling.

---

## 3. #18 — Should the agent be the transport?

### The finding that decides it

2026 structured-output research is unambiguous on one point and easy to over-read on another.

**What is solved:** constrained decoding compiles a JSON Schema into a finite state machine and permits only tokens that keep output on a valid path — *a mathematical guarantee, not a statistical one*. First-attempt success exceeds 95%; unconstrained prompting produces malformed JSON in 8–15% of responses.

**What is not solved:** schema conformance is a guarantee about **shape**, not **content**. Constrained decoding guarantees `{"authority": "AUTHORIZED"}` is well-formed and drawn from the enum. It guarantees nothing about whether `AUTHORIZED` was the right reading of `state: {name: "Todo", type: "unstarted"}`.

That distinction settles option B. Under B the model performs the normalization mapping, so the *judgement* — not merely the serialization — is model-produced. ADR-002 rule 3 permits the model to translate fuzzy state into typed facts, but ADR-002's whole purpose is that the disposition is computed, not inferred, and a mapping from workflow state to authority is a disposition input of the most load-bearing kind. It would also make ADR-008 C7 (byte-identical determinism) and §53 provider portability unmeasurable, which removes #1's falsifiable claim.

### Option C survives, and OTel is the shape of it

Option C — agent fetches, adapter normalizes as a pure function — maps directly onto receiver/processor:

```
agent (receiver: MCP | gh | curl | bd)  →  raw JSON
                                        →  adapter (processor: pure, no I/O)
                                        →  typed facts + provenance
                                        →  engine
```

It keeps every property that matters: the mapping stays mechanical, determinism survives, provenance stays structural, credentials never touch an adapter, and the transport matrix disappears. Conformance gets *easier* — a pure function is trivially testable against recorded raw input, and the fixtures already are recorded raw input.

**Unresolved risk (#18 Q1):** raw Linear-MCP output and raw Linear-GraphQL output are shaped differently for the same issue. If one normalizer cannot handle both, C reintroduces #17 through the back door as one normalizer per (provider, transport). This is testable now and should be tested before committing.

**Unresolved risk (#18 Q2):** under C the agent chooses what to fetch. Nothing stops it querying the wrong issue or passing a summary instead of the payload. Under A the adapter controlled the query. Mitigation: the adapter validates raw input against an expected shape and fails `MALFORMED_SOURCE` rather than normalizing something plausible — the ADR-015 lesson again.

### Recommendation

**Prototype C against one provider before writing the remaining three adapters (#12).** Concretely: split `adapters/linear` into `fetch` (I/O, replaceable) and `normalize` (pure, stdin → typed facts), then run Layer 1 and Layer 2 unchanged. If both still pass, C is validated at the cost of one adapter's refactor. Reject B.

---

## 4. #15 — Where completion evidence comes from

### The finding

The 2026 trend is explicit and points somewhere neither #15's option list nor the PRD anticipated:

> Completion bars are becoming first-class, versioned artifacts — **acceptance-criteria files that live in the repo next to CI config**, reused across sessions and harnesses the way test suites already are.

Alongside it, a repo-local verification protocol for AI coding agents built on acceptance criteria, separate verifier roles, proof artifacts, and evidence-backed done claims.

Standard practice already separates the two concepts Repo Governor has been conflating: **acceptance criteria** are per-work-item conditions, while **definition of done** is the team-wide quality bar. Trackers carry the former badly and the latter not at all. CI carries both well.

### Why this reframes the question

#15 asked where to get acceptance conditions *from the tracker*, and answered "nowhere" — neither GitHub Projects nor Linear can supply them. The research says that is the wrong place to look. Acceptance criteria are drifting into the repository as versioned artifacts, next to the CI config that verifies them.

That decomposes cleanly onto the existing provider roles:

| Concern | Source | Role |
| --- | --- | --- |
| Is this work authorized? | tracker | `RoadmapAuthorityProvider` |
| What counts as done? | repo-local acceptance artifact | new, or an architecture-evidence variant |
| Is it done? | tests, CI status, merged PR | `RepositoryEvidenceProvider` |

The tracker is no longer asked a question it cannot answer. `STOP_COMPLETE` becomes a composition the engine performs — authority from the tracker, criteria from the repo, satisfaction from repository evidence — which is exactly what §40 describes.

It also avoids §54's roadmap-database trap, and for a non-obvious reason: acceptance criteria say *how you know it is done*, not *what is authorized*. Authority stays with the roadmap provider. Repo Governor is not becoming the roadmap by holding the completion bar, any more than a test suite is.

### Recommendation

Pursue a **variant of option 5** — not "infer completion from repo signals" heuristically, but "read a declared repo-local acceptance artifact and verify it against repository evidence." Heuristic inference would manufacture completion authority, which is the same sin as manufacturing architectural authority (§37).

Open sub-questions:
1. Is the acceptance artifact a new provider role, or an `ArchitectureEvidenceProvider` function? It is evidence about how work must be judged, which is closer to architecture than it first appears.
2. How is a criterion keyed to a work item without the tracker? Probably by authority ID, which means the file references tracker IDs — acceptable, since it does not duplicate tracker *state*.
3. What happens with no acceptance artifact? Almost certainly a non-blocking `UNKNOWN` and no `STOP_COMPLETE` — degradation, not failure. Same shape as architecture `UNKNOWN`.
4. Does this raise adoption cost enough to trip §55's friction condition? A repository that declares no criteria simply never gets `STOP_COMPLETE`, which is honest.

Needs an ADR. Blocks meaningful validation of gate 7 (#13) and interacts with ADR-014.

---

## Cross-cutting observation

Three of these four questions resolve toward the same principle: **separate the mechanism that fetches from the mechanism that judges, and let each be replaceable.**

- #17 — capabilities belong to the fetching mechanism, so they must be advertised per transport.
- #18 — the fetch may move to the agent, but the mapping must stay mechanical.
- #15 — completion criteria come from one source and their satisfaction from another; the engine composes.

The PRD reasoned carefully about *what* Repo Governor judges and consistently under-modelled *how evidence arrives*. That is the gap all four questions sit in, and it is worth expecting more of them.

---

## Sources

- [LSP Specification 3.17 — capability negotiation](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/)
- [Client–Server Communication — vscode-languageserver-node](https://deepwiki.com/microsoft/vscode-languageserver-node/2.1-client-server-communication)
- [OpenTelemetry Collector — Architecture](https://opentelemetry.io/docs/collector/architecture/)
- [OpenTelemetry Collector documentation](https://opentelemetry.io/docs/collector/)
- [Getting Structured Output From LLMs in 2026 — JSON, Tool Use, and Validation](https://projectsupply.in/blog/structured-output-llm-2026)
- [LLM StructCore: Schema-Guided Reasoning Condensation and Deterministic Compilation — arXiv:2604.20560](https://arxiv.org/pdf/2604.20560)
- [Define Done, Not Effort: Prompts That Make Agents Verify](https://www.digitalapplied.com/blog/define-done-acceptance-criteria-agent-prompts-2026)
- [Acceptance criteria vs. definition of done — TheServerSide](https://www.theserverside.com/tip/Acceptance-criteria-vs-definition-of-done-Whats-the-difference)
- [Definition of Done — Atlassian](https://www.atlassian.com/agile/project-management/definition-of-done)
- [Linear MCP server — Linear Docs](https://linear.app/docs/mcp)
