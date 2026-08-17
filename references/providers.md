# Providers — operational reference

Eight roles, each answering a different governance question. Normative contracts and
conformance minimums: [`docs/reference/provider-roles.md`](../docs/reference/provider-roles.md).

| Role | Question | Shipped adapter |
|---|---|---|
| `roadmap_authority` | Is this admitted and still authorized? | `file-roadmap`, `linear`, `github-projects` |
| `architecture` | What constrains how it must be built? | `adr` |
| `execution` | What is the state beneath the authority? | `execution-file` |
| `repository` | What is actually here? | `git` |
| `change_signals` | What changed outside? | `change-signals-file` |
| `retirement` | What obligations block removal? | `retirement-analysis` |
| `decision_history` | What was already decided? | built-in log |
| `acceptance_criteria` | What counts as done? | `acceptance-file` |

Keeping these apart is the point: it stops *"the task says READY"* implying *"the work is authorized"*.

## Wire protocol

```bash
$ADAPTER describe                                  # capabilities + contract version
$ADAPTER query <role> <function> [k=v ...]         # typed response on stdout
$ADAPTER query <role> <fn> ... --input -           # option C -- EXPERIMENTAL, see below
```

Any language. The engine never imports a provider SDK. How an adapter reaches its
backend — HTTP, CLI, file, MCP — is invisible to the engine (ADR-016).

**`--input -` is experimental.** It rests on [ADR-020](../docs/adrs/020-agent-supplied-transport-with-adapter-as-normalizer.md), which is `Proposed` and not accepted, and the engine never uses it — only `conformance/transport.py` does. The authority-boundary question it raises is open ([#20](https://github.com/tosin2013/repo-governor/issues/20)). Build against it only if you are prepared for the contract to change.

## Rules an adapter must honour

- **Advertise honestly.** A claimed capability must be exercisable by a probe. Unreachable transport → advertise nothing.
- **Fail typed.** An unreachable backend returns `PROVIDER_UNAVAILABLE`, never a plausible empty result.
- **Distinguish absence from unknown.** "No such item" is `NOT_FOUND`; "could not determine" is an `unknown`.
- **Cite everything.** A fact without provenance is treated as unknown, not as true.
- **Never coerce.** A value outside a closed vocabulary is `MALFORMED_SOURCE`.

Verify with `python3 conformance/layer1.py`.

## Cardinality

Single-valued: `roadmap_authority`, `execution`, `repository`, `acceptance_criteria`.
Multi-valued: `architecture`, `change_signals`, `retirement`, `decision_history`.

Two candidates for a single-valued role halt onboarding. No ranking is applied.
