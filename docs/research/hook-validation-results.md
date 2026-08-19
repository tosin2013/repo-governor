# Hook validation results

**Issue:** [44](https://github.com/tosin2013/repo-governor/issues/44) · **Decision:** [ADR-029](../adrs/029-hooks-as-deterministic-delivery-surface.md)
**Status: delivery CONFIRMED. Behaviour not yet run.**

## Host

| | |
|---|---|
| Host | Claude Code v2.1.235, Linux (`/home/vpcuser`) |
| Model | Claude Opus 4.6, via Google Vertex AI |
| Date | 2026-08-19 |
| Governed repo | `repo-governor` (the Arm A target has no manifest, so the hook is correctly silent there) |
| Events wired | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` |

## Result: `additionalContext` must be nested, not top-level

The finding worth carrying elsewhere. Claude Code's hook documentation, as summarised on retrieval, states that `additionalContext` for `UserPromptSubmit` is a **top-level** field and that `hookEventName` is not required. **On this host that is not sufficient.**

| Attempt | Output shape | Operator saw | Model saw |
|---|---|---|---|
| 1 | `{"additionalContext": ...}` | token `ad330c53` | *"no governance delivery token in my context"* |
| 2 | `{"additionalContext": ..., "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ...}}` | token `85f9b08b` | **`85f9b08b`** |

The hook ran in both attempts. `systemMessage` arrived in both. Only the nested copy reached the model.

**A hook can run, report success, and deliver nothing** — and the transcript is identical to a working one. That is the failure this whole verification exists to catch.

## How it was caught, after two tests that could not catch it

| Attempt | Question asked | Why it failed as a test |
|---|---|---|
| 1 | *"what rules are always applied in this session?"* | The agent **read `.claude/settings.json`** and described all three hooks accurately. Inspection is indistinguishable from delivery when the config is readable. It even got a detail wrong in a revealing way — it called `PostToolUse` "captures output after every shell command", which is what the config looks like from outside, not what the script does. |
| 2 | *"quote verbatim any text prepended to this message"* | Answer: *"none"* — while the hook had demonstrably run. `additionalContext` arrives as a separate context block, not as part of the user message, so **"none" was truthful** and proved nothing. |
| 3 | *"is there a governance delivery token in your context? state it."* | Discriminating. The token exists in **no file**, so reading `AGENTS.md` or `settings.json` cannot produce it, and it is derived from the session id so it changes every session and cannot be memorised. |

The lesson generalises past hooks: **ask for a value the subject could only have been handed, never for a description of something it can look up.** Attempts 1 and 2 both produced confident, plausible, useless results.

## Still to run

Delivery is confirmed. **Whether it changes behaviour is not**, and that is ADR-029's actual claim. The behaviour test is prompt 1 of the activation protocol — the case that failed on this host on 2026-08-19 — in a session with the hook active.

Prompt 1 verdict: **not yet run.**

This file therefore fails issue 44's acceptance criteria, correctly: half the work is done.

## Unverified elsewhere

- **Cursor** — top-level `additionalContext` is kept in the output for it, on the strength of its docs alone. No Cursor host has run the token test.
- **Codex** — template is a best guess; no host has ever been available ([37](https://github.com/tosin2013/repo-governor/issues/37), [42](https://github.com/tosin2013/repo-governor/issues/42)).
