#!/usr/bin/env python3
"""Layer 2 against two LIVE roadmap providers — issue #1's actual bar.

`conformance/layer2.py` runs both trackers on recorded fixtures, because ADR-008
rule 1 requires fixed inputs for determinism (C7). That is correct for a
regression gate and it is why Layer 2 alone cannot close #1: fixtures written by
one author against one mental model measure shared intent as much as
portability.

This runs the same equivalence question against real Linear and real GitHub. It
is deliberately NOT a conformance suite:

  * it is non-deterministic by construction -- the providers change under it;
  * a divergence here is a FINDING for §55, not a broken build;
  * it needs network and credentials the suites must never require.

Linear state arrives on stdin as an MCP payload, so no Linear credential is
needed by this tool or by the adapter (ADR-020, ADR-028). Nothing about the
payload is written to disk: this repository is public and §51 forbids carrying
another workspace's content into it.

    <mcp list_issues output> | python3 tools/live-equivalence.py --github <owner/repo>

Five scenarios. Two of them -- `triage` and `canceled` -- were not expressible
in either provider when this was written, and that is the point: the withdrawal
case is the one that motivated the project and the one no real workspace
happened to contain. They are listed so the gap is visible as a SKIP rather
than absent from the table entirely.

Equivalence is over SEMANTIC STATE, not over the same work item. Layer 2 has
always worked this way -- `authority_withdrawn` uses different ids in each
provider. Two providers agreeing about one shared item would test id lookup;
agreeing about equivalent states is what tests normalization.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The mapping under test. Each row is one semantic state, expressed in whatever
# each provider natively uses to mean it.
SCENARIOS = [
    ("admitted, not cleared to execute", "backlog",   {"authority": "ADMITTED", "admitted": True},
     "milestoned, unassigned"),
    ("authorized and executing",         "started",   {"authority": "AUTHORIZED", "admitted": True},
     "milestoned + assigned"),
    ("finished; authority is a separate axis", "completed",
     {"authority": "AUTHORIZED", "admitted": True}, "closed"),
    # `triage`, not None. This row previously carried `None`, which made `lid`
    # None unconditionally, which tripped the skip guard on every run: a
    # scenario that could never execute, reported forever as "not expressible
    # live". A permanently-skipped row reads like missing data and is really a
    # dead code path -- the same defect class as a vacuously passing check.
    ("not admitted at all",              "triage",    {"__unknown__": "NOT_ADMITTED"},
     "no milestone"),
    # The withdrawal case: the one that motivated the entire project, and the
    # only row here that neither provider could express when this was written.
    # Roadmap says the work is cancelled; anything still running is
    # unauthorized regardless of how much of it is finished.
    ("authority withdrawn",              "canceled",  {"authority": "CANCELLED", "admitted": False},
     "closed NOT_PLANNED"),
]


def observe(resp):
    if not resp.get("ok"):
        return {"__error__": resp.get("error", {}).get("type")}
    if resp.get("unknown"):
        return {"__unknown__": resp["unknown"]["reason"], "blocking": resp["unknown"]["blocking"]}
    return resp.get("value") or {}


def ask_linear(payload, wid):
    p = subprocess.run([sys.executable, str(ROOT / "adapters" / "linear"),
                        "query", "roadmap_authority", "get_authority", f"id={wid}", "--input", "-"],
                       input=payload, capture_output=True, text=True, cwd=ROOT, timeout=60)
    try:
        return observe(json.loads(p.stdout))
    except json.JSONDecodeError:
        return {"__error__": "NON_JSON"}


def ask_github(nwo, number):
    env = {"REPO_GOVERNOR_GH_REPO": nwo, "REPO_GOVERNOR_GH_ADMISSION": "milestone"}
    import os
    p = subprocess.run([sys.executable, str(ROOT / "adapters" / "github-projects"),
                        "query", "roadmap_authority", "get_authority", f"id={number}"],
                       capture_output=True, text=True, cwd=ROOT, timeout=90,
                       env={**os.environ, **env})
    try:
        return observe(json.loads(p.stdout))
    except json.JSONDecodeError:
        return {"__error__": "NON_JSON"}


def pick_github(nwo):
    """Real issues occupying each semantic state. Chosen from live data, not fixed."""
    out = subprocess.run(["gh", "issue", "list", "--repo", nwo, "--state", "all", "--limit", "100",
                          "--json", "number,state,stateReason,milestone,assignees"],
                         capture_output=True, text=True, timeout=90).stdout
    issues = json.loads(out or "[]")
    picks = {}
    for i in issues:
        ms, closed = bool(i.get("milestone")), i["state"] == "CLOSED"
        assigned = bool(i.get("assignees"))
        # NOT_PLANNED is how GitHub says "we decided against this", as opposed
        # to COMPLETED. Bucketing both as "closed" would have made the
        # withdrawal scenario match a merely-finished issue, which is the exact
        # confusion the completion firewall exists to prevent.
        if closed and i.get("stateReason") == "NOT_PLANNED":
            picks.setdefault("closed NOT_PLANNED", i["number"])
        elif not ms and not closed:
            picks.setdefault("no milestone", i["number"])
        elif ms and closed:
            picks.setdefault("closed", i["number"])
        elif ms and assigned and not closed:
            picks.setdefault("milestoned + assigned", i["number"])
        elif ms and not assigned and not closed:
            picks.setdefault("milestoned, unassigned", i["number"])
    return picks


def main(argv):
    if "--github" not in argv:
        print(__doc__.strip().splitlines()[-6].strip(), file=sys.stderr)
        return 2
    nwo = argv[argv.index("--github") + 1]
    payload = sys.stdin.read()
    try:
        issues = json.loads(payload)["issues"]
    except (json.JSONDecodeError, KeyError):
        print("stdin is not an MCP issues payload", file=sys.stderr)
        return 2

    by_type = {}
    for i in issues:
        by_type.setdefault(i.get("statusType"), i.get("id"))
    gh_picks = pick_github(nwo)

    print(f"Linear: {len(issues)} live issues, states {sorted(k for k in by_type if k)}")
    print(f"GitHub: {nwo}, states {sorted(gh_picks)}\n")

    agree = diverge = skipped = 0
    for meaning, ltype, expect, gh_state in SCENARIOS:
        lid = by_type.get(ltype) if ltype else None
        gid = gh_picks.get(gh_state)
        # A scenario expressible in ONE provider is not an equivalence test.
        # Counting it as agreement is how a harness reports a green number for a
        # comparison it never made -- layer2.py already refuses this, and the
        # first version of this tool did not.
        if not lid or not gid:
            print(f"[SKIP] {meaning}\n       not expressible live: "
                  f"linear={ltype or 'n/a'}:{lid} github={gh_state}:{gid}\n")
            skipped += 1
            continue
        lobs = ask_linear(payload, lid) if lid else None
        gobs = ask_github(nwo, gid)
        keys = ("authority", "admitted", "__unknown__")
        lp = {k: lobs[k] for k in keys if lobs and k in lobs}
        gp = {k: gobs[k] for k in keys if k in gobs}
        print(f"[{meaning}]")
        print(f"    linear  {ltype or '-':<10} {json.dumps(lp, sort_keys=True)}")
        print(f"    github  {gh_state:<22} {json.dumps(gp, sort_keys=True)}")
        if lp == gp:
            agree += 1
            print("    AGREE\n")
        else:
            diverge += 1
            print("    ** DIVERGENCE ** equivalent state, different typed facts\n")

    print("-" * 62)
    print(f"live scenarios: {len(SCENARIOS)}   agree: {agree}   diverge: {diverge}   skipped: {skipped}")
    # "EQUIVALENT" alone would be a flattering headline over a run where two of
    # five scenarios never executed. Equivalence is only claimed for what was
    # actually compared; the skipped count rides along with the verdict so it
    # cannot be quoted without it.
    scope = f"across {agree + diverge} of {len(SCENARIOS)} scenarios"
    if skipped:
        scope += f" ({skipped} not expressible in these providers)"
    print("\nLIVE EQUIVALENCE: " + ("EQUIVALENT " if not diverge else "NOT EQUIVALENT ") + scope)
    if diverge:
        print("A divergence is a §55 stop-condition input, not a build failure. Record it.")
    return 0 if not diverge else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
