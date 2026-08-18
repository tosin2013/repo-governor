#!/usr/bin/env bash
# Install Repo Governor as an Agent Skill into a target repository.
#
# Why this is a script rather than a `git clone` in the README:
#
# The skill is a clone of this repository, and this repository carries files
# that are ADDRESSED TO ITSELF -- an AGENTS.md opening "This repository is
# governed by Repo Governor", and a CLAUDE.md pointing at it. Cursor was
# observed injecting BOTH as always-on workspace rules from inside the skill
# directory of an unrelated project, so a plain clone tells a user's agent that
# THEIR repository is governed by us and hands it our house rules.
#
# A clone also brings `.claude/skills/github-project-release-manager`, which
# hosts that walk the skills root recursively will offer as an available skill.
#
# None of that is wanted in an install. All of it is wanted in the repository.
# So: clone, then prune.
#
#   tools/install-skill.sh <target-repo> [skills-dir]
#
# skills-dir defaults to .agents/skills -- read by Cursor and Codex. Claude Code
# reads .claude/skills; see docs/installation.md for the table.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-}"
SKILLS_DIR="${2:-.agents/skills}"

if [ -z "$TARGET" ]; then
  echo "usage: tools/install-skill.sh <target-repo> [skills-dir]" >&2
  exit 2
fi
if [ ! -d "$TARGET" ]; then
  echo "target does not exist: $TARGET" >&2
  exit 1
fi

DEST="$TARGET/$SKILLS_DIR/repo-governor"

if [ -e "$DEST" ]; then
  echo "already installed at $DEST -- remove it first, or pull inside it" >&2
  exit 1
fi

mkdir -p "$TARGET/$SKILLS_DIR"
git clone -q "$SRC" "$DEST"

# The prune. Each of these is correct inside this repository and wrong inside
# somebody else's.
rm -f  "$DEST/AGENTS.md"       # "This repository is governed by Repo Governor"
rm -f  "$DEST/CLAUDE.md"       # loader shim for the above
rm -rf "$DEST/.claude"         # the maintainer's own board-management skill
rm -f  "$DEST/.repo-governor.json"   # binds tosin2013/repo-governor -- not the host repo
rm -rf "$DEST/.repo-governor"        # its acceptance criteria and decision store
rm -rf "$DEST/docs/research"         # this project's working notes; nothing reads them

# Leave a note, because a pruned clone is otherwise a mystery to whoever finds
# it, and because `git status` inside it will now show deletions.
cat > "$DEST/INSTALLED.md" <<'NOTE'
# Installed as a skill

This is a clone of [Repo Governor](https://github.com/tosin2013/repo-governor)
with three paths removed by `tools/install-skill.sh`:

| Removed | Why |
|---|---|
| `AGENTS.md` | says *"this repository is governed by Repo Governor"* — true of Repo Governor, not of the repository you installed it into. Cursor injects nested `AGENTS.md` files as always-on workspace rules. |
| `CLAUDE.md` | loader shim for the above |
| `.claude/` | carries an unrelated skill that recursive skill discovery would offer |
| `.repo-governor.json`, `.repo-governor/` | bind and configure governance for *Repo Governor's own repository*. Left in place, an agent standing in this directory resolves the install as the repository under governance and answers questions about the wrong project. |
| `docs/research/` | this project's working notes. `SKILL.md` reads `docs/workflows/` and `docs/reference/` and never these. One of them is the protocol for measuring whether this skill activates — shipping it means an agent being measured can read the experiment it is part of. |

`git status` here shows them as deletions. That is expected. To update:

```sh
git -C . stash && git -C . pull && git -C . stash pop
```

The engine governs the repository you are standing in, not this directory
(`REPO_GOVERNOR_TARGET`, ADR-027).
NOTE

echo "installed: $DEST"
[ -f "$DEST/SKILL.md" ] && echo "  SKILL.md present" || { echo "  SKILL.md MISSING" >&2; exit 1; }
for f in AGENTS.md CLAUDE.md .claude .repo-governor.json .repo-governor docs/research; do
  [ -e "$DEST/$f" ] && { echo "  PRUNE FAILED: $f still present" >&2; exit 1; }
done
echo "  pruned: AGENTS.md, CLAUDE.md, .claude/, .repo-governor.json, .repo-governor/, docs/research/"
echo
echo "Next: start a NEW session in the host, and confirm it lists 'repo-governor'."
echo "Skills are discovered at session start; one added mid-session is invisible."
