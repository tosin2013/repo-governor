#!/usr/bin/env python3
"""Execution state stays subordinate to roadmap authority (§62, ADR-013, INV-002).

Stage E of the real-repository validation program. The property under test is
not that execution is read -- it is that reading it **changes nothing about
authority**. An execution provider that could promote work would be a second
roadmap, which is ADR-022's failure with a different label.

Before #34 no engine module consulted this role at all, so the scenario the
product exists for -- the tracker says READY while the roadmap says cancelled --
could neither pass nor fail. Getting `AUTHORITY_WITHDRAWN` right by never
looking is not the same as getting it right, and only one of those survives a
provider being bound.

Usage:  python3 conformance/execution.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import _count as _CNT  # noqa: E402 -- uniform counting; alias is deliberate,
# `C` is already taken by `completion` in two suites and the collision silently
# rebound it (issue 67).

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _preflight  # noqa: E402
sys.path.insert(0, str(ROOT / "engine"))
import completion as C  # noqa: E402
import manifest as MF  # noqa: E402

BASE = json.loads((ROOT / ".repo-governor.json").read_text())


def check(label, ok, detail=""):
    _CNT.tally(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"    {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def bound_manifest(with_execution=True):
    """A manifest binding the file providers, so execution has something to read."""
    d = copy.deepcopy(BASE)
    d["providers"]["roadmap_authority"] = {
        "type": "file-roadmap", "adapter": "adapters/file-roadmap", "contract_version": 1,
        "env": {"REPO_GOVERNOR_ROADMAP": "conformance/fixtures/roadmap.json"}}
    d["providers"]["acceptance_criteria"]["env"] = {
        "REPO_GOVERNOR_ACCEPTANCE_DIR": "conformance/fixtures/acceptance"}
    if with_execution:
        d["providers"]["execution"] = {
            "type": "execution-file", "adapter": "adapters/execution-file", "contract_version": 1,
            "env": {"REPO_GOVERNOR_EXECUTION": "conformance/fixtures/execution.json"}}
        d["permissions"]["execution"] = {"read": True}
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(d, f)
    f.close()
    m, errs = MF.load(f.name)
    Path(f.name).unlink()
    assert not errs, errs
    return m


def main():
    absent = _preflight.banner()
    fails = 0
    m = bound_manifest()

    print("Roadmap authority overrides execution state\n")

    r = C.evaluate("CANCELLED-1", manifest=m)
    fails += check("cancelled item with subtasks running is AUTHORITY_WITHDRAWN",
                   r["decision"] == "AUTHORITY_WITHDRAWN", r["decision"])
    fails += check("the in-flight work is REPORTED, not silently ignored",
                   bool(r.get("execution_in_flight")), str(r.get("execution")))
    fails += check("execution never appears as an authority value",
                   r.get("authority") == "CANCELLED", str(r.get("authority")))

    print("\nAbsent execution state invents nothing\n")

    r = C.evaluate("RBAC-1", manifest=m)
    fails += check("no execution root does not fabricate work",
                   (r.get("execution") or {}).get("state") == "NO_EXECUTION_ROOT",
                   str((r.get("execution") or {}).get("state")))
    fails += check("and does not change the disposition", r["decision"] in ("CONTINUE", "STOP_COMPLETE"),
                   r["decision"])

    print("\nCompletion plus a discovery beneath it\n")

    r = C.evaluate("AUTHORIZED-1", manifest=m)
    fails += check("finished work is STOP_COMPLETE", r["decision"] == "STOP_COMPLETE", r["decision"])
    cap = r.get("captured") or []
    fails += check("the discovery is surfaced with the decision", bool(cap), str(r.get("execution")))
    fails += check("and every one is CAPTURE_ONLY",
                   all(c["disposition"] == "CAPTURE_ONLY" for c in cap), str(cap))
    fails += check("completed subtasks are visible as evidence",
                   len((r.get("execution") or {}).get("completed") or []) > 0)

    print("\nAn unbound role is absence of evidence, not evidence of absence\n")

    r = C.evaluate("AUTHORIZED-1", manifest=bound_manifest(with_execution=False))
    ex = r.get("execution") or {}
    fails += check("unbound execution reports UNBOUND", ex.get("state") == "UNBOUND", str(ex))
    fails += check("and the disposition is unchanged by its absence",
                   r["decision"] == "STOP_COMPLETE", r["decision"])
    fails += check("no discoveries are claimed when nothing was read", not r.get("captured"))

    print(f"\n{'EXECUTION SUBORDINATION: CONFORMANT' if not fails else f'EXECUTION SUBORDINATION: NON-CONFORMANT ({fails})'}")
    if fails:
        _preflight.attribute(absent)
    print(_CNT.line("execution"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
