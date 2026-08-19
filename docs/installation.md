# Installing Repo Governor on a host

Repo Governor ships as an [Agent Skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) ([ADR-001](adrs/001-agent-skill-as-primary-delivery-surface.md)). There is no installer and no service — the skill is a directory, and installing it means putting that directory where your agent host looks for skills.

**Which directory that is depends on the host, and getting it wrong is silent.** A host that cannot see the skill behaves exactly like a host that saw it and decided not to use it. That distinction matters enough that the [activation protocol](research/activation-protocol.md) treats an unverified install as no measurement at all.

## Where to put it

`.agents/skills/` is read by more than one vendor and is the closest thing to a neutral location. This repository already uses the same pattern one level up: `AGENTS.md` holds the content and `CLAUDE.md` is a one-line pointer to it, because [ADR-001](adrs/001-agent-skill-as-primary-delivery-surface.md) makes tool-independence the thesis rather than a preference.

```bash
git clone https://github.com/tosin2013/repo-governor /tmp/repo-governor
/tmp/repo-governor/tools/install-skill.sh <target-repo>
```

**Use the script rather than cloning straight into the skills directory.** A plain clone puts this repository's own `AGENTS.md` inside your project, and it opens *"This repository is governed by Repo Governor"* — a true statement about Repo Governor and a false one about yours. Cursor was observed injecting that file as an always-on workspace rule from inside the skill directory of an unrelated project, which hands your agent our house rules and tells it your repository is governed by something it has not agreed to. The script clones and then removes the three paths that are correct here and wrong anywhere else; see `INSTALLED.md` in the result.

Then add whatever pointer your host needs beside it:

| Host | Reads | Status |
|---|---|---|
| **Claude Code** | `.claude/skills/<name>/SKILL.md` | **verified** — used throughout this repository's own development |
| **Cursor** | `.agents/skills/`, `.cursor/skills/`, `~/.agents/skills/`, `~/.cursor/skills/` | **verified** 2026-08-18 — `.agents/skills/repo-governor/SKILL.md` was listed by a fresh Cursor session with its description ([#38](https://github.com/tosin2013/repo-governor/issues/38)) |
| **Codex** | `.agents/skills/`, `.codex/skills/`, `~/.codex/skills/` | from vendor docs; **unverified here** |

Codex is still vendor documentation rather than knowledge; [#37](https://github.com/tosin2013/repo-governor/issues/37) is the run that settles it. Cursor was settled by [#38](https://github.com/tosin2013/repo-governor/issues/38) and the docs were right.

**`.claude/skills/` is wrong for Cursor and Codex**, which is worth stating plainly because it fails silently: the files are there, the host sees nothing, and the skill looks like it declined to activate rather than like it was never found.

For a host that only reads a vendor-specific path, point it at the one copy rather than keeping two:

```bash
mkdir -p .claude/skills
ln -s ../../.agents/skills/repo-governor .claude/skills/repo-governor
```

Two real copies drift, and a drifted skill fails in the way that is hardest to notice: it works, and it is answering from the wrong version.

## What a plain clone drags in, and why the script exists

Verified on Cursor, 2026-08-18. Asked which instruction files were applied to a workspace containing an unrelated project, it listed **six**, of which four came from installed skill copies:

```
<target>/.agents/skills/repo-governor/AGENTS.md      <- injected as an always-on rule
<target>/.agents/skills/repo-governor/CLAUDE.md      <- injected as an always-on rule
```

So on that host, installing Repo Governor by cloning applies **Repo Governor's own house rules to the user's repository**, including a first line asserting that repository is governed by us. Nobody asked for that, and it is invisible unless you think to ask the host what it loaded.

`tools/install-skill.sh` removes three paths after cloning:

| Removed | Why |
|---|---|
| `AGENTS.md` | the assertion above |
| `CLAUDE.md` | loader shim for it |
| `.claude/` | carries `github-project-release-manager`, an unrelated skill that recursive discovery offers as available — also observed on Cursor |

The engine still runs from the pruned copy; none of the removed files are read by it.

**For [measuring activation](research/activation-protocol.md) this is not merely untidy, it is fatal** — an Arm A target that has been told it is governed is Arm B. The protocol carries the test.

## Verify the host can actually see it

**Do this before concluding anything about whether the skill activates.** The install is not finished when the files are in place; it is finished when the host demonstrates it found them.

```bash
test -f .agents/skills/repo-governor/SKILL.md && echo "SKILL.md present"
head -5 .agents/skills/repo-governor/SKILL.md          # name + description frontmatter
```

Files being present is necessary and not sufficient. Then, in the host itself:

1. **Start a new session.** Skills are discovered when a session starts — Cursor documents this explicitly. A skill added mid-session is invisible until you open a new chat, and judging activation from that session measures nothing.
2. Ask the host to list the skills it can see.
3. Confirm `repo-governor` is among them, with its description.

If it is not listed, the path is wrong for that host. Fix the path before running anything that depends on the skill being available.

## Dependencies

The engine is Python stdlib only ([ADR-011](adrs/011-python-stdlib-only-engine-with-language-agnostic-adapters.md) rule 1). Adapters may carry dependencies (rule 4), and one of them matters:

| Tool | Needed for | If absent |
|---|---|---|
| `python3` | the engine | nothing works |
| `git` | provider resolution, target detection | nothing works |
| `dolt` | `decision_history` via `adapters/dolt-decisions` | **4 of 10 conformance suites fail** |
| `gh`, authenticated | the GitHub roadmap provider | live GitHub queries fail; offline suites are unaffected |

**`dolt` is the one that misleads.** Without it, `layer1`, `layer2`, `bindings` and `execution` all fail — including the portability thesis test, which reports `NOT EQUIVALENT`. That reads like a real result and is not one. The suites print a preflight line naming the missing binary, and `tools/bootstrap-decisions.sh` refuses before you reach them, but never report a red verdict from a box without `dolt`.

```bash
./tools/bootstrap-decisions.sh
for s in layer1 layer2 transport manifest onboarding vocabulary bindings skill envelope execution; do
  printf '%-12s ' "$s"; python3 conformance/$s.py >/dev/null 2>&1 && echo PASS || echo FAIL
done
```

Expect 10/10 from a fresh clone.

## Governing a repository other than this one

The skill governs the repository you are standing in, not the one it is installed from. `REPO_GOVERNOR_TARGET` overrides the detection ([ADR-027](adrs/027-the-governed-repository-is-not-the-install-directory.md)):

```bash
REPO_GOVERNOR_TARGET=/path/to/governed/repo python3 engine/completion.py <id>
```

Installing the skill into a target's `.agents/skills/` puts a full clone of this repository inside it — including this repository's `AGENTS.md`, which announces that *this* repo is governed. On a host that loads nested agent-instruction files, that statement leaks into the target. It is harmless in normal use and fatal to an Arm A activation measurement; the [activation protocol](research/activation-protocol.md) carries the check.

## Hooks — deterministic delivery (optional, [ADR-029](adrs/029-hooks-as-deterministic-delivery-surface.md))

The skill is *pulled*: the host decides whether the description matches the task. Measured on 2026-08-19, it did not — [#36](https://github.com/tosin2013/repo-governor/issues/36) Arm A prompt 1 went straight to writing code, and the field baseline is roughly **half** of skill invocations never firing. A hook is *pushed*: it runs whether or not the model thinks it is relevant.

Install it when a missed activation matters more than the extra moving part. The skill works without it.

| Host | Config file | Verified |
|---|---|---|
| Claude Code | `.claude/settings.json` (project) or `~/.claude/settings.json` | **yes** — payload schema confirmed against the official reference |
| Cursor | `.cursor/hooks.json` | events and exit codes yes; **stdin field names no** |
| Codex CLI | `.codex/hooks.json` | **no** — no Codex host has been available to this project ([#37](https://github.com/tosin2013/repo-governor/issues/37)) |

```bash
RG=/absolute/path/to/installed/skill      # the directory containing SKILL.md

# Claude Code, project-scoped:
mkdir -p .claude
sed "s#RG_SKILL_DIR#$RG#g" "$RG/tools/hooks/claude.json" > /tmp/rg-hooks.json
# merge /tmp/rg-hooks.json into .claude/settings.json -- do not overwrite an
# existing settings file, it belongs to the project

# confirm it works before trusting it
echo "{\"session_id\":\"x\",\"cwd\":\"$PWD\"}" | python3 "$RG/tools/hooks/governance-hook.py" prompt
```

The last command prints an `additionalContext` block in a governed repository and **nothing at all** in an un-onboarded one. Silence there is correct, not a failure.

### What it does, and what it will not do

| Moment | Effect |
|---|---|
| every prompt | injects the requirement to run the engine before acting |
| before `Edit`/`Write` | reports if no authority was established, if the engine refused, or if authorization is exhausted (`STOP_COMPLETE`) |
| after a Bash call | records the authority id and disposition the engine returned |

It **never decides authorization** — `engine/completion.py` remains the only thing that produces a disposition — and it makes **no claim about file scope**. Roadmap providers do not declare paths; a compiled envelope for a real GitHub issue returns `in_scope: []`, so a path check there would refuse every write with a fabricated reason. See ADR-029's *What this deliberately does not do*.

### Blocking mode

Advisory by default: the hook speaks, the agent decides. To let it actually stop a write, the **governed repository** opts in:

```json
{ "repo_governor": { "version": 1, "enforcement": "blocking" } }
```

and the config adds `--exit2-on-deny` to the `write` hook. Both are required; the flag alone does nothing. Enforcement is per repository because an un-onboarded repository is not a governed one, and blocking there would stop all editing everywhere the manifest is absent.
