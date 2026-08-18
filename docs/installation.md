# Installing Repo Governor on a host

Repo Governor ships as an [Agent Skill](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) ([ADR-001](adrs/001-agent-skill-as-primary-delivery-surface.md)). There is no installer and no service — the skill is a directory, and installing it means putting that directory where your agent host looks for skills.

**Which directory that is depends on the host, and getting it wrong is silent.** A host that cannot see the skill behaves exactly like a host that saw it and decided not to use it. That distinction matters enough that the [activation protocol](research/activation-protocol.md) treats an unverified install as no measurement at all.

## Where to put it

`.agents/skills/` is read by more than one vendor and is the closest thing to a neutral location. This repository already uses the same pattern one level up: `AGENTS.md` holds the content and `CLAUDE.md` is a one-line pointer to it, because [ADR-001](adrs/001-agent-skill-as-primary-delivery-surface.md) makes tool-independence the thesis rather than a preference.

```bash
git clone https://github.com/tosin2013/repo-governor .agents/skills/repo-governor
```

Then add whatever pointer your host needs beside it:

| Host | Reads | Status |
|---|---|---|
| **Claude Code** | `.claude/skills/<name>/SKILL.md` | **verified** — used throughout this repository's own development |
| **Cursor** | `.agents/skills/`, `.cursor/skills/`, `~/.agents/skills/`, `~/.cursor/skills/` | from vendor docs; **unverified here** |
| **Codex** | `.agents/skills/`, `.codex/skills/`, `~/.codex/skills/` | from vendor docs; **unverified here** |

Only the Claude Code row is something this project has run. The other two are what the vendors document, and [#37](https://github.com/tosin2013/repo-governor/issues/37) and [#38](https://github.com/tosin2013/repo-governor/issues/38) are the runs that will replace "documented" with "verified" — or find that the docs are wrong, which is the more useful outcome.

For a host that only reads a vendor-specific path, point it at the one copy rather than keeping two:

```bash
mkdir -p .claude/skills
ln -s ../../.agents/skills/repo-governor .claude/skills/repo-governor
```

Two real copies drift, and a drifted skill fails in the way that is hardest to notice: it works, and it is answering from the wrong version.

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
