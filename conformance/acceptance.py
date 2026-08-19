#!/usr/bin/env python3
"""An empty completion bar is never a met one (issue 58).

THE CHECK THIS SUITE EXISTS FOR is the first one. Before this work, a
`criteria: []` array reached completion.py's evaluation loop, produced zero
results, and both "anything unresolved?" and "anything unmet?" were false --
so the else branch declared STOP_COMPLETE by vacuous quantification.
Demonstrated on a live authority id: emptying the array turned CONTINUE into
STOP_COMPLETE with satisfied=true, on zero evidence.

Section 40 is the completion FIREWALL. A firewall that opens when handed
nothing to check is not one, and an unedited template would have had exactly
that shape on first contact.

There are TWO guards -- one in the engine, one in the adapter -- and this suite
asserts each holds ALONE. Defence in depth is only defence if removing either
layer is caught; two guards that are only ever tested together are one guard
with a spare.

Usage:  python3 conformance/acceptance.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import _count as _CNT  # noqa: E402 -- uniform counting; alias is deliberate,
# `C` is already taken by `completion` in two suites and the collision silently
# rebound it (issue 67).

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
import completion as C  # noqa: E402
import manifest as MF  # noqa: E402

ACC = ROOT / "adapters" / "acceptance-file"
TOOL = ROOT / "engine" / "acceptance.py"


def check(label, ok, detail=""):
    _CNT.tally(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"\n         {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def adapter(wid, cwd):
    p = subprocess.run([sys.executable, str(ACC), "query", "acceptance_criteria",
                        "get_criteria", f"id={wid}"],
                       capture_output=True, text=True, cwd=str(cwd), timeout=60)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {}


def main():
    fails = 0
    print("An empty bar is not a met bar — the adapter's guard, alone\n")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / ".repo-governor" / "acceptance"
        d.mkdir(parents=True)
        (d / "E-1.json").write_text(json.dumps({"authority_id": "E-1", "criteria": []}))
        r = adapter("E-1", td)
        fails += check("the adapter refuses to serve an empty criteria array",
                       bool(r.get("unknown")) and r["unknown"]["reason"] == "NO_CRITERIA_DECLARED",
                       json.dumps(r)[:200])
        fails += check("and it is non-blocking (absence of a bar does not stop work)",
                       bool(r.get("unknown")) and r["unknown"].get("blocking") is False,
                       "a repository with no bar must still be able to proceed")

        (d / "E-2.json").write_text(json.dumps(
            {"authority_id": "E-2", "criteria": [{"check": "file_exists", "target": "x"}]}))
        r2 = adapter("E-2", td)
        fails += check("positive control: a non-empty array IS served",
                       r2.get("ok") and not r2.get("unknown"),
                       "otherwise the check above passes because nothing is ever served")

    print("\nThe engine's own guard, alone — section 40 does not depend on a provider\n")

    # Grepping completion.py for `if not criteria:` would prove nothing: a
    # comment matches, and this repository has shipped that defect twice. So
    # the adapter guard is genuinely REMOVED from a copy, that copy is bound in
    # a real manifest, and the engine is run against it. If section 40 held
    # only because the adapter refused, this is where the firewall re-opens.
    # Beside _protocol.py, because every adapter does
    #     sys.path.insert(0, str(Path(__file__).parent)); from _protocol import ...
    # A stub under conformance/fixtures/ cannot resolve that import, and the
    # ImportError traceback surfaces as NON_JSON -- which is how this check first
    # passed while never reaching the acceptance step at all.
    stub_rel = "adapters/_stub-acceptance-unguarded"
    stub = ROOT / stub_rel
    s = ACC.read_text(encoding="utf-8")
    guard = '    if not data["criteria"]:\n        return _no_criteria("get_criteria", kw["id"], p)\n'
    fails += check("the adapter guard exists to be removed", guard in s,
                   "the mutation target moved; what follows would prove nothing")
    try:
        stub.write_text(s.replace(guard, "", 1), encoding="utf-8")
        stub.chmod(0o755)
        with tempfile.TemporaryDirectory() as td:
            r = Path(td) / "repo"
            (r / ".repo-governor" / "acceptance").mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(r)], capture_output=True)
            subprocess.run(["git", "-C", str(r), "remote", "add", "origin",
                            "https://github.com/acme/w.git"], capture_output=True)
            (r / "roadmap.json").write_text(json.dumps({"items": {
                "E-3": {"title": "x", "status": "IN_PROGRESS", "authority": "AUTHORIZED",
                        "admitted": True, "required_outcome": "x", "in_scope": [],
                        "decision_history": []}}}))
            (r / ".repo-governor" / "acceptance" / "E-3.json").write_text(
                json.dumps({"authority_id": "E-3", "criteria": []}))
            (r / ".repo-governor.json").write_text(json.dumps({
                "repo_governor": {"version": 1, "engine_min_version": "0.1.0"},
                "repository": {"id": "acme/w"},
                "condition": {"assessed": "L1", "profile": "GOVERNOR_LITE"},
                "permissions": {"repository": {"read": True, "write": False},
                                "roadmap_authority": {"read": True, "write": False},
                                "acceptance_criteria": {"read": True, "write": False}},
                "providers": {
                    "repository": {"type": "git", "adapter": "adapters/git",
                                   "contract_version": 1},
                    "roadmap_authority": {"type": "file-roadmap",
                                          "adapter": "adapters/file-roadmap",
                                          "contract_version": 1,
                                          "env": {"REPO_GOVERNOR_ROADMAP": "roadmap.json"}},
                    "acceptance_criteria": {"type": "acceptance-file", "adapter": stub_rel,
                                            "contract_version": 1}}}))
            env = dict(os.environ)
            env["REPO_GOVERNOR_TARGET"] = str(r)
            pr = subprocess.run([sys.executable, str(ROOT / "engine" / "completion.py"), "E-3"],
                                capture_output=True, text=True, cwd=str(r), env=env, timeout=300)
            try:
                got = json.loads(pr.stdout)
            except Exception:
                got = {}
            reasons = [u.get("reason") for u in (got.get("unknowns") or [])]
            fails += check("the scenario actually reaches criteria evaluation",
                           got.get("decision") in ("CONTINUE", "STOP_COMPLETE"),
                           f"got {got.get('decision')!r} reasons={reasons} — anything else "
                           "means the run failed BEFORE the acceptance step, and the "
                           "assertion below would pass without testing the guard")
            fails += check("with the adapter guard gone, the ENGINE still refuses STOP_COMPLETE",
                           got.get("decision") == "CONTINUE"
                           and "NO_CRITERIA_DECLARED" in reasons,
                           f"got {got.get('decision')!r} with "
                           f"satisfied={got.get('stop_condition')} — the completion firewall "
                           "opened on zero declared conditions")
    finally:
        if stub.exists():
            stub.unlink()

    print("\nThe template scaffolds a bar without declaring one\n")

    with tempfile.TemporaryDirectory() as td:
        r = Path(td) / "repo"
        (r / ".repo-governor").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(r)], capture_output=True)
        env = dict(os.environ); env["REPO_GOVERNOR_TARGET"] = str(r)

        p = subprocess.run([sys.executable, str(TOOL), "T-1"],
                           capture_output=True, text=True, env=env, timeout=300)
        made = (r / ".repo-governor" / "acceptance" / "T-1.json")
        fails += check("without --template it writes nothing (ADR-005)", not made.exists(),
                       "creating a file in a repository is a change to that repository")
        fails += check("and it says how to scaffold one", "--template" in p.stdout, p.stdout[:200])

        subprocess.run([sys.executable, str(TOOL), "T-1", "--template"],
                       capture_output=True, text=True, env=env, timeout=300)
        fails += check("with --template it writes one", made.exists())
        if made.exists():
            data = json.loads(made.read_text())
            fails += check("the template declares NO criteria", data.get("criteria") == [],
                           "a generated criterion is a guess about what done means")
            fails += check("it names the three supported checks",
                           {c["check"] for c in data.get("$examples", [])}
                           == {"tests_pass", "file_exists", "command_exit"})
            fails += check("it says in the file that it is not a bar yet",
                           "NOT a completion bar" in json.dumps(data),
                           "a reader who finds this file must not mistake it for one")
            fails += check("the scaffolded file is still refused as a bar",
                           bool(adapter("T-1", r).get("unknown")),
                           "an unedited template that satisfied itself would make the "
                           "completion firewall a rubber stamp on first contact")

        p2 = subprocess.run([sys.executable, str(TOOL), "T-1", "--template"],
                            capture_output=True, text=True, env=env, timeout=300)
        fails += check("it refuses to overwrite an existing record", p2.returncode != 0,
                       "replacing a bar somebody set is editing the bar to fit the work")

    print(f"\n{'ACCEPTANCE: CONFORMANT' if not fails else f'ACCEPTANCE: NON-CONFORMANT ({fails})'}")
    print(_CNT.line("acceptance"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
