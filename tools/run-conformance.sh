#!/usr/bin/env bash
# Run the conformance suites, and FAIL when any of them fails.
#
# Why this exists. The loop it replaces was published in CONTRIBUTING.md,
# docs/installation.md and AGENTS.md as the gate to run before opening a PR:
#
#     python3 conformance/$s.py >/dev/null 2>&1 && echo PASS || echo FAIL
#
# It prints FAIL and exits 0. Always. "Expect 10/10" was enforced by the reader
# noticing a word go by. That is the exact defect this repository has fixed six
# times inside its own suites -- a check that cannot fail is worse than no
# check, because it reports safety it never established -- sitting in its own
# contributor instructions.
#
# One runner, called by CI and quoted by the docs, so the two cannot drift.
#
# Usage:
#   ./tools/run-conformance.sh                 all suites
#   ./tools/run-conformance.sh --hermetic      everything that needs no network
#   ./tools/run-conformance.sh envelope skill  just these

# NOT `set -e`. A failing suite must be RECORDED and the run continued, so one
# early failure does not hide five later ones. `set -e` here would report the
# first defect and call it the only one.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

# Run the suites in a clean environment, whoever invoked them.
#
# engine/bindings.py::_env_for exports REPO_GOVERNOR_TARGET, _SUBJECT and
# _BINDING into EVERY adapter subprocess. So when the engine evaluates a
# `command_exit` acceptance criterion whose target is this script, the suites
# inherit them -- and two of them correctly go red, because they assert that an
# UNGOVERNED repository gets silence and the inherited target makes the hook
# speak about a repository it is not standing in.
#
# Those failures are real; the environment is what is wrong. A harness that
# reports differently depending on who ran it is not a harness. Suites that
# genuinely need targeting set it themselves, per subprocess (conformance/
# bindings.py does exactly that), so scrubbing here hides nothing.
unset REPO_GOVERNOR_TARGET REPO_GOVERNOR_SUBJECT REPO_GOVERNOR_BINDING

# `hooks` is last and deliberately separate: it runs engine/completion.py
# against the LIVE repository (conformance/hooks.py:163), so its verdict
# depends on issue 36's current milestone and assignee. Someone moving a card
# on the board would turn it red with no code change, which is why --hermetic
# exists and why CI runs it as a non-blocking job.
HERMETIC=(layer1 layer2 transport manifest onboarding vocabulary bindings skill envelope execution imports status acceptance)
LIVE=(hooks)

case "${1:-}" in
  --hermetic) SUITES=("${HERMETIC[@]}"); shift ;;
  --live)     SUITES=("${LIVE[@]}");     shift ;;
  -h|--help)  sed -n '2,25p' "$0"; exit 0 ;;
  "")         SUITES=("${HERMETIC[@]}" "${LIVE[@]}") ;;
  *)          SUITES=("$@") ;;
esac

# A named suite that does not exist must be an error, not a silent skip. A
# runner that quietly ignores a typo reports "all pass" over a set the caller
# did not get -- vacuous green by a different route.
missing=0
for s in "${SUITES[@]}"; do
  [ -f "conformance/$s.py" ] || { echo "no such suite: conformance/$s.py" >&2; missing=1; }
done
[ "$missing" -eq 0 ] || exit 2

failed=()
for s in "${SUITES[@]}"; do
  printf '%-12s ' "$s"
  # Output is captured rather than discarded: on failure it is REPLAYED below.
  # `>/dev/null 2>&1` is what made the old loop useless to debug -- you learned
  # that something failed and nothing about what.
  out="$(python3 "conformance/$s.py" 2>&1)"; rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "PASS"
  else
    echo "FAIL (exit $rc)"
    failed+=("$s")
    printf '%s\n' "$out" | sed 's/^/  | /'
  fi
done

echo
if [ "${#failed[@]}" -eq 0 ]; then
  echo "${#SUITES[@]}/${#SUITES[@]} pass"
  exit 0
fi
echo "$(( ${#SUITES[@]} - ${#failed[@]} ))/${#SUITES[@]} pass -- FAILED: ${failed[*]}"
exit 1
