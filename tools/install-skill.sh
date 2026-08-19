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
HOOKS_OPT="${3:-ask}"     # ask | yes | no -- see the hook block at the end

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

# Activation advice, tailored to what is actually in the target. Deliberately
# ADVICE and not configuration: this script never writes to the user's
# settings.json. It prunes AGENTS.md and CLAUDE.md from every install precisely
# because shipping our house rules into someone else's repository is wrong, and
# writing executable hook config into a file they own is that same error with
# higher stakes. See ADR-029 and docs/research/hook-validation-results.md.
echo
if [ -f "$TARGET/AGENTS.md" ] || [ -f "$TARGET/CLAUDE.md" ]; then
  echo "This repository has AGENTS.md/CLAUDE.md. Governance should activate from it."
  echo "Measured: with such a file present, adding a hook changed nothing (ADR-029)."
else
  echo "WARNING: this repository has no AGENTS.md or CLAUDE.md."
  echo
  echo "  The skill description ALONE did not activate governance under measurement:"
  echo "  an agent asked to add a CLI flag went straight to editing source, and a"
  echo "  controlled run in a governed repository did the same. Installing this skill"
  echo "  and stopping here is likely to leave governance unused while looking present."
  echo
  echo "  Fix it with EITHER (an AGENTS.md is simpler and vendor-neutral):"
  echo "    1. an AGENTS.md saying the repository is governed and how to run the engine"
  echo "    2. the hook surface -- see docs/installation.md, section 'Hooks'"
fi

# --- the hook offer -------------------------------------------------------
# Consent-gated, never default-on. Writing hook config into a settings.json the
# user owns is fine when they said yes and wrong when they did not; the rule is
# no SILENT write, not no write. Same shape as SKILL.md's --write.
case "$SKILLS_DIR" in
  *.claude*) HOST_IS_CLAUDE=1 ;;
  *)         HOST_IS_CLAUDE=0 ;;
esac

if [ "$HOST_IS_CLAUDE" = "1" ] && [ "$HOOKS_OPT" != "no" ]; then
  echo
  if [ ! -f "$TARGET/.repo-governor.json" ]; then
    echo "NOTE: the hook would be SILENT here -- $TARGET has no .repo-governor.json."
    echo "      The hook only speaks in a governed repository. Onboarding this one"
    echo "      makes it no longer silent about governance, which ends any activation"
    echo "      measurement in progress against it (docs/research/activation-protocol.md)."
    echo "      Not offering to install it."
    echo
    # Detection is the tedious half of onboarding and it is safe to automate:
    # it reads the filesystem, cites evidence, probes nothing, and produces a
    # PROPOSAL. Binding stays a human act -- the manifest declares which
    # provider is the roadmap authority and what signal means admission, and
    # guessing that is how a second roadmap of record gets created (ADR-022).
    # onboard.py's own docstring: the engine never reads the proposal, which
    # is why silent binding is unimplementable rather than merely forbidden.
    if [ "$HOOKS_OPT" = "yes" ] || { [ "$HOOKS_OPT" = "ask" ] && [ -t 0 ]; }; then
      echo "Onboarding detection can propose a manifest for you. It reads the"
      echo "filesystem only, contacts nothing, and writes .repo-governor.proposed.json"
      echo "-- a PROPOSAL. You review it, declare the admission signal, and rename it."
      echo
      echo "CAUTION: that file lands in the repository root and is itself a governance"
      echo "signal. Do not run it against a repository under activation measurement."
      REPLY_O="n"
      if [ "$HOOKS_OPT" = "yes" ]; then REPLY_O="n"      # never automatic; ask means ask
      else printf "Run onboarding detection now? [y/N] "; read -r REPLY_O || REPLY_O="n"
      fi
      case "$REPLY_O" in
        [yY]*)
          python3 "$DEST/engine/onboard.py" "$TARGET" --write || true
          echo
          echo "  Review .repo-governor.proposed.json, set the admission signal, then:"
          echo "    mv $TARGET/.repo-governor.proposed.json $TARGET/.repo-governor.json"
          echo "  Nothing governs until you do -- the engine never reads the proposal."
          ;;
        *) echo "  Skipped. Run it later: python3 $DEST/engine/onboard.py $TARGET --write" ;;
      esac
    fi
  else
    REPLY_H="n"
    if [ "$HOOKS_OPT" = "yes" ]; then
      REPLY_H="y"
    elif [ -t 0 ]; then
      printf "Enable the governance hook for Claude Code in %s? [y/N] " "$TARGET"
      read -r REPLY_H || REPLY_H="n"
    else
      echo "Hook not installed (non-interactive). Re-run with 'yes' as the 3rd argument to install it."
    fi
    case "$REPLY_H" in
      [yY]*)
        RG_ABS="$(cd "$DEST" && pwd)"
        python3 - "$TARGET" "$RG_ABS" <<'PYHOOK'
import json, pathlib, sys
target, rg = pathlib.Path(sys.argv[1]), sys.argv[2]
h = f"{rg}/tools/hooks/governance-hook.py"
cfg = {
  "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3",
      "args": [h, "prompt"], "timeout": 20, "statusMessage": "Checking governance..."}]}],
  "PreToolUse": [{"matcher": "Edit|Write|NotebookEdit", "hooks": [{"type": "command",
      "command": "python3", "args": [h, "write"], "timeout": 20}]}],
  "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3",
      "args": [h, "capture"], "timeout": 20}]}],
}
p = target / ".claude" / "settings.json"
cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
kept = [k for k in cfg if k in cur.get("hooks", {})]
cur.setdefault("hooks", {}).update(cfg)          # merge; never replace the file
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
print(f"  hook installed -> {p}")
if kept:
    print(f"  NOTE: replaced your existing {', '.join(kept)} entries -- check them")
print("  advisory only. Blocking needs repo_governor.enforcement='blocking' in the")
print("  manifest AND --exit2-on-deny on the write hook; neither was added.")
PYHOOK
        ;;
      *) echo "  Hook not installed. See docs/installation.md if you change your mind." ;;
    esac
  fi
fi
