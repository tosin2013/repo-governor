# Contributing

Repo Governor decides what an AI coding agent is authorized to create, change, maintain, or retire. Contributions are welcome, and the most valuable ones right now are **measurements taken on machines the maintainer does not have** — see [help wanted](https://github.com/tosin2013/repo-governor/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22).

Licensed **Apache-2.0** ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE)) — chosen partly for its explicit contribution terms, because the adapter protocol is designed to invite third-party adapters.

## The one rule that makes this repository different

**Admission is not authority.** That is the entire thesis, and this project applies it to itself.

An issue in a milestone is **admitted** — the work is wanted. It is not yet authorized to execute; assignment is what authorizes. This is not ceremony: run it yourself and see.

```bash
python3 engine/completion.py 39
# {"authority": "ADMITTED", "decision": "NO_EXECUTION_AUTHORITY", ...}
```

So: **comment on an issue before starting it.** Not to ask permission in the abstract, but because two people silently working the same admitted item is the failure this repository exists to describe. An unassigned admitted issue means nobody is on it yet.

Work that isn't on an admitted issue is a **discovery**, and the correct outcome for a discovery is that it gets captured — filed as an issue — not implemented on the spot. That applies to contributors and maintainer alike. A PR that fixes the thing it was opened for, plus four things noticed along the way, is harder to review and quietly asserts an authority nobody granted.

## Setup

See [`docs/installation.md`](docs/installation.md) for the per-host skill paths and dependencies. Short version:

```bash
git clone https://github.com/tosin2013/repo-governor && cd repo-governor
./tools/bootstrap-decisions.sh
./tools/run-conformance.sh
```

Expect **19/19**. If you see four failures, check whether `dolt` is on your PATH before reporting anything — its absence breaks `layer1`, `layer2`, `bindings` and `execution`, including the portability test, which then reports `NOT EQUIVALENT`. That reads like a real result and is not one. The suites print a preflight line naming the missing binary.

## Reporting measurements from your own repositories — read this one

Several open issues ask you to run census or activation tooling against **your** repositories and report what you find. This repository is public.

**Report numbers and shapes. Never content.**

- Counts, rates, percentages, and the *shape* of anything that failed to parse — yes.
- Issue titles, issue bodies, ADR text, assignee names, internal identifiers, repository names you would rather not publish — no.

This is §51 of the product spec (security and boundary model), and it has been violated here once already: an ADR shipped carrying a real tracker identifier until the check that would have caught it was finally run. It is now enforced mechanically on at least one issue rather than requested politely. De-identify before you paste, not after.

If a finding cannot be described without private content, say so on the issue and describe the shape. A described shape is still a usable defect report; a leak is not undoable.

## Pull requests

- **Branch and PR.** Do not push to `main`.
- **Conformance must be green**, 19/19, before you open it. If a suite fails for a reason you believe is environmental rather than a defect, say which and why in the PR body — do not silence it.
- **Never make a test pass by making it vacuous.** This has been the single most common defect in this repository's own history: a scenario that compares `{}` to `{}`, a check that counts a single provider as agreement, a permission fixture relying on a mode git does not preserve. A green suite that tests nothing is worse than a red one. If a check is hard to satisfy honestly, that is usually the check working.
- **Explain why, not what.** The diff already says what changed. Commit messages here carry the reasoning, including what was tried and rejected.

### One trap specific to this repository

**Never put a closing verb next to a `#` reference in a commit message.** GitHub's closing keywords fire anywhere in the message, and quoting does not escape them — backticks, single quotes and surrounding prose all still parse. This has closed the same issue twice by accident, the second time in the commit *documenting the first*. Write the number without the hash, or separate them: `the closing-keyword trap on issue 27`.

## What is most useful right now

| | Why |
|---|---|
| **Activation runs on a host nobody here has** | Whether the skill fires when it should is measured on three hosts at most. Gemini CLI, VS Code, Windsurf, Copilot and the rest are unknown. |
| **ADR status dialects that fail to parse** | Coverage is 92% across one person's corpus. An unparsed dialect from a corpus we cannot see is worth more than a thousand ADRs in a dialect already handled. |
| **Adapters for trackers we lack** | The protocol is a subprocess contract — `describe`, `query <role> <fn> k=v`, `write` — in any language. Adapters may carry dependencies; the engine may not. |

Read [`AGENTS.md`](AGENTS.md) before making changes. It is the instruction surface for both humans and agents working here, and it is loaded automatically by hosts that support it.
