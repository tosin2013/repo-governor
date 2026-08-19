#!/usr/bin/env python3
"""The status report tells the truth about what it cannot do (issue 57).

A report is easy to make green: print less. So these checks are mostly about
ABSENCE being reported rather than omitted -- the same distinction ADR-008 C4
makes for adapters, applied to the surface a human reads.

The one that matters most is the last: a repository with no acceptance criteria
must be TOLD that STOP_COMPLETE is unreachable. That is the condition under
which the completion firewall silently never fires, it is the state every
freshly onboarded repository is in, and a status view that omitted it would be
hiding the single most important thing about the repository it is describing.

Usage:  python3 conformance/status.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import _count as _CNT  # noqa: E402 -- alias avoids `C`, already bound to
# `completion` in two suites, where the collision silently rebound it (issue 67).
_CNT.watch("status")


ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "engine" / "status.py"
SCHEMA = ROOT / "schemas" / "manifest-v1.json"


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"\n         {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def run(path, env_extra=None):
    env = dict(os.environ)
    env.pop("REPO_GOVERNOR_TARGET", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, str(STATUS), str(path)],
                       capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=120)
    return p.returncode, p.stdout + p.stderr


def bare_repo(td, *, manifest=None, criteria=None):
    r = Path(td) / "repo"
    (r / ".repo-governor").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(r)], capture_output=True)
    subprocess.run(["git", "-C", str(r), "remote", "add", "origin",
                    "https://github.com/acme/widget.git"], capture_output=True)
    (r / "roadmap.json").write_text(json.dumps(
        {"items": [{"id": "W-1", "title": "x", "status": "IN_PROGRESS",
                    "authority": "AUTHORIZED", "admitted": True,
                    "scope": [], "non_goals": [], "acceptance_conditions": []}]}))
    if manifest is not None:
        (r / ".repo-governor.json").write_text(json.dumps(manifest))
    for cid in (criteria or []):
        d = r / ".repo-governor" / "acceptance"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{cid}.json").write_text(json.dumps(
            {"authority_id": cid, "criteria": [{"check": "file_exists", "target": "README.md"}]}))
    return r


MINIMAL = {
    "repo_governor": {"version": 1, "engine_min_version": "0.1.0"},
    "repository": {"id": "acme/widget"},
    "condition": {"assessed": "L1", "profile": "GOVERNOR_LITE"},
    "permissions": {"repository": {"read": True, "write": False},
                    "roadmap_authority": {"read": True, "write": False}},
    "providers": {
        "repository": {"type": "git", "adapter": "adapters/git", "contract_version": 1},
        "roadmap_authority": {"type": "file-roadmap", "adapter": "adapters/file-roadmap",
                              "contract_version": 1,
                              "env": {"REPO_GOVERNOR_ROADMAP": "roadmap.json"}},
    },
}


def main():
    fails = 0
    print("Every role the schema defines appears, bound or not\n")

    rc, out = run(ROOT)
    fails += check("it runs against this repository", rc == 0, out[-400:])

    schema_roles = sorted(
        k for k in json.loads(SCHEMA.read_text())["properties"]["providers"]["properties"]
        if not k.startswith("$"))
    fails += check(f"the schema still defines a role set ({len(schema_roles)})",
                   len(schema_roles) >= 6,
                   "if this is empty every check below passes having compared nothing")
    missing = [r for r in schema_roles if r not in out]
    fails += check("every schema role is named in the report", not missing,
                   f"{missing} — a role omitted from the report is a governance question "
                   "the reader does not know went unasked")

    print("\nUnbound is reported, not omitted\n")
    with tempfile.TemporaryDirectory() as td:
        r = bare_repo(td, manifest=MINIMAL)
        rc, out = run(r)
        fails += check("a two-role repository still reports", rc == 0, out[-300:])
        for role in ("decision_history", "acceptance_criteria", "architecture"):
            fails += check(f"{role} is named as unbound", f"{role}" in out and "UNBOUND" in out,
                           "silence about an unbound role reads as a bound one")
        fails += check("INV-013 is cited for the unbound state", "INV-013" in out,
                       "an unbound provider has no governance function; say why")

        # THE CHECK THIS SUITE EXISTS FOR.
        fails += check("STOP_COMPLETE is reported UNREACHABLE with no criteria",
                       "STOP_COMPLETE" in out and "NOT reachable" in out,
                       "every freshly onboarded repository is in this state, and a report "
                       "that omits it hides the completion firewall never firing")
        fails += check("the record path is reported unreachable with decision_history unbound",
                       "CAPTURE_ONLY" in out and "nowhere to write" in out,
                       "CAPTURE_ONLY is the DEFAULT disposition; if it cannot record, say so")

    print("\nDeclaring criteria changes the answer\n")
    with tempfile.TemporaryDirectory() as td:
        r = bare_repo(td, manifest=MINIMAL, criteria=["W-1"])
        rc, out = run(r)
        seg = out.split("WHAT THIS REPOSITORY CAN CONCLUDE")[-1].split("LOCAL EVIDENCE")[0]
        line = [l for l in seg.splitlines() if "STOP_COMPLETE" in l]
        fails += check("with criteria present, STOP_COMPLETE reads reachable",
                       bool(line) and "NOT reachable" not in line[0],
                       f"{line} — otherwise the check above passes for a reason unrelated "
                       "to criteria, and neither line means anything")

    print("\nIt is not silently green\n")
    with tempfile.TemporaryDirectory() as td:
        r = bare_repo(td, manifest=None)          # no manifest at all
        rc, out = run(r)
        fails += check("an un-onboarded repository exits non-zero", rc != 0, f"rc={rc}")
        fails += check("and names what was missing", "AUTHORITY_SOURCE_MISSING" in out
                       or "MANIFEST INVALID" in out, out[-200:])
    with tempfile.TemporaryDirectory() as td:
        broken = dict(MINIMAL); broken["repo_governor"] = {"version": 99}
        r = bare_repo(td, manifest=broken)
        rc, out = run(r)
        fails += check("an unreadable manifest exits non-zero rather than reporting from it",
                       rc != 0, f"rc={rc}")

    print("\nObligation facts are reported, and gate nothing\n")

    with tempfile.TemporaryDirectory() as td:
        r = bare_repo(td, manifest=MINIMAL)          # no LICENSE, no README
        rc, out = run(r)
        fails += check("a repository with no licence is told so", "licence" in out
                       and "ABSENT" in out,
                       "all-rights-reserved by default is a fact its owner should know")
        fails += check("and told what that actually means", "grant" in out.lower(),
                       "'no licence' without the consequence is trivia")
        fails += check("and told it is not a blocker", "does not block" in out,
                       "an obligation note that reads like a refusal is over-escalation (section 54)")
        fails += check("the report still succeeds", rc == 0,
                       "a missing licence must not turn the report itself into a failure")

        # The load-bearing one: it must not gate. A repository with no licence
        # still gets verdicts.
        env = dict(os.environ); env["REPO_GOVERNOR_TARGET"] = str(r)
        pr = subprocess.run([sys.executable, str(ROOT / "engine" / "completion.py"), "W-1"],
                            capture_output=True, text=True, cwd=str(r), env=env, timeout=300)
        try:
            got = json.loads(pr.stdout)
        except Exception:
            got = {}
        fails += check("a licence-less repository still receives a verdict",
                       got.get("decision") is not None,
                       f"{pr.stdout[:150]} -- section 54: it must not block routine work")
        fails += check("and the verdict names no licence reason",
                       "licen" not in json.dumps(got).lower(),
                       "an obligation indicator must not leak into a governance disposition")

        r2 = bare_repo(td + "/withlic", manifest=MINIMAL)
        (r2 / "LICENSE").write_text("Apache License\n")
        rc2, out2 = run(r2)
        fails += check("positive control: a licensed repository reads present",
                       "licence   present" in out2,
                       "otherwise the ABSENT check passes because it always says ABSENT")

    print("\nIt does not claim what no provider can supply\n")
    rc, out = run(ROOT)
    fails += check("it says admitted-work-without-criteria is NOT COMPUTABLE",
                   "NOT COMPUTABLE" in out,
                   "no roadmap adapter advertises enumeration; claiming the set, or "
                   "printing nothing, would both misrepresent that")

    print(f"\n{'STATUS: CONFORMANT' if not fails else f'STATUS: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
