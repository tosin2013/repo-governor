# Runbook: Cut a Repo Governor release

**Owner**: Repo Governor maintainer ([tosin2013](https://github.com/tosin2013))
**Risk level**: High. A published tag is public, other people clone it, and the plugin channel serves it.
**Last updated**: 2026-09-26
**Last tested**: 2026-09-26. The read-only checks ran against `v0.7.0`. The tag and publish steps did not run in this draft.
**Version**: 1.0.0
**Tracks**: [issue 257](https://github.com/tosin2013/repo-governor/issues/257) (this runbook), [issue 223](https://github.com/tosin2013/repo-governor/issues/223) and [ADR-035](../adrs/035-a-release-may-depend-on-a-proposed-adr-only-on-declared-and-expiring-terms.md) (the release condition)

---

## Quick reference

| Attribute | Value |
|---|---|
| **Execution time** | About 2 hours for the preparation. The release workflow takes about 2 minutes. |
| **Impact window** | From the tag push until the workflow finishes. During this time the tag exists and the release does not. |
| **Rollback time** | About 10 minutes for a release that nobody installed. A tag that people cloned cannot be recalled. |
| **Prerequisites** | Maintainer rights on `tosin2013/repo-governor`, `gh` signed in, Python 3.11, `dolt`, Git |

### The order of work

| Phase | Steps | Who |
|---|---|---|
| Prepare | Step 1 to Step 6 | The maintainer, or an agent under an authorized issue |
| Merge | Step 7 | The maintainer approves and merges the pull request |
| Tag and publish | Step 8 to Step 10 | The maintainer only |
| Verify | Step 11 to Step 13 | Anyone |

### The version sites

A release changes the version in five places. `tools/check-version.py` checks them against the tag.

| File | What it states | Checked by |
|---|---|---|
| `engine/version.py` | `ENGINE_VERSION = "X.Y.Z"`. Every decision record cites it (ADR-009). | `check-version.py` |
| `SKILL.md` | `metadata.version: "X.Y.Z"`. Agent hosts read this value. | `check-version.py` after [PR 260](https://github.com/tosin2013/repo-governor/pull/260) merges. Until then, check it by hand in Step 3. |
| `README.md` | `git clone --branch vX.Y.Z` | `check-version.py`, `conformance/skill.py`, `conformance/install.py` |
| `docs/installation.md` | `git clone --branch vX.Y.Z` | `check-version.py`, `conformance/skill.py`, `conformance/install.py` |
| `.claude-plugin/marketplace.json` | The `version` field and the version in the `source.url` | `conformance/skill.py` (ADR-034 rule 2) |

Two more sites state `engine_min_version`: `.repo-governor.json` and `tools/onboard-interactive.py`. They are a compatibility floor, not the version. Do not bump them with the release. `check-version.py` requires that they agree and that they are not above the tag.

---

## Scope and use case

### When to use this runbook

- You cut a new release of Repo Governor, a minor or a patch.
- A release failed and you must repair it.
- You must decide if a change needs a new release.

### Expected outcome

- An annotated tag `vX.Y.Z` that is an ancestor of `main`.
- A published GitHub release with four assets: the tarball, the plugin zip, and a `.sha256` file for each.
- Release notes from `docs/releases/vX.Y.Z.md`, not generated notes.
- A ratification record `docs/adrs/RATIFICATION-vX.Y.Z.md` when the release depends on a Proposed ADR.
- The plugin channel entry points at the new zip.

### What this runbook does not cover

- The decision to accept an ADR. Acceptance is the maintainer's act (§68). This runbook tells you when the decision is due.
- Governing another repository. See [installation.md](../installation.md) and the [Refact runbook](refact-integration.md).
- Upgrading an existing install. [Issue 258](https://github.com/tosin2013/repo-governor/issues/258) adds `docs/runbooks/upgrade-and-uninstall.md`.

### Why this runbook exists

The procedure lived only in comments in `release.yml` and `check-version.py`. v0.7.0 shows the cost:

- It shipped without `docs/releases/v0.7.0.md`. The Publish step fell back to `--generate-notes`, and the release page is a list of pull requests.
- It shipped with `SKILL.md` at `version: "0.6.0"`. No check read that file.
- It shipped with no ratification record, while it depended on four Proposed ADRs ([ADR-035](../adrs/035-a-release-may-depend-on-a-proposed-adr-only-on-declared-and-expiring-terms.md), context table).

---

## How the release machinery works

### What `release.yml` does

The workflow is [`.github/workflows/release.yml`](../../.github/workflows/release.yml). It starts on a push of a tag that matches `v[0-9]+.[0-9]+.[0-9]+`. It also starts by hand with `workflow_dispatch` and a `tag` input.

| Step in the workflow | What it verifies or makes | Failure |
|---|---|---|
| Resolve the tag | The tag has the form `vX.Y.Z` | `not a release tag` |
| The tag exists, and points at something reviewed | The tag exists. The tag is an ancestor of `origin/main`. | An error for a missing tag or for unreviewed history. A lightweight tag gives a warning only. |
| Version strings agree with the tag | `python3 tools/check-version.py <tag>` | Any `[FAIL]` line |
| Adapter dependencies, bootstrap | Installs Dolt 2.3.0 and runs `tools/bootstrap-decisions.sh` | Download or install error |
| Conformance at the tag | `./tools/run-conformance.sh --hermetic` and `python3 engine/manifest.py --validate` | Any failed suite |
| Build the artifact by RUNNING the installer | Runs `tools/install-skill.sh` at the tag into an empty repository. Packs the result as `repo-governor-<tag>.tar.gz` and as `repo-governor-<tag>.zip`, each with a SHA-256 file. | Installer error |
| The artifact is what it claims to be | `SKILL.md` is in the tarball and at the root of the zip. No pruned path survives in either. | `no SKILL.md`, or `a pruned path survived` |
| Publish | Creates or adopts the release and attaches the four assets | See the table below |

The pruned paths are `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.claude-plugin`, and `.repo-governor`. They are correct in this repository and wrong in an install (ADR-027, ADR-034 rule 1).

### How the Publish step picks the notes

| Condition at publish time | What the workflow runs | Notes on the release page |
|---|---|---|
| A release for the tag already exists, a draft or not | `gh release upload --clobber`, then `gh release edit --draft=false --verify-tag` | The notes of the existing release. The notes file is not read. |
| No release exists and `docs/releases/<tag>.md` exists at the tag | `gh release create --notes-file docs/releases/<tag>.md` | The notes file |
| No release exists and there is no notes file | `gh release create --generate-notes` | A generated list of pull requests. v0.7.0 shipped this way. |

The notes file must exist **in the tagged commit**. A file that you add to `main` after the tag does not count.

### Hermetic and live conformance

`tools/run-conformance.sh` has two sets of suites.

| Set | Suites | Depends on |
|---|---|---|
| `--hermetic` | `layer1 layer2 transport manifest onboarding vocabulary bindings skill envelope execution imports status acceptance coverage benchmark union` | This checkout only. The release workflow runs this set. |
| `--live` | `hooks install roadmap` | The live issue board and the remote tags. The release workflow does not run this set. |

The `install` suite asks the remote if the tag in the install pins exists. Between the version bump and the tag push, the pins name a tag that does not exist yet. In that window `install` fails, and the failure is correct.

---

## Prerequisites

### Required access

- [ ] Maintainer rights on `tosin2013/repo-governor`. You push tags and merge to `main`.
- [ ] `gh` signed in with `repo` scope.
- [ ] An open issue that authorizes the release work, admitted and assigned. `python3 engine/completion.py <issue>` returns `CONTINUE`.

### Required tools

- [ ] Python 3.11 or later. The workflow uses 3.11.
- [ ] Git.
- [ ] `gh`.
- [ ] `dolt`. The decision store needs it (ADR-011 rule 4).
- [ ] `shasum` or `sha256sum`, and `unzip`.

**Verify the tools**:

```bash
python3 --version
git --version
gh auth status
dolt version
```

### System state

- [ ] A clean clone of `main`, with tags fetched.
- [ ] The decision store exists. Run `./tools/bootstrap-decisions.sh` once in a new clone or worktree.

---

## Pre-flight checks

**STOP**: Do not continue until all checks pass.

### Check 1: The work is authorized

```bash
python3 engine/completion.py 257
```

Replace `257` with the issue that authorizes this release.

✅ **Pass criteria**: The output contains `"decision": "CONTINUE"`.
❌ **Fail action**: Stop. Ask the maintainer to admit and assign the issue. Do not admit it yourself (ADR-018).

### Check 2: The previous release is consistent

```bash
git fetch origin --tags
python3 tools/check-version.py v0.7.0
```

Replace `v0.7.0` with the latest release tag.

**Expected output** (measured on 2026-09-26):

```text
Release v0.7.0

  [PASS] engine/version.py (the engine's own version) is 0.7.0
  [PASS] README.md (the version the README tells people to clone) pins 0.7.0
  [PASS] docs/installation.md (the version the installation guide tells people to clone) pins 0.7.0
  [PASS] .repo-governor.json (this repository's own manifest floor) floor 0.1.0 is not above the release
  [PASS] tools/onboard-interactive.py (the floor written into every proposal it generates) floor 0.1.0 is not above the release
  [PASS] both engine_min_version sites agree

VERSION: CONSISTENT
```

✅ **Pass criteria**: The last line is `VERSION: CONSISTENT`.
❌ **Fail action**: `main` drifted after the last release. Find the change with `git log <last-tag>..origin/main -- engine/version.py README.md docs/installation.md` and fix it first.

### Check 3: Hermetic conformance passes on `main`

```bash
./tools/bootstrap-decisions.sh
./tools/run-conformance.sh --hermetic
```

**Expected output** (last line, measured on 2026-09-26):

```text
16/16 pass
```

✅ **Pass criteria**: `16/16 pass`. The number of suites grows over time. Every suite passes.
❌ **Fail action**: Fix the failure on `main` before you prepare a release. See [Hermetic suites fail in a new worktree](#hermetic-suites-fail-in-a-new-worktree).

### Check 4: The last release workflow succeeded

```bash
gh run list --workflow release.yml --limit 3
```

**Expected output** (measured on 2026-09-26):

```text
completed	success	v0.7.0 prep: the plugin channel ships the pruned build over HTTPS (#245)	release	v0.7.0	push	35523508316	2m6s	2026-09-20T16:41:34Z
completed	success	Ratify the v0.6.0 architecture review	release	v0.6.0	push	33912415596	2m5s	2026-09-04T19:41:01Z
completed	success	Architecture ratification review for v0.5.0 (evidence half) (#219)	release	v0.5.0	push	33424134030	1m56s	2026-08-31T18:16:48Z
```

✅ **Pass criteria**: The latest run shows `completed` and `success`.
❌ **Fail action**: Repair the previous release first. See [Rollback procedure](#rollback-procedure).

---

## Step-by-step procedure

### Step 1: Choose the version

**What this does**: Sets `X.Y.Z` for every later step.

Repo Governor is before 1.0. The rules are:

| Change since the last tag | Bump | Example |
|---|---|---|
| A behaviour change that can turn an adopter's CI red | Minor: `0.Y+1.0` | v0.8.0. `manifest.py --validate` now fails a repository declared below its ADR-006 floor. |
| A new host, a new adapter, or a new channel | Minor | v0.8.0 adds Refact as a hook host. |
| Fixes that do not change a disposition or a validation result | Patch: `0.Y.Z+1` | v0.4.1 |

1. List the changes since the last tag with `git log --oneline v0.7.0..origin/main`.
2. For each change, ask: can this make an adopter's `--validate` or conformance fail?
3. If one change can, choose a minor bump.
4. Otherwise, choose a patch bump.
5. Write the version in the release issue.

✅ **Success indicator**: The release issue states `vX.Y.Z` and the reason for the bump.

---

### Step 2: Do the ADR-035 duties

**What this does**: Finds each Proposed ADR that the release depends on, counts its releases, and records the result before the tag. This is the release condition from [ADR-035](../adrs/035-a-release-may-depend-on-a-proposed-adr-only-on-declared-and-expiring-terms.md).

#### 2a: Derive the dependent ADRs

Rule 1 of ADR-035 sets the scope: `engine/`, the adapters that `.repo-governor.json` binds, `tools/`, and `.claude-plugin/`. The script below uses that scope for the current tree. For earlier tags it searches all of `adapters/`, as ADR-035 measured.

```bash
python3 - <<'EOF'
import json, re, subprocess
from pathlib import Path
m = json.load(open(".repo-governor.json"))
bound = sorted({b["adapter"] for k, v in (m.get("providers") or {}).items()
                if not k.startswith("$") for b in (v if isinstance(v, list) else [v])})
scope = ["engine", "tools", ".claude-plugin"] + bound
tags = subprocess.run(["git", "tag", "-l", "v*"], capture_output=True, text=True).stdout.split()
for adr in sorted(Path("docs/adrs").glob("[0-9]*.md")):
    st = re.search(r"^\*\*Status\*\*:\s*(\S+)", adr.read_text(), re.M)
    if not (st and st.group(1).startswith("Proposed")):
        continue
    num = adr.name[:3]
    now = subprocess.run(["git", "grep", "-l", f"ADR-{num}", "--"] + scope,
                         capture_output=True, text=True).stdout.split()
    past = [t for t in tags if subprocess.run(
        ["git", "grep", "-q", f"ADR-{num}", t, "--",
         "engine", "adapters", "tools", ".claude-plugin"]).returncode == 0]
    if now:
        print(f"ADR-{num} DEPENDENT  earlier releases: {len(past)}  cited by: {len(now)} file(s)")
    else:
        print(f"ADR-{num} not dependent")
EOF
```

**Expected output** (measured on `main` on 2026-09-26, with 12 tags from `v0.1.0` to `v0.7.0`):

```text
ADR-020 DEPENDENT  earlier releases: 11  cited by: 2 file(s)
ADR-029 DEPENDENT  earlier releases: 11  cited by: 8 file(s)
ADR-030 DEPENDENT  earlier releases: 7  cited by: 1 file(s)
ADR-031 DEPENDENT  earlier releases: 4  cited by: 2 file(s)
ADR-032 not dependent
ADR-033 DEPENDENT  earlier releases: 3  cited by: 1 file(s)
ADR-034 DEPENDENT  earlier releases: 1  cited by: 2 file(s)
ADR-035 not dependent
```

⚠️ **Important**: The ADR-035 context table names ADR-029, ADR-031, ADR-033 and ADR-034. With the rule 1 scope, the script also finds ADR-020 and ADR-030. `tools/live-equivalence.py` and `tools/provider-readiness.py` cite ADR-020. `tools/onboard-interactive.py` cites ADR-030. To see the citing files, run `git grep -n "ADR-020" -- engine tools .claude-plugin`. Record every ADR that the script names. If a citation is not a real dependency, remove the citation or amend ADR-035. Do not drop the ADR from the record by judgement.

#### 2b: Count the releases for each dependent ADR

1. Take `earlier releases` from the output of 2a.
2. Add 1 for the release that you prepare now.
3. Write the total for each ADR in the release issue.

#### 2c: Resolve each ADR past the expiry, before you tag

Rule 5 of ADR-035 permits at most two releases for each Proposed ADR. An ADR with 2 or more earlier releases cannot ship in this release as it is.

1. List each ADR whose earlier releases are 2 or more.
2. Give the list to the maintainer.
3. The maintainer decides each ADR, reduces it, or removes the dependency.
4. Merge each decision to `main` before Step 7.
5. Run 2a again.

| Action | What changes |
|---|---|
| **Decide** | The ADR becomes `Accepted`, or a new ADR that can be accepted supersedes it. |
| **Reduce** | The ADR is amended to the part its evidence supports, and that part is accepted. |
| **Remove** | The runtime stops citing and using the ADR. |

✅ **Success indicator**: Every ADR that 2a names has 1 earlier release or none.
⚠️ **Important**: Do not amend rule 5 to let an expired ADR ship once more. ADR-035 acceptance condition 4 forbids it.

#### 2d: Write the ratification record

Write `docs/adrs/RATIFICATION-vX.Y.Z.md` when 2a names one or more dependent ADRs. Use [RATIFICATION-v0.6.0.md](../adrs/RATIFICATION-v0.6.0.md) as the model for the format.

The record contains:

1. The date it was prepared, and the statement that it is not ratified yet.
2. The method: the scope from rule 1, and the command from 2a.
3. A table with one row for each dependent ADR.
4. For each ADR, each acceptance condition and its state: met, not met, or cannot be met by this project.
5. For each ADR, the count from 2b, this release included.
6. The findings that the review made.
7. An empty section headed `Maintainer's acceptance`.

**Do not** write the acceptance line. Acceptance is the maintainer's act (§68). An agent writes it only when the maintainer tells it the exact words in the session, and the record says so.

✅ **Success indicator**: The record exists, names every ADR from 2a, and gives each count.

---

### Step 3: Bump every version site

**What this does**: Makes the tree state the new version in each place that `check-version.py` and `conformance/skill.py` read.

1. In `engine/version.py`, set `ENGINE_VERSION = "X.Y.Z"`.
2. In `SKILL.md`, set `metadata.version` to `"X.Y.Z"`.
3. In `README.md`, set the `git clone --branch vX.Y.Z` line.
4. In `docs/installation.md`, set the `git clone --branch vX.Y.Z` line.
5. In `.claude-plugin/marketplace.json`, set `version` to `"X.Y.Z"`.
6. In the same file, set both versions in `source.url` to `vX.Y.Z`.
7. Do not change `engine_min_version`.

**Verification**:

```bash
grep -n -E 'ENGINE_VERSION =|--branch v[0-9]|"version": "|releases/download/v|^  version:' \
  engine/version.py SKILL.md README.md docs/installation.md .claude-plugin/marketplace.json
```

**Expected output** (measured on `main` on 2026-09-26, before a bump):

```text
engine/version.py:19:ENGINE_VERSION = "0.7.0"
SKILL.md:7:  version: "0.6.0"
README.md:84:git clone --branch v0.7.0 https://github.com/tosin2013/repo-governor /tmp/rg
docs/installation.md:12:git clone --branch v0.7.0 https://github.com/tosin2013/repo-governor /tmp/repo-governor
.claude-plugin/marketplace.json:16:        "url": "https://github.com/tosin2013/repo-governor/releases/download/v0.7.0/repo-governor-v0.7.0.zip"
.claude-plugin/marketplace.json:19:      "version": "0.7.0",
```

The `SKILL.md` line shows the v0.7.0 defect. After your bump, every line states `X.Y.Z`.

✅ **Success indicator**: Six lines print, and all of them state the new version.

---

### Step 4: Write the release notes

**What this does**: Gives the Publish step a notes file. Without it, the release page gets generated notes, as v0.7.0 did.

1. Create `docs/releases/vX.Y.Z.md`.
2. Use [v0.6.0.md](../releases/v0.6.0.md) as the model for the format.
3. Start with a heading: `# vX.Y.Z` and a one-line summary.
4. Write one section for each change that an adopter can see.
5. For a behaviour change, state what fails now that passed before.
6. Write a section for the architecture: each dependent ADR and its count from Step 2.
7. Write a `Verification` section with the conformance result from Step 5.
8. Name the issues that the release closes, and the issues that it files.

**Verification**:

```bash
ls docs/releases/
```

✅ **Success indicator**: The list contains `vX.Y.Z.md`.

---

### Step 5: Run the version check and conformance

**What this does**: Runs the same checks that the release workflow runs, before the tag exists.

```bash
python3 tools/check-version.py vX.Y.Z
./tools/run-conformance.sh --hermetic
python3 engine/manifest.py --validate
./tools/run-conformance.sh --live
```

**Expected output**: The `check-version.py` output ends with `VERSION: CONSISTENT`. The hermetic run ends with `16/16 pass`. The `--validate` banner starts with `READY_FOR_GOVERNANCE`.

For comparison, this is `check-version.py v0.8.0` on `main` before a bump (measured on 2026-09-26):

```text
Release v0.8.0

  [FAIL] engine/version.py (the engine's own version) is 0.8.0
         states '0.7.0', the tag says '0.8.0' -- decision records would cite an engine that is not this one
  [FAIL] README.md (the version the README tells people to clone) pins 0.8.0
         tells readers to install v0.7.0 while releasing v0.8.0 -- a stale pin is worse than none, because it looks deliberate
  [FAIL] docs/installation.md (the version the installation guide tells people to clone) pins 0.8.0
         tells readers to install v0.7.0 while releasing v0.8.0 -- a stale pin is worse than none, because it looks deliberate
  [PASS] .repo-governor.json (this repository's own manifest floor) floor 0.1.0 is not above the release
  [PASS] tools/onboard-interactive.py (the floor written into every proposal it generates) floor 0.1.0 is not above the release
  [PASS] both engine_min_version sites agree

VERSION: INCONSISTENT (3)
```

✅ **Success indicator**: `VERSION: CONSISTENT`, all hermetic suites pass, and `hooks` and `roadmap` pass in the live run.
⚠️ **Expected failure**: `install` fails in the live run until Step 9. The pins name `vX.Y.Z`, and the remote does not have that tag yet.
⚠️ **If `roadmap` fails**: An authorized issue has no acceptance record. See [roadmap fails on an authorized issue](#roadmap-fails-on-an-authorized-issue).

---

### Step 6: Open the release pull request

**What this does**: Puts the version bump, the notes, and the record through review.

1. Create a branch from `origin/main`.
2. Commit the files from Step 2, Step 3, and Step 4.
3. Do not put a closing verb next to a `#` reference in the commit message.
4. Push the branch and open a pull request.
5. Wait for the `conformance` workflow to pass.

**Verification**:

```bash
gh pr checks <pr-number>
```

✅ **Success indicator**: Every check passes.

---

### Step 7: Merge to `main`

**What this does**: Makes the release commit reviewed history. The workflow refuses a tag that is not an ancestor of `origin/main`.

1. The maintainer reads the ratification record.
2. The maintainer writes the acceptance line, or refuses the release.
3. The maintainer merges the pull request.

**Verification**:

```bash
git fetch origin
python3 tools/check-version.py vX.Y.Z
```

✅ **Success indicator**: `VERSION: CONSISTENT` on the merged `main`.
⚠️ **Important**: From this point, `main` tells readers to clone a tag that does not exist yet. Do Step 8 and Step 9 without delay.

---

### Step 8: Create the annotated tag

**Not run in this draft.** The maintainer does this step.

**What this does**: Creates a tag with a tagger and a date. A lightweight tag gets a warning from the workflow, because it is thin provenance for a governance artifact.

1. Check out the merged `main`.
2. Create the tag on the merge commit.
3. Verify the tag type and ancestry.

```bash
git checkout main
git pull --ff-only
git tag -a vX.Y.Z -m "vX.Y.Z: <one-line summary>"
git cat-file -t vX.Y.Z
git merge-base --is-ancestor vX.Y.Z origin/main && echo "vX.Y.Z is an ancestor of origin/main"
```

**Expected output** (the two checks, measured against `v0.7.0`):

```text
tag
v0.7.0 is an ancestor of origin/main
```

✅ **Success indicator**: `tag`, and the ancestor line prints.
❌ **If `commit` prints**: The tag is lightweight. Delete it with `git tag -d vX.Y.Z` and create it again with `-a`.

---

### Step 9: Push the tag

**Not run in this draft.** The maintainer does this step.

**What this does**: Starts the release workflow.

```bash
git push origin vX.Y.Z
```

✅ **Success indicator**: Git reports `* [new tag] vX.Y.Z -> vX.Y.Z`.

---

### Step 10: Watch the release workflow

**Not run in this draft** for a new tag. The list command below ran on 2026-09-26.

**What this does**: Confirms that each workflow step passes.

1. Find the run for the tag.
2. Watch it until it stops.

```bash
gh run list --workflow release.yml --limit 3
gh run watch <run-id> --exit-status
```

✅ **Success indicator**: The run shows `completed` and `success` for `vX.Y.Z`. A good run takes about 2 minutes.
❌ **If failed**: Read the failed step with `gh run view <run-id> --log-failed`. Go to [Troubleshooting](#troubleshooting).

---

### Step 11: Verify the published release and its assets

**What this does**: Checks what the users get, not what the workflow reported.

```bash
gh release view vX.Y.Z --json tagName,name,isDraft,publishedAt,assets \
  --jq '{tagName,name,isDraft,publishedAt,assets:[.assets[]|{name,size}]}'
```

**Expected output** (measured against `v0.7.0` on 2026-09-26):

```text
{"assets":[{"name":"repo-governor-v0.7.0.tar.gz","size":542763},{"name":"repo-governor-v0.7.0.tar.gz.sha256","size":94},{"name":"repo-governor-v0.7.0.zip","size":706967},{"name":"repo-governor-v0.7.0.zip.sha256","size":91}],"isDraft":false,"name":"v0.7.0","publishedAt":"2026-09-20T16:43:37Z","tagName":"v0.7.0"}
```

✅ **Success indicator**: Four assets, and `"isDraft":false`.

Download the assets into an empty directory and check them:

```bash
mkdir -p /tmp/rg-release && cd /tmp/rg-release
gh release download vX.Y.Z --repo tosin2013/repo-governor --dir . --clobber
shasum -a 256 -c repo-governor-vX.Y.Z.tar.gz.sha256
shasum -a 256 -c repo-governor-vX.Y.Z.zip.sha256
unzip -Z1 repo-governor-vX.Y.Z.zip | grep -x SKILL.md
unzip -Z1 repo-governor-vX.Y.Z.zip | grep -cE '^(AGENTS\.md|CLAUDE\.md|\.claude/|\.claude-plugin|\.repo-governor)'
tar -tzf repo-governor-vX.Y.Z.tar.gz | grep -x repo-governor/SKILL.md
unzip -p repo-governor-vX.Y.Z.zip SKILL.md | grep -m1 'version:'
```

**Expected output** (measured against `v0.7.0` on 2026-09-26):

```text
repo-governor-v0.7.0.tar.gz: OK
repo-governor-v0.7.0.zip: OK
SKILL.md
0
repo-governor/SKILL.md
  version: "0.6.0"
```

✅ **Success indicator**: Both checksums are `OK`. `SKILL.md` is at the zip root and in the tarball. The pruned-path count is `0`. The `version:` line states the new version.
⚠️ **Note**: The last line for v0.7.0 states `0.6.0`. This is the v0.7.0 defect. For a new release it states `X.Y.Z`.

Check the release notes:

```bash
gh release view vX.Y.Z --json body --jq .body | head -3
```

✅ **Success indicator**: The first line is the heading from `docs/releases/vX.Y.Z.md`.
❌ **If the first line is `## What's Changed`**: The workflow used generated notes. See [The release has generated notes](#the-release-has-generated-notes).

---

### Step 12: Verify the plugin channel

**What this does**: Confirms that the marketplace entry on `main` points at an asset that exists.

```bash
grep -n -E '"url"|"version"' .claude-plugin/marketplace.json
curl -sIL -o /dev/null -w '%{http_code}\n' \
  https://github.com/tosin2013/repo-governor/releases/download/vX.Y.Z/repo-governor-vX.Y.Z.zip
```

**Expected output** (the `curl` line, measured against `v0.7.0` on 2026-09-26):

```text
200
```

✅ **Success indicator**: The entry names `vX.Y.Z` in `url` and `version`, and `curl` prints `200`.
❌ **If `404`**: The asset is missing. The plugin channel is broken for every user. Go to [Rollback procedure](#rollback-procedure).

---

### Step 13: Verify an install from the tag, and an upgrade

**Not run in this draft.** The installer runs `git clone`, which the isolated worktree for this draft did not permit. The expected output comes from the `echo` lines in `tools/install-skill.sh`.

**What this does**: Does what a new user does, from the published tag.

```bash
rm -rf /tmp/rg-verify && mkdir -p /tmp/rg-verify/target
git -C /tmp/rg-verify/target init -q
git clone -q --branch vX.Y.Z https://github.com/tosin2013/repo-governor /tmp/rg-verify/rg
bash /tmp/rg-verify/rg/tools/install-skill.sh /tmp/rg-verify/target .agents/skills no </dev/null
grep -n ENGINE_VERSION /tmp/rg-verify/target/.agents/skills/repo-governor/engine/version.py
```

**Expected output** (excerpt):

```text
installed: /tmp/rg-verify/target/.agents/skills/repo-governor
  SKILL.md present
  pruned: AGENTS.md, CLAUDE.md, .claude/, .claude-plugin/, .repo-governor.json, .repo-governor/, docs/research/, CONTRIBUTING.md
  kept: LICENSE, NOTICE (Apache-2.0 sections 4a and 4d)
```

✅ **Success indicator**: The install prints `SKILL.md present`, and `ENGINE_VERSION` states `X.Y.Z`.

Then run the live `install` suite. It now passes, because the tag exists:

```bash
python3 conformance/install.py
```

✅ **Success indicator**: The last line is `INSTALL: CONFORMANT`.

**Upgrade check**: [Issue 258](https://github.com/tosin2013/repo-governor/issues/258) adds `docs/runbooks/upgrade-and-uninstall.md`. If that file is on `main`, do its upgrade procedure from the previous tag to `vX.Y.Z`. If it is not on `main`, write "upgrade not verified" in the release issue.

---

## Verification and success criteria

- [ ] `python3 tools/check-version.py vX.Y.Z` prints `VERSION: CONSISTENT` on `main`.
- [ ] `SKILL.md` states `version: "X.Y.Z"`.
- [ ] `docs/releases/vX.Y.Z.md` is in the tagged commit.
- [ ] `docs/adrs/RATIFICATION-vX.Y.Z.md` is in the tagged commit, if Step 2a named a dependent ADR.
- [ ] No dependent ADR has more than two releases, this one included.
- [ ] The maintainer wrote the acceptance line in the ratification record.
- [ ] `git cat-file -t vX.Y.Z` prints `tag`.
- [ ] The release workflow run shows `success`.
- [ ] The release has four assets, and both checksums are `OK`.
- [ ] The plugin zip has `SKILL.md` at its root and no pruned path.
- [ ] The marketplace URL returns `200`.
- [ ] The release page shows the notes file, not generated notes.
- [ ] An install from the tag prints `SKILL.md present`.
- [ ] `python3 conformance/install.py` prints `INSTALL: CONFORMANT`.

---

## Rollback procedure

### What can and cannot be undone

| Item | Can you undo it? | How |
|---|---|---|
| The release object and its assets | Yes | `gh release delete vX.Y.Z` |
| The tag on the remote | Yes, but other clones keep it | `gh release delete vX.Y.Z --cleanup-tag`, or `git push origin :refs/tags/vX.Y.Z` |
| Clones and downloads that people made | **No** | Nothing recalls them. |
| Decision records that cite `engine_version` X.Y.Z | **No** | They are append-only (ADR-009). |
| Plugin installs from the marketplace entry | **No** | A new release with a new pin replaces them on update. |
| The version number | **Do not reuse it** | Two different sets of bytes under one version break replay. Cut `X.Y.Z+1`. |

### When to roll back

- The workflow failed before Publish. Nothing was published.
- The workflow published a release with a wrong asset, and nobody installed it yet.
- The plugin zip ships a pruned path. This leaks the repository's own manifest to every user.

### Rollback steps

#### Case A: The workflow failed before Publish

The tag exists and no release exists.

1. Read the failure with `gh run view <run-id> --log-failed`.
2. Fix the cause on `main` through a pull request.
3. Delete the remote tag: `git push origin :refs/tags/vX.Y.Z`.
4. Delete the local tag: `git tag -d vX.Y.Z`.
5. Do Step 8 to Step 10 again on the new `main`.

#### Case B: Only the notes are wrong

The assets are correct. Replace the notes. Do not touch the tag.

```bash
gh release edit vX.Y.Z --notes-file docs/releases/vX.Y.Z.md
```

#### Case C: The assets are wrong, or the release is broken

1. Delete the release and the tag: `gh release delete vX.Y.Z --cleanup-tag --yes`.
2. Delete the local tag: `git tag -d vX.Y.Z`.
3. Fix the cause on `main`.
4. Release the fix as `X.Y.Z+1`. Do not reuse `X.Y.Z`.
5. Write in the new notes what was wrong with `X.Y.Z`.

#### Case D: Re-run the workflow for an existing tag

Use this when the workflow failed for a transient cause, such as a Dolt download error.

```bash
gh workflow run release.yml -f tag=vX.Y.Z
```

If a release object exists, Publish adopts it and uploads the assets with `--clobber`. It does not replace the notes.

---

## Troubleshooting

### Hermetic suites fail in a new worktree

**Symptoms**: `layer1`, `skill`, and `execution` fail. `skill` reports `'199 contract checks' matches the 194 layer1 runs`.

**Cause**: The decision store `.repo-governor/decisions-db/` is gitignored. A new clone or worktree does not have it, and five `layer1` capability checks do not run.

**Solution**:

```bash
./tools/bootstrap-decisions.sh
./tools/run-conformance.sh --hermetic
```

Measured on 2026-09-26: 13/16 before the bootstrap, and 16/16 after it.

---

### `roadmap` fails on an authorized issue

**Symptoms**: The live run prints `AUTHORIZED with no acceptance record: [...]`.

**Cause**: An issue has a milestone and an assignee, and no `.repo-governor/acceptance/<n>.json`.

**Solution**: Write the acceptance record for each issue named, or remove the milestone if the work is not committed. This is not a release defect, but fix it before you tag. The release notes cite the conformance result.

---

### The workflow fails at `Version strings agree with the tag`

**Cause**: A version site states a different version from the tag.

**Solution**: Run `python3 tools/check-version.py vX.Y.Z` on the tagged commit. Fix the sites on `main`, then do [Case A](#case-a-the-workflow-failed-before-publish).

---

### The workflow fails at `is not an ancestor of origin/main`

**Cause**: The tag points at a commit that is not on `main`. An example is a commit on the release branch before the merge.

**Solution**: Do [Case A](#case-a-the-workflow-failed-before-publish). Create the tag on the merge commit on `main`.

---

### The workflow fails at `a pruned path survived`

**Cause**: `tools/install-skill.sh` did not remove a path that the release check forbids.

**Solution**: Fix the prune list in `tools/install-skill.sh` and its self-check loop. `conformance/skill.py` checks that both name `.claude-plugin`. Then do [Case A](#case-a-the-workflow-failed-before-publish).

---

### The release has generated notes

**Symptoms**: The release page starts with `## What's Changed` and a list of pull requests.

**Cause**: `docs/releases/vX.Y.Z.md` was not in the tagged commit, or a draft release existed before the workflow ran.

**Solution**: Add the notes file to `main` through a pull request. Then do [Case B](#case-b-only-the-notes-are-wrong). v0.7.0 is in this state today.

---

### `install` fails in the live run before the tag

**Cause**: The pins name `vX.Y.Z`, and the remote does not have the tag yet.

**Solution**: None. This is correct. The suite passes after Step 9.

---

### Escalation path

| Problem | Action |
|---|---|
| An ADR is past the two-release expiry | Stop. The maintainer decides, reduces, or removes it (Step 2c). The release waits. |
| The workflow fails and the cause is not in this runbook | Open a [Repo Governor issue](https://github.com/tosin2013/repo-governor/issues). Attach the output of `gh run view <run-id> --log-failed`. |
| A published asset leaks a pruned path | Do [Case C](#case-c-the-assets-are-wrong-or-the-release-is-broken) at once, then open an issue. |
| The derivation in Step 2a disagrees with the ADR index or `conformance/skill.py` | Record every ADR that the derivation names. Open an issue against [issue 257](https://github.com/tosin2013/repo-governor/issues/257) or its successor. |

---

## Post-execution tasks

### Immediately

- [ ] Remove `/tmp/rg-release` and `/tmp/rg-verify`.
- [ ] Write the release URL and the workflow run id in the release issue.
- [ ] Record the Step 2b counts in the release issue.

### Before the next release

- [ ] Check each ADR with one earlier release. It expires at the next release.
- [ ] Update **Last tested** and the version history of this runbook.

---

## Appendix

### Related documents

- [ADR-035](../adrs/035-a-release-may-depend-on-a-proposed-adr-only-on-declared-and-expiring-terms.md): the release condition, the scope, and the expiry.
- [ADR-034](../adrs/034-publication-is-per-channel-and-a-listing-claims-only-what-is-calibrated.md): the plugin channel and the pruned archive.
- [ADR-027](../adrs/027-the-governed-repository-is-not-the-install-directory.md): why the install is pruned.
- [RATIFICATION-v0.6.0.md](../adrs/RATIFICATION-v0.6.0.md): the model for a ratification record.
- [v0.6.0.md](../releases/v0.6.0.md): the model for release notes.
- [release.yml](../../.github/workflows/release.yml): the workflow.
- [check-version.py](../../tools/check-version.py): the version check.
- [run-conformance.sh](../../tools/run-conformance.sh): the conformance runner.
- [installation.md](../installation.md): the install pin that readers follow.

### Release history that shaped this runbook

| Release | What went wrong | Where the runbook covers it |
|---|---|---|
| v0.2.0 | A draft release pointed at a tag that did not exist | Step 8, and the `--verify-tag` in Publish |
| v0.4.0 | `main` named a tag that did not exist, and the checks were green | Step 5, the live `install` suite |
| v0.7.0 | No notes file, `SKILL.md` at `0.6.0`, and no ratification record | Step 2d, Step 3, Step 4 |

### Version history

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0.0 | 2026-09-26 | Repo Governor maintainer, with Claude Code | First version. Read-only steps measured against v0.7.0. |

---

**Next review**: after v0.8.0 is published, or on 2026-12-26.
