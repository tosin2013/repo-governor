# Skill activation reliability, and whether hooks are still a vendor bet

**Date:** 2026-08-19 · **Prompted by:** [#36](https://github.com/tosin2013/repo-governor/issues/36) Arm A prompt 1
**Consumed by:** [ADR-029](../adrs/029-hooks-as-deterministic-delivery-surface.md), which amends [ADR-001](../adrs/001-agent-skill-as-primary-delivery-surface.md)

Same role as [`2026-08-17-external-landscape.md`](2026-08-17-external-landscape.md), which ADR-001 was built on: establish what is true outside this repository before deciding anything inside it.

## Why this was run

Arm A prompt 1 on Claude Code (Opus 4.6) graded **NONE**. The agent was asked to *"have a look at issue 27 and fix it"*, and read the issue, explored a 9,738-line source file, ran a coverage baseline, and began writing tests. Governance was never consulted.

Minutes earlier the same agent, asked what rules were always applied, had answered with an accurate paraphrase of the skill's `description`. **The description was present and understood, and lost anyway.** That is a precedence failure, not a discovery failure, and no rewording of `SKILL.md` addresses it.

Two questions followed, and neither could be answered from inside this repository:

1. Is a ~0% activation rate normal, or is this repository's skill unusually bad at announcing itself?
2. Hooks were deferred by ADR-001 as a vendor bet. Is that still true?

## Finding 1 — roughly half of skill invocations do not fire, industry-wide

| Measurement | Source |
|---|---|
| Skills **uninvoked in 56%** of cases where the agent had access | Vercel benchmark, January 2026 |
| **46% recall** on skill invocation, independently | reported alongside the above |
| Benchmarks exercise only **38.66–45.51%** of a skill's documented behaviour constraints | [Skill Coverage: A Test Adequacy Metric for Agent Skills](https://arxiv.org/abs/2606.20659) |
| **56,804** indexed skills compete for **fewer than 100** reliable auto-trigger slots per agent | [The Agent Skills Ecosystem in 2026](https://agentman.ai/blog/agent-skills-ecosystem-report-2026) |
| Curated skills lift pass rate 33.9% -> 50.5%, but **drop it on 16 of 84 tasks** | [SkillsBench](https://arxiv.org/abs/2602.12670) |

The ecosystem report also states the failure mode in almost the same words ADR-001 used ten months earlier:

> When a skill sits in a hidden directory and is supposed to fire on its own, if it fails to fire, nothing says so -- and users cannot invoke it by name either, because they no longer remember it is there.

**Prompt 1's NONE is the field norm.** It is not evidence that this skill's description is defective.

## Finding 2 — the problem is structural, and the literature has not measured it

[@skills: Attention Is All You Have](https://arxiv.org/abs/2608.12610) (August 2026) proposes an open skills protocol built on the premise that installation-based auto-triggering cannot be made reliable:

> a lottery in which N descriptions must each win a probabilistic match at once, with the odds compounding against exactly the multi-skill workflows real work is made of

Its remedy is to abandon implicit triggering: skills are referenced explicitly by path (`@skills:<path>`), and only those listed in an `.autotrigger` file fire unprompted. **Explicit invocation plus an opt-in allowlist** -- which is, structurally, the operator's own observation that this skill appears to work only when called by slash command.

The paper is candid about what it did not do:

> Our central quantity, the number of reliable auto-trigger slots, is bounded by argument and by the literature rather than measured by us.

**So the activation rate is unmeasured in the published literature.** The two-arm protocol in [`activation-protocol.md`](activation-protocol.md) measures exactly that quantity, per host, with per-prompt grading. That is a contribution the field does not currently have.

## Finding 3 — this reframes the Cursor result as the anomaly

Cursor's Arm A scored **20/20 FULL** against a field baseline near 50%. A perfect score is out of family and needs an explanation rather than a victory lap.

The most likely one is already recorded in `cd857ae`: the Arm A target, `mcp-adr-analysis-server`, is a repository *about* architectural governance, and its README uses "governance" three times. Subject and skill share vocabulary. Under a description-matching mechanism that is a large thumb on the scale, and it plausibly accounts for most of the difference between 20/20 and the published ~50%.

**This is now the single most valuable open question in [#5](https://github.com/tosin2013/repo-governor/issues/5)**, and it is answered by one cheap experiment: the same 20 prompts against an Arm A target whose README never says "governance".

## Finding 4 — hooks are no longer a vendor bet

This is the finding that changes a decision.

ADR-001 deferred "coding-agent hooks" because §54 makes requiring a specific vendor a failure condition, and in August 2025 a hook meant one vendor. As of 2026 all three target hosts ship a hook system, with converged semantics:

| Host | Config file | Fires on user prompt | Fires before a write |
|---|---|---|---|
| Claude Code | `.claude/settings.json` | `UserPromptSubmit` | `PreToolUse` |
| Cursor | `.cursor/hooks.json` | `beforeSubmitPrompt` | `preToolUse` |
| Codex CLI | `.codex/hooks.json` | (hooks.json, shipped early 2026) | yes |

The calling convention converged too -- **JSON on stdin, exit 2 blocks, JSON on stdout carries a structured decision** -- described across sources as the de facto standard, originating with Claude Code and adopted by the others.

Claude Code specifics, confirmed against [the official reference](https://code.claude.com/docs/en/hooks):

- `PreToolUse` -- `matcher` accepts `"Edit|Write"`; exit 2 blocks unconditionally and stderr becomes the reason shown to the model. Exit 0 with `hookSpecificOutput.permissionDecision` of `allow|deny|ask` is the non-blocking structured path.
- `UserPromptSubmit` -- no matcher, always fires, runs **before the model processes the prompt**; stdout on exit 0 is injected as context. Exit 2 rejects the prompt.
- `SessionStart` -- injects context at session open; cannot block.
- `additionalContext` and `systemMessage` are available on both prompt-time events.

Cursor's `beforeSubmitPrompt` and `preToolUse` mirror these, with `"permission": "allow"|"deny"|"ask"` and the same exit-2 convention.

**The argument ADR-001 used to promote Agent Skills now applies to hooks**: adopt a cross-vendor convention rather than build N integrations. The objection has expired on its own terms. What remains vendor-specific is a small JSON config file per host over one shared script -- the same shape as the per-host skill directories already documented in [`installation.md`](../installation.md).

## What this does not settle

- **Hooks are host-level, not repository-level.** A hook protects a machine that installed it. A cloned repository does not carry its own enforcement, so this narrows the gap ADR-001 named without closing it.
- **A hook cannot produce a verdict on its own.** `engine/completion.py` requires an authority id; a raw user prompt has none. What a prompt-time hook can deliver deterministically is the *requirement*, not the answer.
- **Un-onboarded repositories.** A repository with no manifest yields `AUTHORITY_SOURCE_MISSING` -- an **onboarding** disposition, from a separate alphabet that `vocabulary.py` says never appears in a governance decision. Enforcement keyed off it would block all editing in any repository that has not onboarded. Enforcement must therefore be opt-in per repository.

## Sources

- [Hooks reference — Claude Code Docs](https://code.claude.com/docs/en/hooks)
- [Hooks — Cursor Docs](https://cursor.com/docs/hooks)
- [@skills: Attention Is All You Have (arXiv 2608.12610)](https://arxiv.org/abs/2608.12610)
- [The Agent Skills Ecosystem in 2026](https://agentman.ai/blog/agent-skills-ecosystem-report-2026)
- [SkillsBench (arXiv 2602.12670)](https://arxiv.org/abs/2602.12670)
- [Skill Coverage: A Test Adequacy Metric for Agent Skills (arXiv 2606.20659)](https://arxiv.org/abs/2606.20659)
- [Agent Skills Can Be Harmful: An Empirical Study of Skill-Induced Failures (arXiv 2608.11888)](https://arxiv.org/abs/2608.11888)
