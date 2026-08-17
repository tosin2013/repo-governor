#!/usr/bin/env python3
"""ADR-008 Layer 1 conformance — contract tests every adapter must pass.

Layer 1 asks "does this adapter honour the contract?", not "is it correct
about the world". Layer 2 (cross-provider equivalence — the thesis test,
issue #1) is separate and not implemented here.

Checks, from ADR-008:
  C1  describe is well-formed and declares role + contract_version
  C2  honest capability advertisement — every claimed capability is exercised
  C3  typed failure — an unreachable backend errors, never returns empty
  C4  absence vs unknown are distinct
  C5  provenance on every fact
  C6  unsupported function is rejected, not silently absorbed
  C7  determinism — same input, byte-identical output

Usage:  python3 conformance/layer1.py [adapter ...]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# adapter -> (role, probe args, capability->function map, env that breaks the backend)
SUITE = {
    "adapters/git": {
        "role": "repository",
        "probe": {},
        "capability_fn": {
            "git_state": ("get_state", {}),
            "file_listing": ("get_files", {}),
            "dependency_manifests": ("get_manifests", {}),
        },
        "break_env": {"REPO_GOVERNOR_REPO": "/nonexistent-path-xyz"},
        "unknown_fn": ("get_entry_points", {}),
    },
    "adapters/adr": {
        "role": "architecture",
        "probe": {},
        "capability_fn": {
            "active_decisions": ("get_active_decisions", {}),
            "superseded_decisions": ("get_superseded_decisions", {}),
            "constraints": ("get_constraints", {}),
            "provenance": ("get_provenance", {}),
        },
        "break_env": {"REPO_GOVERNOR_ADR_DIR": "/nonexistent-path-xyz"},
        "unknown_fn": None,
    },
    "adapters/file-roadmap": {
        "role": "roadmap_authority",
        "probe": {"id": "GATE-6"},
        "capability_fn": {
            "work_lookup": ("get_work", {"id": "GATE-6"}),
            "status": ("get_status", {"id": "GATE-6"}),
            "authority": ("get_authority", {"id": "GATE-6"}),
            "scope": ("get_scope", {"id": "GATE-6"}),
            "non_goals": ("get_non_goals", {"id": "GATE-6"}),
            "acceptance_conditions": ("get_acceptance_conditions", {"id": "GATE-6"}),
            "decision_history": ("get_decision_history", {"id": "RBAC-1"}),
            "cancellation_detection": ("get_authority", {"id": "CANCELLED-1"}),
        },
        "break_env": {"REPO_GOVERNOR_ROADMAP": "/nonexistent-path-xyz.json"},
        "unknown_fn": ("get_non_goals", {"id": "THIN-1"}),
        "absence_fn": ("get_work", {"id": "NO-SUCH-ITEM"}),
        "malformed_fn": ("get_authority", {"id": "BADAUTH-1"}),
    },
    "adapters/github-projects": {
        "role": "roadmap_authority",
        "probe": {"id": "1"},
        "capability_fn": {
            "work_lookup": ("get_work", {"id": "1"}),
            "status": ("get_status", {"id": "1"}),
            "authority": ("get_authority", {"id": "1"}),
            "cancellation_detection": ("get_authority", {"id": "3"}),
            "decision_history": ("get_decision_history", {"id": "3"}),
        },
        # Fixture mode by default so C7 determinism is assertable (ADR-008 rule 1).
        "env": {"REPO_GOVERNOR_GH_FIXTURE": "conformance/fixtures/github-projects.json"},
        "break_env": {"REPO_GOVERNOR_GH_FIXTURE": "/nonexistent-fixture-xyz.json"},
        "unknown_fn": ("get_non_goals", {"id": "1"}),
        "absence_fn": ("get_work", {"id": "9999"}),
    },
}


def run(adapter, args, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([sys.executable, str(ROOT / adapter), *args],
                       capture_output=True, text=True, cwd=ROOT, env=env, timeout=30)
    return p.returncode, p.stdout, p.stderr


def q(adapter, role, fn, kw, env_extra=None, base_env=None):
    args = ["query", role, fn] + [f"{k}={v}" for k, v in kw.items()]
    merged = dict(base_env or {})
    merged.update(env_extra or {})
    rc, out, err = run(adapter, args, merged or None)
    try:
        return json.loads(out), out, err
    except json.JSONDecodeError:
        return None, out, err


class Report:
    def __init__(self):
        self.rows = []

    def add(self, adapter, check, ok, detail=""):
        self.rows.append((adapter, check, ok, detail))

    def failures(self):
        return [r for r in self.rows if not r[2]]


def check_adapter(adapter, spec, rep):
    role = spec["role"]
    base = spec.get("env")

    # C1 describe well-formed
    rc, out, err = run(adapter, ["describe"], base)
    try:
        d = json.loads(out)
        good = (d.get("role") == role and isinstance(d.get("contract_version"), int)
                and isinstance(d.get("capabilities"), dict) and isinstance(d.get("functions"), list))
        rep.add(adapter, "C1 describe well-formed", good,
                "" if good else f"got {out[:120]}")
    except json.JSONDecodeError:
        rep.add(adapter, "C1 describe well-formed", False, f"not JSON: {out[:80]} {err[:80]}")
        return

    # C2 honest capability advertisement
    for cap, claimed in d["capabilities"].items():
        if claimed is not True:
            continue
        pair = spec["capability_fn"].get(cap)
        if pair is None:
            rep.add(adapter, f"C2 capability '{cap}' exercised", False,
                    "claimed true but no probe defined — untestable claim")
            continue
        fn, kw = pair
        r, raw, err = q(adapter, role, fn, kw, base_env=base)
        good = bool(r) and r.get("ok") is True and (r.get("value") is not None or r.get("unknown"))
        rep.add(adapter, f"C2 capability '{cap}' exercised", good,
                "" if good else f"{fn} -> {str(r)[:100]}")

    # C3 typed failure on unreachable backend
    fn, kw = next(iter(spec["capability_fn"].values()))
    r, raw, err = q(adapter, role, fn, kw, spec["break_env"], base_env=base)
    good = bool(r) and r.get("ok") is False and r.get("error", {}).get("type") == "PROVIDER_UNAVAILABLE"
    rep.add(adapter, "C3 unreachable backend -> typed failure", good,
            "" if good else f"expected PROVIDER_UNAVAILABLE, got {str(r)[:110]}")

    # C4 absence vs unknown are distinct
    if spec.get("absence_fn"):
        fn, kw = spec["absence_fn"]
        r, _, _ = q(adapter, role, fn, kw, base_env=base)
        good = bool(r) and r.get("ok") is False and r.get("error", {}).get("type") == "NOT_FOUND"
        rep.add(adapter, "C4a absence -> NOT_FOUND", good,
                "" if good else f"got {str(r)[:110]}")
    if spec.get("unknown_fn"):
        fn, kw = spec["unknown_fn"]
        r, _, _ = q(adapter, role, fn, kw, base_env=base)
        good = bool(r) and r.get("ok") is True and r.get("unknown") is not None \
            and {"reason", "detail", "resolution", "blocking"} <= set(r["unknown"])
        rep.add(adapter, "C4b unknown carries typed payload", good,
                "" if good else f"got {str(r)[:110]}")

    # C4c a malformed source value must not be silently coerced (the ADR-015 lesson)
    if spec.get("malformed_fn"):
        fn, kw = spec["malformed_fn"]
        r, _, _ = q(adapter, role, fn, kw, base_env=base)
        good = bool(r) and r.get("ok") is False and r.get("error", {}).get("type") == "MALFORMED_SOURCE"
        rep.add(adapter, "C4c malformed value -> MALFORMED_SOURCE", good,
                "" if good else f"got {str(r)[:110]}")

    # C5 provenance on every fact
    missing = []
    for cap, pair in spec["capability_fn"].items():
        fn, kw = pair
        r, _, _ = q(adapter, role, fn, kw, base_env=base)
        if r and r.get("ok") and r.get("value") is not None:
            if not r.get("provenance"):
                missing.append(fn)
            else:
                for c in r["provenance"]:
                    if not (c.get("source") and c.get("ref")):
                        missing.append(f"{fn}(malformed cite)")
    rep.add(adapter, "C5 every fact carries provenance", not missing,
            "" if not missing else f"missing on: {missing}")

    # C6 unsupported function rejected
    r, _, _ = q(adapter, role, "get_nonexistent_thing", {}, base_env=base)
    good = bool(r) and r.get("ok") is False and r.get("error", {}).get("type") == "UNSUPPORTED_FUNCTION"
    rep.add(adapter, "C6 unsupported function rejected", good,
            "" if good else f"got {str(r)[:110]}")

    # C7 determinism
    fn, kw = next(iter(spec["capability_fn"].values()))
    _, a, _ = q(adapter, role, fn, kw, base_env=base)
    _, b, _ = q(adapter, role, fn, kw, base_env=base)
    _, c, _ = q(adapter, role, fn, kw, base_env=base)
    rep.add(adapter, "C7 byte-identical across runs", a == b == c,
            "" if a == b == c else "output varies between identical invocations")


def main(argv):
    targets = argv or list(SUITE)
    rep = Report()
    for adapter in targets:
        if adapter not in SUITE:
            print(f"unknown adapter {adapter!r}", file=sys.stderr)
            return 2
        check_adapter(adapter, SUITE[adapter], rep)

    cur = None
    for adapter, check, ok, detail in rep.rows:
        if adapter != cur:
            print(f"\n{adapter}")
            cur = adapter
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {check}" + (f"\n         {detail}" if detail else ""))

    fails = rep.failures()
    print(f"\n{len(rep.rows) - len(fails)}/{len(rep.rows)} checks passed")
    print("LAYER 1: " + ("CONFORMANT" if not fails else f"NON-CONFORMANT ({len(fails)} failures)"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
