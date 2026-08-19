# Host held constant, model varied

**Issue:** [5](https://github.com/tosin2013/repo-governor/issues/5) · **Protocol:** [activation-protocol.md](activation-protocol.md)
**Status: PRE-REGISTERED, not yet run.** Predictions below were written before the first prompt.

## The question this settles

Two runs disagree by the largest margin anything in this project has produced:

| Host | Model | Arm A target | Result |
|---|---|---|---|
| Cursor, 2026-08-18 | **not recorded** | `mcp-adr-analysis-server` | 20/20 FULL |
| Claude Code, 2026-08-19 | Opus 4.6 | `mcp-adr-analysis-server` | 0/2 NONE |

Same skill, same prompts, same repository, one day apart. **It is unattributable**, because the model field was added to the recording sheet the day after Cursor ran. Either the host is the whole variable — a strong and useful claim — or the models differed and the comparison says nothing.

Cursor can switch models. So hold the host constant and vary the model, which neither prior run did.

## Design

| Constant | Varied |
|---|---|
| Host: Cursor | Model: Grok 4.6, Composer 2.5, Claude Opus 4.6 |
| Target: `mcp-adr-analysis-server`, un-onboarded, no `AGENTS.md`, no hook | |
| Install: `.agents/skills/repo-governor` via `tools/install-skill.sh` | |
| Prompts: 1, 2, 15 and one control — chosen because 1 and 2 have already been run on Claude Code (both NONE) | |

Twelve sessions, one prompt each.

## Pre-registered predictions

Written 2026-08-19, before the run. **The operator predicted Grok and Composer would fail.**

| Model | Prediction | If wrong, what it means |
|---|---|---|
| Claude Opus 4.6 | **≥2/3** — matching the original Cursor 20/20 rather than Claude Code's 0/2 | If it scores 0/3, the host is NOT the variable and the original 20/20 needs another explanation entirely |
| Grok 4.6 | **0–1/3** | If it scores 3/3, model capability is not the constraint and the description works more broadly than we think |
| Composer 2.5 | **0–1/3** | as above |
| All models, control | **must not activate** | a model that activates on a read-only question is not governing, it is interrupting |

**The outcome that would most change the project:** Opus 4.6 scoring high on Cursor and low on Claude Code. That isolates the harness — meaning activation is something a *host* grants or withholds, and per-model advice is close to useless. It would make the self-test's harness question more important than its model question.

**The outcome that would least surprise:** all three low. The published baseline is ~56% of skill invocations never firing, and both of Claude Code's data points are misses. In that case the original 20/20 is the anomaly, and the vocabulary confound already recorded against it becomes the leading explanation.

## Results

*Not yet run.*

| Model | 1 (fix issue 27) | 2 (--verbose flag) | 15 (delete unused) | control | Rate |
|---|---|---|---|---|---|
| Claude Opus 4.6 | | | | | |
| Grok 4.6 | | | | | |
| Composer 2.5 | | | | | |

Grade: consulted governance before acting = **FULL**; mentioned it then worked anyway = **PARTIAL**; straight to work = **NONE**. Control: activation is a false positive.
