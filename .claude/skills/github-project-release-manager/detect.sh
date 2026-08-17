#!/usr/bin/env bash
# detect.sh — read-only repository snapshot + mode decision.
#
# Makes NO writes. Safe to run repeatedly.
# Usage:  ./detect.sh          human-readable
#         ./detect.sh --json   machine-readable
set -uo pipefail

JSON=0
[ "${1:-}" = "--json" ] && JSON=1

command -v gh >/dev/null || { echo "FATAL: gh not installed" >&2; exit 2; }
gh auth status >/dev/null 2>&1 || { echo "FATAL: gh not authenticated. Run: gh auth login" >&2; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "FATAL: not a git repository" >&2; exit 2; }

# Resolve the repo LOCALLY first. `gh repo view` needs the API, and during an
# incident it returns empty -- which read as "no remote configured" and made
# the driver exit 2 with a wrong reason. Local git always answers.
ORIGIN=$(git remote get-url origin 2>/dev/null)
if [ -z "$ORIGIN" ]; then
  echo "FATAL: no git remote 'origin' configured" >&2
  echo "  git remote add origin https://github.com/<owner>/<repo>.git" >&2
  exit 2
fi
case "$ORIGIN" in
  *github.com[:/]*) NWO=$(printf '%s' "$ORIGIN" | sed -E 's#.*github\.com[:/]##; s#\.git$##') ;;
  *) echo "FATAL: origin is not a GitHub remote: $ORIGIN" >&2; exit 2 ;;
esac
[ -n "$NWO" ] || { echo "FATAL: could not parse owner/repo from $ORIGIN" >&2; exit 2; }

# API health gate. Without this a 5xx makes `gh issue list` print nothing,
# which `grep -c .` reports as 0 -- a degraded API becomes "quiet repo" and
# every downstream count and the complexity score are silently wrong.
# Same rule ADR-008 C3 imposes on adapters: typed failure, never a plausible
# empty result. Verified against a real GitHub partial outage 2026-08-17.
# Check BOTH endpoints: `gh issue list` / `pr list` go through GraphQL, and
# during the 2026-08-17 outage REST answered while GraphQL returned 503.
API_ERR=$(gh api repos/"$NWO" --jq .name 2>&1 >/dev/null)
[ -n "$API_ERR" ] || API_ERR=$(gh api graphql -f query='query{viewer{login}}' --jq .data.viewer.login 2>&1 >/dev/null)
if [ -n "$API_ERR" ]; then
  echo "FATAL: GitHub API is not answering reliably -- refusing to report state." >&2
  echo "  $API_ERR" >&2
  echo "  Check https://www.githubstatus.com/ and retry. Counts would be wrong, not missing." >&2
  exit 3
fi
OWNER=${NWO%%/*}
REPO=${NWO##*/}

SCOPES=$(gh auth status 2>&1 | sed -n 's/.*Token scopes: //p' | head -1)
case "$SCOPES" in *"'project'"*) PROJECT_WRITE=true ;; *) PROJECT_WRITE=false ;; esac

# --- linked projects: the only reliable repo<->project link check -------------
LINKED=$(gh api graphql -f query="query{ repository(owner:\"$OWNER\", name:\"$REPO\"){ projectsV2(first:20){ nodes{ number title url } } } }" \
  --jq '[.data.repository.projectsV2.nodes[]? | {number,title,url}]' 2>/dev/null)
[ -n "$LINKED" ] || LINKED='[]'
LINKED_N=$(printf '%s' "$LINKED" | grep -o '"number"' | wc -l | tr -d ' ')

# --- config marker ------------------------------------------------------------
CONFIG_PATH=".github/project-config.json"
if [ -f "$CONFIG_PATH" ]; then HAS_CONFIG=true; else HAS_CONFIG=false; fi

# --- release markers ----------------------------------------------------------
# NOTE: `gh release list` prints nothing and exits 0 when empty — count lines.
REL_N=$(gh release list --limit 100 2>/dev/null | grep -c . || true)
LAST_REL=$(gh release list --limit 1 2>/dev/null | awk -F'\t' 'NR==1{print $1}')
TAG_N=$(git tag -l | grep -c . || true)
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
MS_OPEN=$(gh api "repos/$NWO/milestones?state=open" --jq 'length' 2>/dev/null || echo 0)
[ -f CHANGELOG.md ] && HAS_CHANGELOG=true || HAS_CHANGELOG=false

WF_N=0; [ -d .github/workflows ] && WF_N=$(ls -1 .github/workflows 2>/dev/null | grep -c . || true)
REL_WF=false
if [ -d .github/workflows ] && grep -rlqiE 'release-please|semantic-release|softprops/action-gh-release|gh release create' .github/workflows 2>/dev/null; then
  REL_WF=true
fi
AUTO_CFG=false
for f in release-please-config.json .release-please-manifest.json .releaserc .releaserc.json .releaserc.yaml release.config.js; do
  [ -e "$f" ] && AUTO_CFG=true
done

# --- activity -----------------------------------------------------------------
COMMITS_90=$(git log --since=90.days --oneline 2>/dev/null | grep -c . || true)
CONTRIB=$(git log --since=180.days --format='%ae' 2>/dev/null | sort -u | grep -c . || true)
[ "$CONTRIB" -eq 0 ] && CONTRIB=$(git log --format='%ae' 2>/dev/null | sort -u | grep -c . || true)
ISSUES_OPEN=$(gh issue list --state open --limit 200 2>/dev/null | grep -c . || true)
PRS_OPEN=$(gh pr list --state open --limit 200 2>/dev/null | grep -c . || true)
PRS_MERGED_30=$(gh pr list --state merged --limit 100 --search "merged:>=$(date -v-30d +%Y-%m-%d 2>/dev/null || date -d '30 days ago' +%Y-%m-%d)" 2>/dev/null | grep -c . || true)

# --- complexity score (biased toward minimalism) ------------------------------
SCORE=0
[ "$CONTRIB" -gt 2 ]  && SCORE=$((SCORE+2))
[ "$((ISSUES_OPEN+PRS_OPEN))" -gt 15 ] && SCORE=$((SCORE+2))
[ "$((ISSUES_OPEN+PRS_OPEN))" -gt 5 ] && [ "$((ISSUES_OPEN+PRS_OPEN))" -le 15 ] && SCORE=$((SCORE+1))
[ "$COMMITS_90" -gt 100 ] && SCORE=$((SCORE+2))
[ "$COMMITS_90" -gt 20 ] && [ "$COMMITS_90" -le 100 ] && SCORE=$((SCORE+1))
[ "$REL_N" -gt 0 ] && SCORE=$((SCORE+1))
[ "$WF_N" -gt 1 ] && SCORE=$((SCORE+1))

if   [ "$SCORE" -le 2 ]; then BOARD_REC="none"
elif [ "$SCORE" -le 4 ]; then BOARD_REC="lightweight"
else                          BOARD_REC="full"; fi

if   [ "$AUTO_CFG" = true ] || [ "$REL_WF" = true ]; then REL_REC="automated"
elif [ "$REL_N" -gt 0 ] || [ "$TAG_N" -gt 0 ] || [ "$MS_OPEN" -gt 0 ]; then REL_REC="milestone"
else REL_REC="none"; fi

# --- mode ---------------------------------------------------------------------
if [ "$HAS_CONFIG" = true ] || [ "$LINKED_N" -gt 0 ] || [ "$REL_N" -gt 0 ] || [ "$TAG_N" -gt 0 ] || [ "$MS_OPEN" -gt 0 ]; then
  MODE="operational"
  case "$HAS_CONFIG:$LINKED_N" in
    true:*) WHY="config marker present at $CONFIG_PATH" ;;
    *:0)    WHY="release markers exist (releases=$REL_N tags=$TAG_N milestones=$MS_OPEN)" ;;
    *)      WHY="$LINKED_N project(s) linked to $NWO" ;;
  esac
else
  MODE="setup"; WHY="no config marker, no linked project, no releases/tags/milestones"
fi

if [ "$JSON" -eq 1 ]; then
  cat <<EOF
{
  "repo": "$NWO",
  "mode": "$MODE",
  "mode_reason": "$WHY",
  "project_write_scope": $PROJECT_WRITE,
  "has_config_marker": $HAS_CONFIG,
  "linked_projects": $LINKED,
  "releases": $REL_N,
  "last_release": "$LAST_REL",
  "tags": $TAG_N,
  "last_tag": "$LAST_TAG",
  "open_milestones": $MS_OPEN,
  "has_changelog": $HAS_CHANGELOG,
  "workflows": $WF_N,
  "release_workflow": $REL_WF,
  "automation_config": $AUTO_CFG,
  "commits_90d": $COMMITS_90,
  "contributors": $CONTRIB,
  "open_issues": $ISSUES_OPEN,
  "open_prs": $PRS_OPEN,
  "prs_merged_30d": $PRS_MERGED_30,
  "complexity_score": $SCORE,
  "board_recommendation": "$BOARD_REC",
  "release_recommendation": "$REL_REC"
}
EOF
else
  echo "repo               : $NWO"
  echo "MODE               : $MODE  ($WHY)"
  echo "project write scope: $PROJECT_WRITE  (scopes: $SCOPES)"
  echo "--- structure ---"
  echo "config marker      : $HAS_CONFIG ($CONFIG_PATH)"
  echo "linked projects    : $LINKED_N  $LINKED"
  echo "releases / tags    : $REL_N / $TAG_N   last: ${LAST_REL:-none} / ${LAST_TAG:-none}"
  echo "open milestones    : $MS_OPEN"
  echo "CHANGELOG.md       : $HAS_CHANGELOG"
  echo "workflows          : $WF_N (release automation: $REL_WF, config: $AUTO_CFG)"
  echo "--- activity ---"
  echo "commits (90d)      : $COMMITS_90"
  echo "contributors       : $CONTRIB"
  echo "open issues / PRs  : $ISSUES_OPEN / $PRS_OPEN"
  echo "PRs merged (30d)   : $PRS_MERGED_30"
  echo "--- recommendation ---"
  echo "complexity score   : $SCORE/8"
  echo "board              : $BOARD_REC"
  echo "release process    : $REL_REC"
fi
