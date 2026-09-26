# Runbook: Upgrade or uninstall Repo Governor

**Owner**: Repo Governor maintainer ([tosin2013](https://github.com/tosin2013))
**Risk level**: Low for an upgrade. Medium for an uninstall, because it edits host configuration files that you own.
**Last updated**: 2026-09-26
**Last tested**: 2026-09-26, macOS, git 2.x, Python 3, in a scratch directory. See [What was run and what was not](#what-was-run-and-what-was-not).
**Version**: 1.0.0
**Tracks**: [issue 258](https://github.com/tosin2013/repo-governor/issues/258)

---

## Quick reference

| Attribute | Value |
|---|---|
| **Execution time** | About 2 minutes for an upgrade. About 5 minutes for an uninstall. |
| **Impact window** | None. A running agent session keeps the skill it loaded. New sessions get the new version. |
| **Rollback time** | About 2 minutes |
| **Prerequisites** | Git, Python 3, network access to github.com, a copy installed by `tools/install-skill.sh` |

| Task | Section |
|---|---|
| Upgrade a copy installed by `install-skill.sh` | [Procedure A](#procedure-a-upgrade-an-installed-copy) |
| Upgrade a copy installed by v0.7.0 or earlier | [Procedure B](#procedure-b-upgrade-a-copy-installed-by-v070-or-earlier) |
| Uninstall from a host | [Procedure C](#procedure-c-uninstall-from-a-host) |
| Upgrade or uninstall the Claude Code plugin | [Procedure D](#procedure-d-the-claude-code-plugin-channel) |

---

## Scope and use case

### When to use this runbook

- A new release of Repo Governor is out and you want it in a repository.
- The update line in an old `INSTALLED.md` fails with `You are not currently on a branch.`
- You want to remove Repo Governor from a repository, and its hook configuration with it.
- You installed the Claude Code plugin and want to upgrade or remove it.

### Expected outcome

After an upgrade, the installed copy is at the tag you chose. `INSTALLED.md` names that tag and its commit. The prune is applied again. Hook configuration in your repository does not change.

After an uninstall, the skill directory is gone. The host configuration file has no entry that calls `governance-hook.py`. Keys that you added to that file stay.

### What this runbook does not cover

- A first install. See [installation.md](../installation.md).
- Removal of governance from a repository. The manifest (`.repo-governor.json`), the `.repo-governor/` directory, and the governance text in your `AGENTS.md` belong to your repository. This runbook does not remove them. That is a separate decision.
- The Refact trust entry in detail. See the rollback in the [Refact runbook](refact-integration.md#rollback-procedure).

---

## How an installed copy works

`tools/install-skill.sh` clones Repo Governor into the skills directory of your repository. Then it removes the files that describe Repo Governor's own repository. This removal is "the prune". The list of pruned paths is in the script and nowhere else.

The documented install clones a tag into a temporary directory first. So the installed copy has a detached HEAD, which is correct for a copy of a release. It is not on a branch, so `git pull` cannot work in it.

Since issue 258, the installer does three things for upgrades:

1. It sets the `origin` of the copy to `https://github.com/tosin2013/repo-governor`. The temporary directory is not used again.
2. It writes the installed tag and commit into `INSTALLED.md`. It names a tag only when HEAD is exactly at that tag. Otherwise it names the commit only ([ADR-028](../adrs/028-provider-identity-is-never-defaulted.md)).
3. It accepts `--prune <copy>`. This applies the prune of the version that is checked out in the copy, and writes `INSTALLED.md` again.

A copy installed by v0.7.0 or earlier has none of these. Its `origin` is the temporary directory, and its `INSTALLED.md` has the update line that fails. Use [Procedure B](#procedure-b-upgrade-a-copy-installed-by-v070-or-earlier) for it.

---

## Prerequisites

### Required access

- [ ] Write access to the repository that contains the installed copy.
- [ ] Read access to `https://github.com/tosin2013/repo-governor`.

### Required tools

- [ ] Git.
- [ ] Python 3. Procedure C uses it to edit JSON.
- [ ] For Procedure D only: Claude Code with the `claude plugin` command.

**Verify the tools**:

```bash
git --version
python3 --version
```

### System state

- [ ] You know the path of the installed copy. This runbook calls it `$RG`. The default is `.agents/skills/repo-governor`. Claude Code uses `.claude/skills/repo-governor`.
- [ ] You know which host the hook was installed for, if any: `claude`, `cursor`, `codex`, `gemini`, `vscode`, or `refact`.

---

## Pre-flight checks

**STOP**: Do not continue until all checks pass or you know which procedure to use.

### Check 1: The copy is an installed copy

```bash
ls "$RG/INSTALLED.md" "$RG/SKILL.md"
```

✅ **Pass criteria**: The command lists both files.
❌ **Fail action**: The directory is not an install made by `install-skill.sh`. It is a plain clone or a symlink. Do not use `--prune` on it. `--prune` refuses a directory with no `INSTALLED.md`.

### Check 2: Which procedure applies

```bash
git -C "$RG" config --get remote.origin.url
grep '^- Installed' "$RG/INSTALLED.md"
```

✅ **Pass criteria for Procedure A**: The first line is `https://github.com/tosin2013/repo-governor`, and `grep` prints two lines. Example from a run:

```
https://github.com/tosin2013/repo-governor
- Installed tag: `v0.0.1-fixture`
- Installed commit: `db34720a5c22e281c3029680903639e8e26a009d`
```

❌ **Fail action**: The first line is a temporary directory and `grep` prints nothing. The copy was installed by v0.7.0 or earlier. Use [Procedure B](#procedure-b-upgrade-a-copy-installed-by-v070-or-earlier). Example from a v0.7.0 install:

```
/var/folders/.../rg258/migrate/rg-tmp
```

### Check 3: The tag you want exists

```bash
git ls-remote --tags https://github.com/tosin2013/repo-governor 'v0.7*'
```

✅ **Pass criteria**: The tag is in the list. Output on 2026-09-26:

```
d38a1fc1fb502e058629476177d7625758e6755c	refs/tags/v0.7.0
73960e11d5a822d00f7b9dec40dabef7a9bea50e	refs/tags/v0.7.0^{}
```

❌ **Fail action**: Use a tag from the list. Do not upgrade to a branch. A branch is not a release ([ADR-034](../adrs/034-publication-is-per-channel-and-a-listing-claims-only-what-is-calibrated.md) rule 2).

**Important**: The upgrade procedure needs a target tag whose installer has `--prune`. v0.7.0 does not have it. Procedure A and Procedure B work only toward the first release after v0.7.0, or a later one.

---

## Procedure A: Upgrade an installed copy

`INSTALLED.md` in the copy has the same three commands. Replace `vX.Y.Z` with the tag from Check 3.

### Step A1: Go to the installed copy

```bash
cd "$RG"
```

### Step A2: Fetch the tags

```bash
git fetch --tags origin
```

**Expected output**: Git lists the branches and tags that the copy does not have yet. The install copies the tags that the temporary clone had, so the list can be short. From a run where the copy had all tags:

```
From <upstream>
 * [new branch]      upgrade-path-258 -> origin/upgrade-path-258
```

### Step A3: Check out the tag

```bash
git checkout --force vX.Y.Z
```

`--force` discards local changes in the copy. The prune is one of these changes. Step A4 applies it again. If you changed files in the copy yourself, copy them to a safe place before this step.

**Expected output**:

```
Previous HEAD position was db34720 fixture: working-tree installer
HEAD is now at ed8dc17 fixture b
```

### Step A4: Apply the prune of the new version

```bash
bash tools/install-skill.sh --prune .
```

**Expected output**:

```
re-pruned: <path to the copy>
  SKILL.md present
  pruned: AGENTS.md, CLAUDE.md, .claude/, .claude-plugin/, .repo-governor.json, .repo-governor/, docs/research/, CONTRIBUTING.md
  kept: LICENSE, NOTICE (Apache-2.0 sections 4a and 4d)
  - Installed tag: `v0.0.2-fixture`
  - Installed commit: `ed8dc17ebef2a7bd7327466da03c68bb9f5b3261`
```

The `pruned:` line comes from the new version of the script. It can differ from the line above if a release changes the prune list.

### Step A5: Start a new agent session

Skills load at session start. Close the current session of your agent. Start a new one in the repository.

---

## Procedure B: Upgrade a copy installed by v0.7.0 or earlier

This procedure changes `origin` once. Then it is the same as Procedure A.

### Step B1: Go to the installed copy

```bash
cd "$RG"
```

### Step B2: Set origin to the canonical repository

```bash
git remote set-url origin https://github.com/tosin2013/repo-governor
```

**Expected output**: None.

### Step B3: Fetch the tags

```bash
git fetch --tags origin
```

**Expected output**: From a run. The list depends on the tags in the upstream.

```
 * [new branch]      upgrade-path-258 -> origin/upgrade-path-258
 * [new tag]         v0.0.1-fixture   -> v0.0.1-fixture
 * [new tag]         v0.0.2-fixture   -> v0.0.2-fixture
```

### Step B4: Check out the tag

```bash
git checkout --force vX.Y.Z
```

**Expected output**:

```
Previous HEAD position was 73960e1 v0.7.0 prep: the plugin channel ships the pruned build over HTTPS (#245)
HEAD is now at ced3b35 fixture b
```

### Step B5: Apply the prune of the new version

```bash
bash tools/install-skill.sh --prune .
```

**Expected output**: The same as Step A4. The old `INSTALLED.md` is replaced. The new one names the tag and the upgrade procedure.

### Step B6: Start a new agent session

Do Step A5.

---

## Procedure C: Uninstall from a host

Do the steps in this order. Step C1 reads a template from the installed copy. Step C3 deletes the copy.

### Which file and which keys

The installer merges the template `tools/hooks/<host>.json` into one file in your repository. It adds the event keys under `hooks`. It adds each top-level `$comment` key of the template if your file does not have that key. For Cursor, it also adds `version` if your file does not have it.

| Host | File in your repository | Event keys under `hooks` | Top-level keys it can add |
|---|---|---|---|
| Claude Code (`claude`) | `.claude/settings.json` | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `$comment` |
| Cursor (`cursor`) | `.cursor/hooks.json` | `beforeSubmitPrompt`, `preToolUse`, `afterShellExecution` | `$comment`, `version` |
| Codex (`codex`) | `.codex/hooks.json` | `PreToolUse`, `PostToolUse` | `$comment`, `$comment_no_prompt_event` |
| Gemini CLI (`gemini`) | `.gemini/settings.json` | `BeforeAgent`, `BeforeTool`, `AfterTool` | `$comment` |
| VS Code (`vscode`) | `.github/hooks/repo-governor.json` | `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `$comment` |
| Refact (`refact`) | `.refact/hooks.yaml` | `PreToolUse`, `PostToolUse` | `$comment`, `$comment_trust`, `$comment_exit2`, `$comment_no_prompt_event` |

The installer replaces an event key that was already in your file. It prints `NOTE: replaced your existing ... entries` when it does this. This procedure cannot bring back those old entries. Get them from the history of the file in your repository.

If you merged a template by hand into a user-level file (`~/.claude/settings.json`, `~/.cursor/hooks.json`, `~/.gemini/settings.json`), the same keys apply to that file.

### Step C1: Remove the hook entries

Set the three variables for your install. Then run the Python command from the root of your repository. It removes each entry that calls `governance-hook.py` from the events in the table. It removes an event key that has no other entries. It removes a `$comment` key only when its value is the value in the template. It keeps all other keys.

```bash
RG=.claude/skills/repo-governor
HOST=claude
CFG=.claude/settings.json
python3 - "$RG/tools/hooks/$HOST.json" "$CFG" <<'PY'
import json, pathlib, sys
tpl = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
p = pathlib.Path(sys.argv[2])
cur = json.loads(p.read_text(encoding="utf-8"))
hooks = cur.get("hooks", {})
for event in tpl.get("hooks", {}):
    kept = [e for e in hooks.get(event, []) if "governance-hook.py" not in json.dumps(e)]
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)
for key, value in tpl.items():
    if key.startswith("$comment") and cur.get(key) == value:
        del cur[key]
p.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
print("left:", sorted(cur), "hooks:", sorted(hooks))
PY
```

**Expected output** when the installer created the file:

```
left: ['hooks'] hooks: []
```

**Expected output** when the file also had a key and a `Stop` hook of your own (from a run on each of the six hosts):

```
left: ['hooks', 'userKey'] hooks: ['Stop']
```

For Cursor, `version` stays. Cursor needs it in any `hooks.json`:

```
left: ['hooks', 'userKey', 'version'] hooks: ['Stop']
```

**Refact**: If `.refact/hooks.yaml` is YAML that you wrote by hand, the command fails on it. The installer did not merge into such a file. Remove the `PreToolUse` and `PostToolUse` entries that call `governance-hook.py` by hand.

### Step C2: Delete an empty configuration file

If the output of Step C1 is `left: ['hooks'] hooks: []`, nothing of yours is in the file. Delete it:

```bash
rm .claude/settings.json
```

For Cursor, the file is empty when the output is `left: ['hooks', 'version'] hooks: []`.

### Step C3: Remove the installed copy

```bash
rm -rf "$RG"
```

If you made a symlink to the copy from a second skills directory ([installation.md](../installation.md)), remove the symlink too.

### Step C4: Remove host-specific trust

- **Refact**: Remove the repository path from `hooks.trusted_projects` in `~/.config/refact/privacy.yaml`. Then restart the worker. See the [Refact runbook, rollback](refact-integration.md#rollback-procedure).
- **Codex**: The installer did not change the trust state of `.codex/`. Change it only if you trusted the directory for Repo Governor alone.
- **Other hosts**: No step.

### Step C5: Verify the uninstall

```bash
grep -c governance-hook.py "$CFG"
git status --short
```

**Expected output**: `grep` prints `0`. If you deleted the file in Step C2, it prints `grep: .cursor/hooks.json: No such file or directory`, with the name of your file. `git status` shows no hook file and no skills directory that you did not have before. From a run with a governed repository where Step C2 deleted the file:

```
?? .repo-governor.json
```

The manifest stays. It is part of your repository, not of the install.

---

## Procedure D: The Claude Code plugin channel

**NOT RUN.** The commands in this section come from `claude plugin --help` in Claude Code 2.1.283. They were not run for this runbook, because they change the Claude Code configuration of the user who runs them. No output is shown, because none was observed. `claude plugin validate .` on this repository printed `✔ Validation passed` for `.claude-plugin/marketplace.json`. That is the only command of this channel that was run.

The marketplace entry is `.claude-plugin/marketplace.json` ([ADR-034](../adrs/034-publication-is-per-channel-and-a-listing-claims-only-what-is-calibrated.md)). The marketplace name is `repo-governor`. The plugin name is `repo-governor`. The entry points at the pruned release archive of one tag. The plugin declares only the skill. It does not install hook configuration. If you added hooks by hand, remove them with Procedure C, Step C1 and Step C2.

### Step D1: Upgrade

1. Refresh the marketplace catalog:

   ```bash
   claude plugin marketplace update repo-governor
   ```

2. Update the plugin:

   ```bash
   claude plugin update repo-governor@repo-governor
   ```

3. Restart Claude Code. The help text says a restart is necessary.

The version you get is the version that `marketplace.json` pins on the default branch. A release updates that pin.

### Step D2: Uninstall

1. Remove the plugin:

   ```bash
   claude plugin uninstall repo-governor@repo-governor
   ```

   The default scope is `user`. If you installed it with `--scope project` or `--scope local`, give the same scope.

2. Remove the marketplace:

   ```bash
   claude plugin marketplace remove repo-governor
   ```

3. Verify:

   ```bash
   claude plugin list
   claude plugin marketplace list
   ```

   Neither list contains `repo-governor`.

---

## Verification and success criteria

After an upgrade:

- [ ] `grep '^- Installed' "$RG/INSTALLED.md"` names the tag you chose.
- [ ] `git -C "$RG" status | head -n 1` prints `HEAD detached at <tag>`.
- [ ] `ls "$RG/AGENTS.md"` fails with `No such file or directory`.
- [ ] Your hook configuration file did not change. In a run, `shasum .claude/settings.json` gave the same value before and after the upgrade.
- [ ] A new agent session lists `repo-governor`.

After an uninstall:

- [ ] `$RG` does not exist.
- [ ] The host configuration file has no `governance-hook.py`, or does not exist.
- [ ] The keys that you added to that file are still there.

---

## Rollback procedure

### When to roll back

- The new version breaks something in your repository.
- You uninstalled by mistake.

### Roll back an upgrade to a tag that has `--prune`

Do Procedure A, Step A3 and Step A4, with the old tag. From a run:

```
$ git checkout --force v0.0.1-fixture
HEAD is now at 4d35aed fixture: working-tree installer
$ bash tools/install-skill.sh --prune .
...
  - Installed tag: `v0.0.1-fixture`
  - Installed commit: `4d35aed69107d073941384e90e57a75db4079dd1`
```

### Roll back an upgrade to v0.7.0 or earlier

The installer of v0.7.0 has no `--prune`. Step A4 fails with it:

```
target does not exist: --prune
```

Delete the copy and install the old tag again. Give `no` as the hooks argument, so that the installer does not touch your hook configuration. The configuration names the path of the copy, and the path does not change.

1. Remove the copy:

   ```bash
   rm -rf .claude/skills/repo-governor
   ```

2. Clone the old tag to a temporary directory:

   ```bash
   git clone --branch v0.7.0 https://github.com/tosin2013/repo-governor /tmp/rg-old
   ```

3. Install it with the same skills directory, and `no` for hooks:

   ```bash
   bash /tmp/rg-old/tools/install-skill.sh "$PWD" .claude/skills no
   ```

In a run, `shasum .claude/settings.json` gave the same value before step 1 and after step 3. The hook path `tools/hooks/governance-hook.py` existed again in the copy. The run cloned v0.7.0 from a local copy of this repository, not from GitHub.

### Roll back an uninstall

Do the install in [installation.md](../installation.md) again. To get the hook back, give `yes` and the host as the third and fourth arguments of `install-skill.sh`.

---

## Troubleshooting

### `You are not currently on a branch.`

**Symptom**: The update line in an old `INSTALLED.md` fails:

```
$ git -C . stash && git -C . pull && git -C . stash pop
Saved working directory and index state WIP on (no branch): 73960e1 v0.7.0 prep: the plugin channel ships the pruned build over HTTPS (#245)
You are not currently on a branch.
Please specify which branch you want to merge with.
```

**Cause**: The copy was installed by v0.7.0 or earlier. It is a detached HEAD at a tag ([issue 258](https://github.com/tosin2013/repo-governor/issues/258)).

**Resolution**: Run `git stash pop` in the copy to undo the stash. Then use [Procedure B](#procedure-b-upgrade-a-copy-installed-by-v070-or-earlier).

### `does not appear to be a git repository`

**Symptom**:

```
fatal: '/var/folders/.../rg-tmp' does not appear to be a git repository
fatal: Could not read from remote repository.
```

**Cause**: `origin` is the temporary directory of the install, and that directory is gone.

**Resolution**: Do Procedure B, Step B2.

### `not an installed copy`

**Symptom**:

```
not an installed copy: <path> (no INSTALLED.md, or not a git clone)
```

**Cause**: The path given to `--prune` is not an install. It can be a source checkout of Repo Governor.

**Resolution**: Give the path of the installed copy. `--prune` refuses other directories on purpose, so that it does not remove `AGENTS.md` from a source checkout.

### `target does not exist: --prune`

**Cause**: The checked-out version of `install-skill.sh` is v0.7.0 or earlier. It has no `--prune`.

**Resolution**: Check out a newer tag, or use [the rollback for v0.7.0 or earlier](#roll-back-an-upgrade-to-v070-or-earlier).

### `already installed at ...`

**Cause**: `install-skill.sh` does not install over a copy.

**Resolution**: Use Procedure A to change the version. Use Procedure C, Step C3, then install again, to start from nothing.

### Escalation path

Open an issue at [tosin2013/repo-governor](https://github.com/tosin2013/repo-governor/issues). Give the output of Check 2 and the command that failed.

---

## What was run and what was not

All commands in Procedures A, B, and C, and in the rollback, were run on 2026-09-26 in scratch directories under `$TMPDIR`, not in a real repository. The outputs in this runbook come from those runs. Long temporary paths are shortened to `<path to the copy>` or `/var/folders/...`.

- **The upgrade target was a fixture tag.** No release tag has the fixed installer yet. The runs used a local upstream with the tags `v0.0.1-fixture` and `v0.0.2-fixture`. The setting `url.<local upstream>.insteadOf=https://github.com/tosin2013/repo-governor` sent the fetch there. So `origin` was the real URL and the fetch was local. The same case runs in `conformance/hooks.py` (the checks that start with `upgrade`).
- **The v0.7.0 install was real.** Check 2, Procedure B, and the troubleshooting outputs used a v0.7.0 install cloned from a local copy of this repository.
- **Check 3 was run against GitHub.**
- **Procedure C was run for all six hosts**, with an install by `install-skill.sh` and the hooks argument `yes`. No agent host was started. The runs checked the files, not the behavior of a host.
- **Procedure D was not run**, except `claude plugin validate .`.

---

## Appendix

### Related documents

- [installation.md](../installation.md): the first install and the host table.
- [Refact runbook](refact-integration.md): Refact trust and rollback.
- [ADR-027](../adrs/027-the-governed-repository-is-not-the-install-directory.md): the engine governs the repository, not the install directory.
- [ADR-028](../adrs/028-provider-identity-is-never-defaulted.md): why `INSTALLED.md` names a tag only when HEAD is at it.
- [ADR-029](../adrs/029-hooks-as-deterministic-delivery-surface.md): the hook surface.
- [ADR-034](../adrs/034-publication-is-per-channel-and-a-listing-claims-only-what-is-calibrated.md): the plugin channel.

### Version history

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0.0 | 2026-09-26 | Repo Governor maintainer, with Claude Code | First version, with the installer change for issue 258 |

---

**Next review**: when the first release after v0.7.0 is cut. Then run Procedure A against GitHub, replace the fixture outputs, and update **Last tested**.
