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
#   tools/install-skill.sh <target-repo> [skills-dir] [ask|yes|no] [harness]
#   tools/install-skill.sh --prune <installed-copy>
#
# skills-dir defaults to .agents/skills -- read by Cursor and Codex. Claude Code
# reads .claude/skills; see docs/installation.md for the table.
#
# The second form is the upgrade path (issue 258). The documented install
# clones a TAG into a temporary directory and runs this script from there, so
# the installed copy is a detached HEAD whose `origin` was that temporary
# clone. The update line INSTALLED.md used to carry (`stash && pull && stash
# pop`) failed on the detached HEAD, and failed again once the temporary clone
# was gone. Now the copy's `origin` is the canonical repository, INSTALLED.md
# records what was actually installed, and an upgrade is fetch, checkout of a
# tag, then `--prune` from the version just checked out -- so the prune list
# below stays the only one, and a newer version prunes with its own list.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Where an installed copy fetches upgrades from. A constant, not a guess: the
# temporary clone the install ran from is deleted afterwards and cannot be it.
UPSTREAM_URL="https://github.com/tosin2013/repo-governor"

# The prune. Each of these is correct inside this repository and wrong inside
# somebody else's. Used by the install and by `--prune`, so there is one list.
prune_copy() {
rm -f  "$DEST/AGENTS.md"       # "This repository is governed by Repo Governor"
rm -f  "$DEST/CLAUDE.md"       # loader shim for the above
rm -rf "$DEST/.claude"         # the maintainer's own board-management skill
rm -f  "$DEST/.repo-governor.json"   # binds tosin2013/repo-governor -- not the host repo
rm -rf "$DEST/.repo-governor"        # its acceptance criteria and decision store
rm -rf "$DEST/docs/research"         # this project's working notes; nothing reads them
rm -f  "$DEST/CONTRIBUTING.md"       # Repo Governor's contribution rules, not yours
rm -rf "$DEST/.claude-plugin"        # Claude Code marketplace entry (ADR-034): it
                                     # publishes THIS repository by tag, so in a copy
                                     # it points at the wrong tree -- ADR-034 rule 1's
                                     # "no second copy" arriving via the install door
}

# Leave a note, because a pruned clone is otherwise a mystery to whoever finds
# it, and because `git status` inside it will now show deletions.
write_note() {
cat > "$DEST/INSTALLED.md" <<'NOTE'
# Installed as a skill

This is a clone of [Repo Governor](https://github.com/tosin2013/repo-governor)
with the paths below removed by `tools/install-skill.sh`:

| Removed | Why |
|---|---|
| `AGENTS.md` | says *"this repository is governed by Repo Governor"* — true of Repo Governor, not of the repository you installed it into. Cursor injects nested `AGENTS.md` files as always-on workspace rules. |
| `CLAUDE.md` | loader shim for the above |
| `.claude/` | carries an unrelated skill that recursive skill discovery would offer |
| `.repo-governor.json`, `.repo-governor/` | bind and configure governance for *Repo Governor's own repository*. Left in place, an agent standing in this directory resolves the install as the repository under governance and answers questions about the wrong project. |
| `CONTRIBUTING.md` | Repo Governor's contribution rules — its conformance suites, its branch policy, its PR template. True of Repo Governor, false of the repository you installed it into, and grepping for contribution rules would otherwise turn up two files describing different projects. To contribute an adapter, see https://github.com/tosin2013/repo-governor/blob/main/CONTRIBUTING.md |
| `docs/research/` | this project's working notes. `SKILL.md` reads `docs/workflows/` and `docs/reference/` and never these. One of them is the protocol for measuring whether this skill activates — shipping it means an agent being measured can read the experiment it is part of. |
| `.claude-plugin/` | the Claude Code marketplace entry (ADR-034). It publishes *this* repository as a plugin pinned to a tag; inside a copy it names the wrong tree, which is ADR-034 rule 1's "no second copy" arriving through the install door. |

`git status` here shows them as deletions. That is expected.
NOTE

# What is installed, read from the copy itself. A tag is named only when HEAD
# is exactly at one; otherwise the commit is all that is claimed (ADR-028).
local commit tag
commit="$(git -C "$DEST" rev-parse HEAD)"
tag="$(git -C "$DEST" describe --tags --exact-match HEAD 2>/dev/null || true)"
{
  echo
  echo "## What is installed"
  echo
  if [ -n "$tag" ]; then
    echo "- Installed tag: \`$tag\`"
  else
    echo "- Installed tag: none. HEAD is not exactly at a tag, so no tag is claimed."
  fi
  echo "- Installed commit: \`$commit\`"
  echo
  cat <<'NOTE'
## To upgrade

Run these from this directory. Replace `vX.Y.Z` with the release tag you want:

```sh
git fetch --tags origin
git checkout --force vX.Y.Z
bash tools/install-skill.sh --prune .
```

`--force` discards local changes in this copy, and the prune is one of them.
The third command applies the prune list of the version you checked out and
rewrites this file. Hook configuration in the host repository is not touched:
it names this directory, and this directory does not move.

`origin` is https://github.com/tosin2013/repo-governor. A copy installed
before this note carried an upgrade section has a temporary directory as its
`origin`; run `git remote set-url origin https://github.com/tosin2013/repo-governor`
once, first.

To remove the skill and its hook configuration, see
https://github.com/tosin2013/repo-governor/blob/main/docs/runbooks/upgrade-and-uninstall.md

The engine governs the repository you are standing in, not this directory
(`REPO_GOVERNOR_TARGET`, ADR-027).
NOTE
} >> "$DEST/INSTALLED.md"
}

verify_prune() {
[ -f "$DEST/SKILL.md" ] && echo "  SKILL.md present" || { echo "  SKILL.md MISSING" >&2; exit 1; }
for f in AGENTS.md CLAUDE.md .claude .claude-plugin .repo-governor.json .repo-governor docs/research CONTRIBUTING.md; do
  [ -e "$DEST/$f" ] && { echo "  PRUNE FAILED: $f still present" >&2; exit 1; }
done
echo "  pruned: AGENTS.md, CLAUDE.md, .claude/, .claude-plugin/, .repo-governor.json, .repo-governor/, docs/research/, CONTRIBUTING.md"

# LICENSE and NOTICE must SURVIVE. Apache-2.0 section 4(a) requires recipients
# get a copy of the License and 4(d) requires the NOTICE travel with it, so the
# prune list is exactly the place a licence obligation could be dropped by
# accident. Assert the opposite of a prune, right beside the prune.
for f in LICENSE NOTICE; do
  [ -e "$DEST/$f" ] || { echo "  $f MISSING from the install -- Apache-2.0 requires it travel" >&2; exit 1; }
done
echo "  kept: LICENSE, NOTICE (Apache-2.0 sections 4a and 4d)"
}

# --- upgrade: re-prune a copy after `git checkout --force <tag>` ------------
# Refuses anything without an INSTALLED.md. Every install writes one, and this
# repository's own checkout has none, so a mistyped path cannot prune the
# source tree of its AGENTS.md.
if [ "${1:-}" = "--prune" ]; then
  DEST="${2:-}"
  if [ -z "$DEST" ] || [ ! -d "$DEST" ]; then
    echo "usage: tools/install-skill.sh --prune <installed-copy>" >&2
    exit 2
  fi
  DEST="$(cd "$DEST" && pwd)"
  if [ ! -f "$DEST/INSTALLED.md" ] || ! git -C "$DEST" rev-parse --git-dir >/dev/null 2>&1; then
    echo "not an installed copy: $DEST (no INSTALLED.md, or not a git clone)" >&2
    exit 1
  fi
  prune_copy
  write_note
  echo "re-pruned: $DEST"
  verify_prune
  grep '^- Installed' "$DEST/INSTALLED.md" | sed 's/^/  /'
  exit 0
fi

TARGET="${1:-}"
SKILLS_DIR="${2:-.agents/skills}"
HOOKS_OPT="${3:-ask}"     # ask | yes | no -- see the hook block at the end
HOST_OPT="${4:-}"         # claude | cursor | codex | gemini | vscode | refact -- DECLARED,
                          # never inferred. See the host block below.

if [ -z "$TARGET" ]; then
  echo "usage: tools/install-skill.sh <target-repo> [skills-dir] [ask|yes|no] [harness]" >&2
  echo "       tools/install-skill.sh --prune <installed-copy>" >&2
  echo "  harness: claude | cursor | codex | gemini | vscode | refact" >&2
  echo "       tools/install-skill.sh --prune <installed-copy>" >&2
  exit 2
fi
if [ ! -d "$TARGET" ]; then
  echo "target does not exist: $TARGET" >&2
  exit 1
fi

DEST="$TARGET/$SKILLS_DIR/repo-governor"

if [ -e "$DEST" ]; then
  echo "already installed at $DEST -- to upgrade it, follow $DEST/INSTALLED.md" >&2
  exit 1
fi

mkdir -p "$TARGET/$SKILLS_DIR"
git clone -q "$SRC" "$DEST"
# The clone's origin is $SRC, which the documented install deletes when it is
# done. Point it at the repository an upgrade actually fetches from.
git -C "$DEST" remote set-url origin "$UPSTREAM_URL"

prune_copy
write_note

echo "installed: $DEST"
verify_prune
grep '^- Installed' "$DEST/INSTALLED.md" | sed 's/^/  /'
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

# --- onboarding advice -----------------------------------------------------
# Deliberately OUTSIDE the host block and NOT gated on a TTY. Onboarding has
# nothing to do with which agent you use, and a target with no recognisable
# host directory was silently getting no guidance at all. The offer to RUN it
# needs a terminal; the advice to run it does not.
if [ ! -f "$TARGET/.repo-governor.json" ]; then
  echo
  echo "This repository is not onboarded, so the engine can only ever answer"
  echo "AUTHORITY_SOURCE_MISSING. Onboarding runs detection, shows the evidence,"
  echo "then asks the two things no amount of file-reading can answer: which"
  echo "system is the roadmap authority, and what ADMITTED means in it."
  echo
  echo "    python3 $DEST/tools/onboard-interactive.py $TARGET"
  echo
  echo "It writes a PROPOSAL. Review it, then:"
  echo "    mv $TARGET/.repo-governor.proposed.json $TARGET/.repo-governor.json"
  echo "    cd $TARGET && python3 $DEST/engine/manifest.py --validate"
  echo "    (run it from $TARGET: the engine validates the repository you stand in)"
  echo "Then commit .repo-governor.json. Until it is tracked, validation reads"
  echo "READY_FOR_GOVERNANCE ON THIS HOST ONLY."
  echo
  echo "CAUTION: the proposal lands in the repository root and is itself a"
  echo "governance signal. Do not run it against a repository under activation"
  echo "measurement."
  if [ "$HOOKS_OPT" != "no" ] && [ -t 0 ]; then
    printf "Start onboarding now? [y/N] "
    read -r REPLY_O || REPLY_O="n"
    case "$REPLY_O" in
      [yY]*)
        python3 "$DEST/tools/onboard-interactive.py" "$TARGET" || true
        echo
        echo "  Once bound, re-run this script to be offered the hook:"
        echo "    $SRC/tools/install-skill.sh $TARGET $SKILLS_DIR"
        echo "  The re-run is not busywork -- the hook is silent without a"
        echo "  manifest, so there is nothing to offer until you have bound one." ;;
    esac
  fi
fi

# --- the hook offer -------------------------------------------------------
# Consent-gated, never default-on. Writing hook config into a settings.json the
# user owns is fine when they said yes and wrong when they did not; the rule is
# no SILENT write, not no write. Same shape as SKILL.md's --write.
# Which host, and therefore which config file. The host is DECLARED, never
# inferred.
#
# An earlier version fell back to sniffing the target for a `.cursor/` or
# `.claude/` directory. That is the defect ADR-028 exists for -- an identity
# guessed from incidental filesystem evidence -- and the consequence here is
# nastier than usual: a repository someone once opened in Cursor, whose owner
# actually runs Codex, would get `.cursor/hooks.json`. Codex would never read
# it, and the result is indistinguishable from a hook that does not work, which
# is the exact confusion this whole surface is built to avoid.
#
# Typing `.claude/skills` IS a declaration -- the user named the host. The
# cross-vendor `.agents/skills` names none, so we ask, or refuse.
HOST=""
if [ -n "$HOST_OPT" ]; then
  HOST="$HOST_OPT"                       # explicit, wins over everything
else
  case "$SKILLS_DIR" in
    *.claude*) HOST=claude ;;
    *.cursor*) HOST=cursor ;;
    *.codex*)  HOST=codex ;;
    *.gemini*) HOST=gemini ;;
    *.refact*) HOST=refact ;;
    *vscode*|*.github*) HOST=vscode ;;
  esac
fi
case "$HOST" in
  claude|cursor|codex|gemini|vscode|refact) ;;
  "") ;;                                  # undeclared; handled below
  *) echo "unknown host: '$HOST' (claude|cursor|codex|gemini|vscode|refact)" >&2; exit 2 ;;
esac
# `.agents/skills` is the cross-vendor path and declares nothing. Ask if there
# is a terminal; otherwise say what is missing and install the skill anyway --
# the skill works on every host, only the hook config is host-specific.
if [ -z "$HOST" ] && [ "$HOOKS_OPT" != "no" ] && [ -f "$TARGET/.repo-governor.json" ]; then
  if [ -t 0 ]; then
    echo
    echo "'$SKILLS_DIR' is the cross-vendor path and names no host, so which agent"
    echo "reads hooks here cannot be known. Guessing it from a stray .cursor/ or"
    echo "\.claude/ directory is how you write a config the host never reads --"
    echo "indistinguishable from a hook that does not work."
    printf "Which harness? [claude|cursor|codex|gemini|vscode|refact|skip] "
    read -r HOST || HOST=""
    [ "$HOST" = "skip" ] && HOST=""
  else
    echo
    echo "NOTE: no hook offered -- '$SKILLS_DIR' names no host and this is not a"
    echo "      terminal. Declare it to install one:"
    echo "        $SRC/tools/install-skill.sh $TARGET $SKILLS_DIR ask <harness>"
    echo "      harness: claude | cursor | codex | gemini | vscode | refact"
  fi
fi

case "$HOST" in
  claude) HOST_CFG=".claude/settings.json" ;;
  cursor) HOST_CFG=".cursor/hooks.json" ;;
  codex)  HOST_CFG=".codex/hooks.json" ;;
  gemini) HOST_CFG=".gemini/settings.json" ;;
  vscode) HOST_CFG=".github/hooks/repo-governor.json" ;;
  refact) HOST_CFG=".refact/hooks.yaml" ;;   # JSON is valid YAML
  *)      HOST_CFG="" ;;
esac
[ -n "$HOST_CFG" ] && HOST_KNOWN=1 || HOST_KNOWN=0

if [ "$HOST_KNOWN" = "1" ] && [ "$HOOKS_OPT" != "no" ]; then
  echo
  if [ ! -f "$TARGET/.repo-governor.json" ]; then
    echo "NOTE: the hook would be SILENT here -- $TARGET has no .repo-governor.json."
    echo "      The hook only speaks in a governed repository. Onboarding this one"
    echo "      makes it no longer silent about governance, which ends any activation"
    echo "      measurement in progress against it (docs/research/activation-protocol.md)."
    echo "      Not offering to install it. Onboard first -- see above."
  else
    REPLY_H="n"
    if [ "$HOOKS_OPT" = "yes" ]; then
      REPLY_H="y"
    elif [ -t 0 ]; then
      printf "Enable the governance hook (%s -> %s)? [y/N] " "$HOST" "$HOST_CFG"
      read -r REPLY_H || REPLY_H="n"
    else
      echo "Hook not installed (non-interactive). Re-run with 'yes' as the 3rd argument to install it."
    fi
    case "$REPLY_H" in
      [yY]*)
        RG_ABS="$(cd "$DEST" && pwd)"
        python3 - "$TARGET" "$RG_ABS" "$HOST" "$HOST_CFG" <<'PYHOOK'
import json, pathlib, sys
target, rg, host, rel = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]

# Use the SHIPPED template rather than a second copy inline. A config the
# installer writes and a config the docs describe must not be able to drift.
tpl = json.loads((pathlib.Path(rg) / "tools" / "hooks" / f"{host}.json")
                 .read_text(encoding="utf-8").replace("RG_SKILL_DIR", rg))
cfg = tpl.get("hooks", {})

p = target / rel
try:
    cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
except json.JSONDecodeError:
    # Refact's .refact/hooks.yaml may be hand-written YAML. This merge speaks
    # JSON only, and rewriting the user's YAML as JSON would lose comments and
    # structure they own. Refuse, say what to do; never replace the file.
    print(f"  NOT installed: {p} exists and is not JSON (hand-written YAML?).")
    print(f"  Merge the PreToolUse/PostToolUse entries from")
    print(f"    {rg}/tools/hooks/{host}.json")
    print(f"  into it by hand, replacing RG_SKILL_DIR with {rg}.")
    sys.exit(0)
kept = [k for k in cfg if k in cur.get("hooks", {})]
cur.setdefault("hooks", {}).update(cfg)          # merge; never replace the file
for k, v in tpl.items():                          # carry version etc, without clobbering
    cur.setdefault(k, v) if k != "hooks" else None
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
print(f"  hook installed -> {p}")
if kept:
    print(f"  NOTE: replaced your existing {', '.join(kept)} entries -- check them")
if host == "refact":
    print("  REFACT: blocking tested on Refact 8.6.4 (issue 247). The delivery-token")
    print("  check cannot run on Refact, because Refact discards hook output.")
    print("  Project hooks run ONLY when this repository is listed in")
    print("  hooks.trusted_projects in ~/.config/refact/privacy.yaml:")
    print(f"      hooks:\n        trusted_projects: [\"{target.resolve()}\"]")
    print("  Untrusted, it behaves exactly like a hook that does nothing.")
    print("  Refact discards hook stdout, so there is no advisory mode and no prompt")
    print("  moment: the write hook blocks (exit 2) when the manifest sets")
    print("  repo_governor.enforcement='blocking', and is silent otherwise.")
    print("  AGENTS.md is the activation remedy on this host; Refact loads it.")
elif host != "claude":
    print(f"  WARNING: the {host} template is UNVERIFIED. Event names come from its")
    print("  docs; the stdin field names have never been confirmed on a real host.")
    print()
    print("  A hook that runs and delivers nothing looks EXACTLY like a model")
    print("  ignoring governance. That happened on Claude Code: the operator saw a")
    print("  delivery token and the model reported none. So check delivery before")
    print("  you trust anything this hook does or fails to do:")
    print()
    print("    export RG_HOOK_VERBOSE=1")
    print(f"    echo '{{\"session_id\":\"x\",\"cwd\":\"{target}\"}}' \\")
    print(f"      | python3 {rg}/tools/hooks/governance-hook.py prompt")
    print()
    print("  Then, in a fresh session of your agent, ask it -- with no tool calls --")
    print("  whether it has a governance delivery token, and compare. If it does not")
    print("  match, the hook is not reaching the model and any result from it is not")
    print("  evidence. Report either way: docs/installation.md names the issue.")
if host == "codex":
    print()
    print("  CODEX: project hooks load only when .codex/ is TRUSTED. An untrusted")
    print("  directory behaves exactly like a hook that does nothing. Codex also")
    print("  documents no prompt-submit event, so only the write check is installed")
    print("  -- an AGENTS.md is the whole activation remedy on this host.")
if host != "refact":
    print("  advisory only. Blocking needs repo_governor.enforcement='blocking' in the")
    print("  manifest AND --exit2-on-deny on the write hook; neither was added.")
PYHOOK
        ;;
      *) echo "  Hook not installed. See docs/installation.md if you change your mind." ;;
    esac
  fi
fi
