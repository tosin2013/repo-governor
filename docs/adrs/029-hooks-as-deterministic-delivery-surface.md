# 29. Hooks as a Deterministic Delivery Surface

**Status**: Accepted (reduced), 2026-09-26, under [RATIFICATION-v0.8.0.md](RATIFICATION-v0.8.0.md). The accepted scope is the **Reduction** section below. The claim that the surface works across vendors is not accepted: it waits on calibration this project cannot run (issues 37, 42, 254). Validated 2026-08-19 by a four-condition controlled comparison, and on Refact 8.6.4 on 2026-09-26. Acceptance is a human act (§68).
**Date**: 2026-08-19
**Domain**: Distribution & agent integration
**Amends**: [ADR-001](001-agent-skill-as-primary-delivery-surface.md) — promotes "coding-agent hooks" from a deferred §65 candidate to a secondary delivery surface. The Agent Skill remains primary.
**Evidence**: [`docs/research/2026-08-19-activation-and-hooks.md`](../research/2026-08-19-activation-and-hooks.md)

## Context

ADR-001 named this failure precisely, ten months before it was observed:

> Skill activation is model-mediated: the agent decides whether the description matches the task. **A governance skill that fails to activate is worse than absent, because the human assumes it ran. This is a real failure mode with no clean fix at the skill layer.**
>
> **No enforcement.** A skill advises; it cannot block.

It then deferred hooks, correctly: in August 2025 a hook meant one vendor, and §54 makes requiring a specific vendor a failure condition.

**The prediction came true under measurement.** [#36](https://github.com/tosin2013/repo-governor/issues/36) Arm A prompt 1, Claude Code / Opus 4.6, 2026-08-19: asked to *"have a look at issue 27 and fix it"*, the agent read the issue, explored a 9,738-line file, ran a coverage baseline and began writing tests. Governance was never consulted. Minutes earlier the same agent had listed the skill among its always-applied rules, paraphrasing the `description` accurately.

**So the description was present, was understood, and lost anyway.** That is a precedence failure, not a discovery failure, and no rewording of `SKILL.md` reaches it.

Two research findings decide the rest:

1. **This is the industry norm, not a defect in our description.** Vercel measured skills uninvoked in **56%** of cases where the agent had access; an independent study found **46% recall**; 56,804 indexed skills compete for fewer than 100 reliable auto-trigger slots. The @skills protocol paper calls installation-based triggering *"a lottery in which N descriptions must each win a probabilistic match at once."* Description tuning has a ceiling, and we are near it.

2. **The vendor-bet objection has expired.** All three target hosts now ship hooks — `.claude/settings.json`, `.cursor/hooks.json`, `.codex/hooks.json` — with a converged calling convention: JSON on stdin, exit 2 blocks, JSON on stdout carries a structured decision. This is the same argument ADR-001 used to promote Agent Skills: adopt a cross-vendor convention rather than build N integrations.

## Decision

**Repo Governor ships a hook surface as a secondary delivery mechanism. The Agent Skill remains primary.** One shared script, `tools/hooks/governance-hook.py`, with a thin JSON config per host.

The hook occupies three moments:

| Moment | Event (Claude / Cursor) | What it does |
|---|---|---|
| `prompt` | `UserPromptSubmit` / `beforeSubmitPrompt` | injects the governance **requirement** before the agent reasons |
| `write` | `PreToolUse` / `preToolUse` on `Edit\|Write` | checks a pending change against what the engine established |
| `capture` | `PostToolUse` on Bash / `afterShellExecution` | records the authority and disposition a session obtained |

**Four constraints, each load-bearing.**

**1. The hook never decides authorization.** `engine/completion.py` remains the only thing that produces a disposition (ADR-002). The hook routes and reports; it does not compute. It also never infers an authority id from prompt text — that would be a second authority surface, which ADR-022 forbids.

**2. The `prompt` moment delivers the requirement, not a verdict.** It cannot produce one: `completion.py` requires an authority id and a raw user prompt has none. What it makes deterministic is that the requirement *arrives*. This is the fix for an activation miss, and it must land at prompt time rather than at write time — by the time `PreToolUse` fires, the agent has already chosen an approach.

**3. Enforcement is opt-in per repository, via `repo_governor.enforcement: "blocking"`.** Default is `advisory`. An un-onboarded repository is not a governed one; blocking there would stop all editing everywhere the manifest is absent.

**4. Silence in ungoverned repositories.** No manifest, no output. A governance tool that narrates in repositories it has no authority over is a nuisance that gets uninstalled.

## Measured consequences (2026-08-19, added after validation)

This ADR was written to fix an activation miss. **Validation refuted that.**

| Test | Result |
|---|---|
| Does the hook fire and reach the model? | **yes** — token matched operator and model, but only after nesting `additionalContext` inside `hookSpecificOutput`. Top-level alone runs, reports success, and delivers nothing. |
| Prompt-1 shape, hook **on**, in `repo-governor` | FULL |
| Prompt-1 shape, hook **off**, same repo, same prompt | **FULL** |

`AGENTS.md` was doing the work. The agent named it as its source in every session. **In a repository that already announces itself, the hook adds nothing to activation.**

Worse for the original motivation: the hook is deliberately silent in un-onboarded repositories, and prompt 1 failed in an un-onboarded repository. **The surface could never have spoken in the case that prompted it.** The only row where it improves activation is a governed repository with no `AGENTS.md` — which one file would also fix.

**Resolved by a controlled comparison**, same repository and prompt, one variable at a time:

| `AGENTS.md` | prompt hook | write hook | Result |
|---|---|---|---|
| present | on | on | refuses |
| absent | on | on | refuses, quoting text found only in the injection |
| absent | **off** | off | **edits immediately** |
| absent | off | **on** | attempts the edit, **blocked by exit 2** |

- Activation: the hook adds nothing where `AGENTS.md` exists, and **governs on its own where it does not** (row 2 vs row 3). Row 3 also shows the skill description alone does not activate in a governed repository — the un-onboarded confound behind Arm A prompt 1's NONE is removed.
- Enforcement: **proven** (row 4). A write was prevented by mechanism rather than persuasion, which is what ADR-001 said the skill layer could not do.
- Reachability: blocking only engages when advisory delivery is absent. Where injection works the agent stops first, so **enforcement is a backstop against a non-compliant agent, not part of the normal path**.

**The hook is not a security boundary.** The remedy is captured as [issue 46](https://github.com/tosin2013/repo-governor/issues/46) — the CI surface ADR-001 deferred — gated on a *declared* PR-to-authority signal, because guessing one would reproduce in a new surface the defect [ADR-018](018-admission-signal-is-declared-not-assumed.md) exists to prevent.

**Restated:** Offered options after being blocked, the agent proposed *"remove it from `.claude/settings.json`"* unprompted, within one turn. It has file access and the config is a file. This stops mistakes — which is the common case, and it did so here — but containment requires somewhere the agent cannot reach: CI, branch protection, or review.

Full record: [`docs/research/hook-validation-results.md`](../research/hook-validation-results.md). Candidates that depend on the enforcement test are captured in [issue 45](https://github.com/tosin2013/repo-governor/issues/45), **unmilestoned**, so the engine returns the disposition `UNKNOWN` with a blocking unknown whose reason is `NOT_ADMITTED` — `NOT_ADMITTED` is a reason code, not a disposition, and does not appear in `DISPOSITIONS` — if enforcement fails, this surface should be deleted rather than kept as a plausible-sounding option, and issue 45 goes with it.

## Consequences

**Positive**

- Delivery becomes deterministic where it was probabilistic. Obedience remains model-mediated — the hook closes the activation gap, not the compliance gap.
- The completion firewall (ADR-023) gains a real chokepoint: a write attempted under `STOP_COMPLETE` is surfaced before it happens, which is §40's hardest case.
- Enforcement, where a repository opts into it, is the first thing in this project that can actually stop an agent rather than advise it.
- Cross-vendor by the same reasoning that made the skill cross-vendor. One script, three config files.

**Negative**

- **Hooks are host-level, not repository-level.** A cloned repository does not carry its own enforcement; the operator must install the hook on each machine. This narrows the gap ADR-001 named without closing it, and it is the strongest remaining argument for the deferred CI surface.
- **Only the Claude Code payload schema is verified.** Cursor's event names and exit semantics are confirmed from its docs; its stdin field names are not. The Codex template is a best guess — no Codex host has ever been available to this project ([#37](https://github.com/tosin2013/repo-governor/issues/37), [#42](https://github.com/tosin2013/repo-governor/issues/42)). Both templates say so in their own `$comment`.
- **A fourth surface to keep consistent.** `SKILL.md`, `AGENTS.md`, the engine and now the hook can drift apart. `conformance/hooks.py` is the mitigation and is mutation-tested.
- **Session state on disk.** `.repo-governor/sessions/` is per-machine, per-conversation, and gitignored. It is a cache, not evidence; the decision log (ADR-009/ADR-019) remains the record.

**Neutral**

- Reversible. Deleting the config files removes the surface; the skill and engine are untouched.

## Amendment — Refact as a host (2026-09-26, [issue 247](https://github.com/tosin2013/repo-governor/issues/247))

Refact ([JegernOUTT/refact](https://github.com/JegernOUTT/refact), which continues the archived `smallcloudai/refact`) ships the converged convention: `PreToolUse`/`PostToolUse`, JSON on stdin, exit 2 blocks. That makes it a host, not a provider. It is added the same way as the others, with one template (`tools/hooks/refact.json`, installed as `.refact/hooks.yaml`) and no new code path. Its source was read at commit `0d096c9`. Blocking was then tested on a running host, Refact 8.6.4, on 2026-09-26 (PR 249, and the [Refact runbook](../runbooks/refact-integration.md)). The delivery-token check cannot run there, because Refact discards hook output. It departs from the other hosts in ways that change what this ADR's moments can do there:

- **Stdout is discarded on every event.** The `prompt` moment cannot deliver, so it is not installed. Advisory mode is silence, so the Refact template is the only one that carries `--exit2-on-deny` by default. The manifest's `enforcement` stays the single switch.
- **It fell open before this amendment, silently.** The payload names the repository `project_dir` and the hook runs in the daemon's working directory. Tool output arrives as `tool_output`. File changes go through `*_textdoc`, `mv`, `rm` and three merge tools. Each of these alone made the hook find no manifest, record a null verdict, or treat the tool as unknown. All four are fixed in the shared script and pinned by `conformance/hooks.py`.
- **It reads `.claude/settings.json` but drops the `args` array**, so a repository governed for Claude Code looks governed under Refact and is not. The installation docs say so.

The adapter half of issue 247 (Refact's `.refact/` task board as execution state) is not decided here.

## Reduction (2026-09-26, under ADR-035)

ADR-035 rule 5: this ADR had been a runtime dependency of eleven releases while `Proposed`. The maintainer chose to **reduce** it to what its evidence supports and accept that part.

**Accepted:**

1. Repo Governor ships a hook surface as a **secondary** delivery mechanism. The Agent Skill stays primary.
2. The four constraints in the Decision: the hook never decides; the prompt moment delivers a requirement, not a verdict; enforcement is opt-in per repository; silence where the repository is not governed.
3. Blocking (`enforcement: "blocking"` plus exit 2) is a **backstop** against a non-compliant agent. It is not a security boundary (see Measured consequences).
4. **Verified hosts:** Claude Code (prompt, write and capture moments) and Refact (write and capture moments, in a single agent chat; not for subagents, [JegernOUTT/refact#35](https://github.com/JegernOUTT/refact/issues/35), issue 254).
5. The prompt moment improves activation only where the repository has no `AGENTS.md`.
6. Templates for other hosts ship **labelled unverified** and claim nothing beyond their label.

**Not accepted:** the claim that one script with a thin config per host governs every host. For Cursor, Codex, Gemini CLI and VS Code the templates exist and have not run on a real host. That claim waits for per-host calibration, which is external evidence (issues 37 and 42). A host joins the verified list in item 4 when it has a calibration record, without a new ADR.

## Acceptance conditions

For the reduced scope above. **All met.**

1. **Enforcement stops a write on a real host.** *(Met: Claude Code, 2026-08-19, [hook-validation-results.md](../research/hook-validation-results.md); Refact 8.6.4, 2026-09-26, PR 249.)*
2. **The four constraints are held by a suite.** *(Met: `conformance/hooks.py`, mutation-tested; live `hooks` suite green in CI.)*
3. **Delivery to the model is proven where the prompt moment is claimed.** *(Met for Claude Code: the delivery token matched on both sides, 2026-08-19. Not claimed for Refact, which discards hook output.)*
4. **Unverified templates say so.** *(Met: each template's `$comment` and `docs/installation.md` mark them unverified, and the installer warns.)*

## What this deliberately does not do

**Scope enforcement by file path was designed, built, and removed.** `engine/envelope.py` can classify a target against `in_scope`/`non_goals`, so checking a pending write against the compiled envelope looked correct. Compiling a real envelope for a real GitHub issue returns:

```
in_scope: []    non_goals: []    required_outcome: null
```

GitHub issues declare no structured file scope. Every path would classify as *"outside declared in_scope"* — a confident refusal with a fabricated reason, on every write. In blocking mode it would have blocked all editing while stating something untrue.

**A governance tool that refuses confidently for the wrong reason is worse than one that stays quiet.** Path-level scope needs providers that declare paths; it is not available from the roadmap providers bound today, and asserting it would be exactly the "information acquires authority by existing" error the whole project refuses. `conformance/hooks.py` now asserts the hook makes no scope claim.

## Related Specification Sections

§54 Failure Conditions · §63 MVP Requirements · §64 MVP Non-Commitments · §65 Future Candidate Capabilities · §40 Completion

## Domain References

- [Hooks reference — Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [Hooks — Cursor Docs](https://cursor.com/docs/hooks)
- [@skills: Attention Is All You Have (arXiv 2608.12610)](https://arxiv.org/abs/2608.12610)
- [`docs/research/2026-08-19-activation-and-hooks.md`](../research/2026-08-19-activation-and-hooks.md)

---

_`§NN` and `INV-NNN` citations above resolve against [`docs/reference/`](../reference/) — see its [section map](../reference/README.md#section-map)._
