---
name: github-project-release-manager
description: Manage the GitHub Project board and release process for the current repo using the gh CLI. Use when asked to manage github project, set up or sync project board, triage issues into project, check milestone progress, prepare release, cut a release, draft release notes, recommend a version bump, update CHANGELOG, or report project and release status.
---

Act as a technical Project Manager and Release Manager working GitHub-natively via the `gh` CLI.

**Never re-create structure that already exists.** Every invocation starts by running the detection driver, which decides Setup vs Operational mode from the repo's actual state.

All paths are relative to the repository root. The driver is `.claude/skills/github-project-release-manager/detect.sh`.

## Prerequisites

```bash
gh --version          # GitHub CLI
gh auth status        # must be authenticated
jq --version          # used for the config marker
```

Authenticate if needed:

```bash
gh auth login
```

**Reading Projects needs `read:project`. Writing to Projects needs `project`.** Check before promising board mutations:

```bash
gh auth status 2>&1 | grep -i 'token scopes'
```

If `'project'` is absent, board writes will fail. Get it with:

```bash
gh auth refresh -s project -h github.com
```

**`--hostname` is required whenever this runs non-interactively** — without it `gh` exits with `--hostname required when not running interactively` and prints usage. This is an OAuth device flow: it prints a one-time code to enter at `github.com/login/device`, so an agent cannot complete it. Hand the command to the user rather than attempting it.

## Step 1 — Always run the driver first

```bash
./.claude/skills/github-project-release-manager/detect.sh
```

Read-only. Makes no writes. Safe to run repeatedly.

Real output from a fresh solo repo:

```text
repo               : tosin2013/repo-governor
MODE               : setup  (no config marker, no linked project, no releases/tags/milestones)
project write scope: false  (scopes: 'gist', 'read:org', 'read:project', 'repo', 'workflow')
--- structure ---
config marker      : false (.github/project-config.json)
linked projects    : 0  []
releases / tags    : 0 / 0   last: none / none
open milestones    : 0
CHANGELOG.md       : false
workflows          : 0 (release automation: false, config: false)
--- activity ---
commits (90d)      : 1
contributors       : 1
open issues / PRs  : 0 / 0
PRs merged (30d)   : 0
--- recommendation ---
complexity score   : 0/8
board              : none
release process    : none
```

For scripting, use `--json` and parse with `jq`:

```bash
./.claude/skills/github-project-release-manager/detect.sh --json > /tmp/snap.json
jq -r '.mode, .board_recommendation, .release_recommendation' /tmp/snap.json
```

| field | meaning |
|---|---|
| `mode` | `setup` or `operational` — obey it |
| `project_write_scope` | `false` → board mutations will fail; say so, don't attempt |
| `linked_projects` | projects actually linked to this repo (not all your projects) |
| `complexity_score` | 0–8; drives the board recommendation. **Measures coordination need** — contributors, open items, activity — **not tracking need.** A solo repository under heavy development scores low and may still warrant a board. |
| `board_decided` / `release_decided` | the decision **recorded in the marker**. When present it **outranks** the computed recommendation — report it, do not re-argue it |
| `board_recommendation` | `none` / `lightweight` / `full` |
| `release_recommendation` | `none` / `milestone` / `automated` |

**Enter Setup mode only when `mode` is `setup`, or when the user explicitly asks for a re-evaluation.** Otherwise go to Operational mode.

**A recorded decision outranks the computed recommendation.** When `board_decided` is set, the driver prints it and flags any divergence:

```text
board (decided)    : full  [human override]
                     computed would be 'none'; the recorded decision governs.
```

Report the decision. Do not re-open the question — a driver that surfaces only its own computation asks the human to re-litigate a settled choice every run, which is how a parallel decision surface starts.

## Step 2a — Setup mode

Run only on first setup or explicit re-evaluation.

### Decide the board — bias hard toward none

Take `complexity_score` from the driver:

| score | decision | what to create |
|---|---|---|
| 0–2 | **none** | No Project. Record the decision and stop. |
| 3–4 | **lightweight** | User-level Project with `Status` + `Priority` only. |
| 5–8 | **full** | Project with `Status`, `Priority`, `Size`, `Target date`, plus a board view and a table view. |

Do not create a Project for a solo repo with few open items. A board nobody reads is worse than no board. When the score says `none`, say so plainly and write the marker — that is a complete, successful Setup run.

Create only when warranted:

```bash
gh project create --owner "@me" --title "<repo> roadmap" --format json
```

Link it to the repo. **Use the literal login, not `@me`** (see Gotchas):

```bash
gh project link <number> --owner <login> --repo <owner>/<repo>
```

Add fields only for `full`:

```bash
gh project field-create <number> --owner <login> --name "Priority" \
  --data-type SINGLE_SELECT --single-select-options "P0,P1,P2"
gh project field-create <number> --owner <login> --name "Size" \
  --data-type SINGLE_SELECT --single-select-options "XS,S,M,L"
```

Enable the built-in workflows (auto-add items, auto-set status on close) in the Project's UI settings — `gh` cannot configure Project workflows.

### Decide the release process — lightest that works

| situation | decision |
|---|---|
| No shipped artifact, or spec/docs only | **none** — do not create tags or a CHANGELOG |
| Ships occasionally, humans decide versions | **milestone** — version-named milestones + `gh release create --generate-notes` |
| Frequent releases, conventional commits already in use | **automated** — release-please or semantic-release |
| Signed artifacts, matrix builds, staged rollout | **full** — only when actually required |

Create a milestone only if the decision is `milestone` or heavier:

```bash
gh api repos/<owner>/<repo>/milestones -f title="v0.1.0" -f state=open
```

### Write the marker — always, even when both decisions are "none"

This is what makes the next invocation Operational. Record the decision **and** what would change it.

```bash
mkdir -p .github
cat > .github/project-config.json <<'EOF'
{
  "$comment": "Marker for the github-project-release-manager skill. Presence => Operational mode; do not re-run setup analysis.",
  "version": 1,
  "evaluated_at": "YYYY-MM-DD",
  "repo": "<owner>/<repo>",
  "board": {
    "decision": "none",
    "reason": "<why, citing the score and the numbers behind it>",
    "revisit_when": "contributors > 2, or open issues+PRs > 5, or first release cut"
  },
  "release": {
    "decision": "none",
    "reason": "<why>",
    "revisit_when": "<concrete trigger>"
  }
}
EOF
jq -e . .github/project-config.json >/dev/null && echo "marker valid"
```

Verify the flip before reporting success:

```bash
./.claude/skills/github-project-release-manager/detect.sh | head -2
# MODE : operational  (config marker present at .github/project-config.json)
```

## Step 2b — Operational mode

Default for every repeat call. Do useful maintenance. **Do not re-analyze whether a board should exist** unless asked.

Pick the work that matches the request. When the request is vague, check milestone risk and triage, then report.

### Triage untriaged issues

```bash
gh issue list --state open --search "no:label" --limit 20
gh issue list --state open --search "no:milestone" --limit 20
```

Apply labels and milestones:

```bash
gh issue edit <n> --add-label "bug" --milestone "v0.1.0"
```

Add to the board (needs `project` scope):

```bash
gh project item-add <number> --owner <login> --url https://github.com/<owner>/<repo>/issues/<n>
```

### Sync board status

List items and their current status:

```bash
gh project item-list <number> --owner <login> --limit 100 --format json \
  | jq -r '.items[] | "\(.content.number // "-")\t\(.status // "no status")\t\(.content.title)"'
```

**`--limit` is not optional.** Without it the command returns 30 items and says nothing about the rest — see Gotchas.

Flag mismatches — a closed issue still in `In Progress`, a merged PR not marked `Done` — and fix them, or report them when write scope is missing.

### Check milestone progress

```bash
gh api repos/<owner>/<repo>/milestones \
  --jq '.[] | "\(.title): \(.closed_issues)/\(.open_issues + .closed_issues) due \(.due_on // "none")"'
```

Flag as at-risk any milestone whose due date is near with open issues remaining.

### Recommend a version bump

Scan commits since the last tag. `git describe` fails on a repo with no tags, so fall back to full history:

```bash
RANGE=$(git describe --tags --abbrev=0 2>/dev/null | sed 's/$/../'); RANGE=${RANGE:-HEAD}
echo "range: ${RANGE:-all history}"
git log ${RANGE} --format='%s' | grep -cE '^feat(\(.+\))?!?:'
git log ${RANGE} --format='%s' | grep -cE '^fix(\(.+\))?!?:'
git log ${RANGE} --format='%s' | grep -cE '(^[a-z]+(\(.+\))?!:|BREAKING CHANGE)'
```

Breaking > 0 → major (or minor while `0.x`). Any `feat` → minor. Only `fix` → patch. If commits are not conventional, read the merged PR titles instead and say the recommendation is judgment-based.

### Draft release notes without creating anything

This API generates notes and writes nothing:

```bash
gh api repos/<owner>/<repo>/releases/generate-notes \
  -f tag_name=v0.1.0 -f target_commitish=main --jq '.body'
```

For the human-written summary, list what merged:

```bash
gh pr list --state merged --limit 100 \
  --search "merged:>=$(date -v-30d +%Y-%m-%d 2>/dev/null || date -d '30 days ago' +%Y-%m-%d)" \
  --json number,title,author --jq '.[] | "- \(.title) (#\(.number)) @\(.author.login)"'
```

### Cut the release — only on explicit approval

Creating a release is public and hard to undo. Confirm the version with the user first, then:

```bash
gh release create v0.1.0 --generate-notes --draft --title "v0.1.0"
```

Keep `--draft` unless the user asked to publish. Publish separately:

```bash
gh release edit v0.1.0 --draft=false
```

## Output format

Report in this order, every time:

1. **Mode** — Setup or Operational, with the driver's one-line reason.
2. **Current snapshot** — repo, board/release structure, activity numbers that matter.
3. **Actions taken / recommendations** — what changed, or what should happen next.
4. **Release status** — progress to next release, suggested version, blockers. Omit when no release process exists.
5. **Config update** — only when something material changed.

## Rules

- Prefer the simplest thing that works. Recommending "none" is a valid, complete outcome.
- Be idempotent. Check before creating; never produce a second Project, milestone, or marker.
- Ground every claim in driver output or a `gh` command you ran. Do not assert board state you did not read.
- In Operational mode, when unsure, do maintenance rather than re-architecting.
- Confirm before public, hard-to-undo actions: publishing a release, deleting items, closing issues in bulk.
- When `project_write_scope` is `false`, report what you would change and give the `gh auth refresh -s project` command. Do not attempt the write.

## Gotchas

These were all hit while building this skill.

- **`gh project link --owner "@me"` fails** with `'owner/repo' has different owner from '@me'`. `gh` compares the `--repo` owner string against the literal `@me` instead of resolving it. Use the real login: `--owner tosin2013`.
- **`gh project link` succeeds silently and exits 0** — no output on success. It also works with only `read:project`. You cannot tell success from a no-op by exit code; verify with the GraphQL query below.
- **`gh project item-list` defaults to `--limit 30`, and silently truncates.** Observed 2026-08-19 on this repository: the board appeared to "stop at issue 30", and comparing that list against `gh issue list` produced a confident, wrong diagnosis that 14 issues were missing from the board. The board held 34. Always pass `--limit` well above the item count before comparing board membership to anything:
  ```bash
  gh project item-list <n> --owner <login> --limit 200 --format json
  ```
  The failure mode is nasty because truncation looks exactly like a real gap, and the remedy for a real gap — adding items — is harmless enough that you may never notice you were wrong. Check the item count against `--limit` before believing a diff.

- **`gh project list` shows every project you own, not this repo's.** Two untitled projects on an account are common. The only reliable repo↔project check is:
  ```bash
  gh api graphql -f query='query{ repository(owner:"<owner>", name:"<repo>"){ projectsV2(first:20){ nodes{ number title url } } } }' \
    --jq '.data.repository.projectsV2.nodes[]?'
  ```
- **`gh release list`, `gh issue list`, and `gh pr list` print nothing and exit 0 when empty.** Never branch on their exit code. Count lines: `gh release list | grep -c .`.
- **`read:project` covers more than it looks, but not board mutations.** Verified on this repo: `gh project link` and every `list`/`view` command succeed with `read:project` alone, because linking is a repository-side operation. **`gh project item-edit` fails**, because setting a field value is a Project mutation:
  ```text
  $ gh project item-edit --id PVTI_... --field-id PVTSSF_... --single-select-option-id ...
  exit=1
  error: your authentication token is missing required scopes [project]
  ```
  So "can I read the board?" and "can I change the board?" are different questions. Test the actual write before promising it — `gh project list` succeeding proves nothing about `item-edit`.

  After `gh auth refresh -s project -h github.com`, note the scope list shows `'project'` and **no longer shows `'read:project'`** — the refresh replaces the narrower scope rather than adding to it. Detect write capability by looking for `'project'`, not by counting scopes.
- **`read:project` is not enough to write.** The failure is a GraphQL error, not a non-zero CLI exit in every path:
  ```text
  INSUFFICIENT_SCOPES ... The 'updateProjectV2' field requires one of the
  following scopes: ['project'], but your token has only been granted the:
  ['gist','read:org','read:project','repo','workflow'] scopes.
  ```
- **`$?` after a pipe is the last command's status.** `gh ... | head` always reports `head`'s exit code. Capture first: `out=$(gh ... 2>&1); rc=$?`.
- **A trailing `[ a != b ] && echo …` sets the script's exit status.** Found in this driver: the "recorded decision diverges from computed" lines were the last commands, so every *healthy* run where the two agreed exited 1 — indistinguishable from a failure, on a script whose exit codes are contractual (3 = degraded API). End such a script with an explicit `exit 0`.
- **`git describe --tags` exits non-zero on a repo with no tags.** Always `2>/dev/null` with a fallback, or the whole script dies under `set -e`.
- **`date -d` is GNU-only.** macOS needs `date -v-30d`. Use `date -v-30d +%Y-%m-%d 2>/dev/null || date -d '30 days ago' +%Y-%m-%d`.
- **During a GitHub incident, writes report success and silently do not take.** Verified 2026-08-17 during a partial outage: `gh issue reopen 17` printed `✓ Reopened issue` and exited 0, and three subsequent reads showed the issue still `CLOSED`. Never trust a write's success message during degraded service — read the state back before reporting.
- **A degraded API makes `gh issue list` return nothing, which is indistinguishable from an empty repo.** Same outage: consecutive runs returned 16, then 0, then 16 open issues, with `HTTP 503` on the GraphQL endpoint while REST still answered. `detect.sh` now gates on **both** endpoints and exits 3 rather than reporting a wrong count. Without that gate a degraded API reads as a quiet repo, and the complexity score is confidently wrong.
- **Closing keywords in commit messages fire anywhere in the message, and quoting does not escape them.** Verified twice on the same issue. First a message beginning `Clos` + `e #NN defect` — meaning "close the NN defect" — closed it. Then the commit *documenting that gotcha* closed it again, because the explanation quoted the offending string. Backticks, single quotes and surrounding prose all still parse. **Never put a closing verb adjacent to a `#` reference in a commit message, even inside a quotation.** Write the number without the hash, or separate them: `the closing-keyword trap on issue NN`.
- **`gh project item-list` silently caps at 30 items.** No warning, no pagination hint, exit 0 — a truncated board reads exactly like a complete one. This produced three false "0 drift across 30 items" reconciliation reports on a 33-item board, each of which looked like a clean bill of health. It is the same failure family as the degraded-API case below: **a partial answer presented as a total one.** Always pass `--limit`, and cross-check the count against `gh issue list --state all --limit 100` rather than trusting either number alone:
  ```bash
  gh project item-list <n> --owner <login> --limit 100 --format json | jq '.items | length'   # 33
  gh project item-list <n> --owner <login> --format json | jq '.items | length'               # 30
  ```
- **`gh` cannot configure Project built-in workflows.** Auto-add and auto-archive must be enabled in the web UI. Say this rather than silently skipping it.

## Troubleshooting

- **`FATAL: gh not authenticated`** — run `gh auth login`.
- **`FATAL: no GitHub remote resolved`** — the repo has no GitHub remote. `git remote add origin https://github.com/<owner>/<repo>.git`.
- **`'owner/repo' has different owner from '@me'`** — replace `@me` with the literal login in `--owner`.
- **`INSUFFICIENT_SCOPES ... requires ['project']`** — the user must run `gh auth refresh -s project -h github.com`, then retry. An agent cannot do this: it is a browser device flow.
- **`--hostname required when not running interactively`** — `gh auth refresh` was run without `-h github.com`. Add it.
- **Driver reports `setup` on a repo you already configured** — the marker is missing or invalid. Check `jq -e . .github/project-config.json`; recreate it rather than re-running setup analysis.
- **`could not resolve to a Repository`** — the token lacks `repo` scope for a private repo, or the name is wrong. Verify with `gh repo view --json nameWithOwner`.
