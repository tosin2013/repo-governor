#!/usr/bin/env python3
"""Manifest loader conformance — gate 5 (#11).

The loader's value is entirely in what it REFUSES. Each case below mutates
the real manifest into something that must fail, and asserts the specific
error fires. A loader that accepts a bad manifest is worse than none: it
produces confident governance from a wrong binding.

Usage:  python3 conformance/manifest.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import pathlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
import manifest as M  # noqa: E402

BASE = json.loads((ROOT / ".repo-governor.json").read_text())


def mutate(fn):
    d = copy.deepcopy(BASE)
    fn(d)
    return d


def _drop_repo(d):
    del d["providers"]["repository"]
    d["permissions"].pop("repository", None)


CASES = [
    ("baseline is valid",              lambda d: None,                                    None),
    ("future version refuses",         lambda d: d["repo_governor"].__setitem__("version", 99), "UNSUPPORTED_VERSION"),
    ("scalar role given a list",       lambda d: d["providers"].__setitem__("roadmap_authority", [d["providers"]["roadmap_authority"]]), "CARDINALITY"),
    ("array role given a scalar",      lambda d: d["providers"].__setitem__("architecture", d["providers"]["architecture"][0]), "CARDINALITY"),
    ("repository role missing",        _drop_repo,                                        "MISSING_ROLE"),
    ("adapter escapes repository",     lambda d: d["providers"]["repository"].__setitem__("adapter", "../../../etc/passwd"), "ADAPTER"),
    ("adapter does not exist",         lambda d: d["providers"]["repository"].__setitem__("adapter", "adapters/nope"), "ADAPTER_MISSING"),
    ("reserved verb execute",          lambda d: d["permissions"]["repository"].__setitem__("execute", True), "PERMISSION_RESERVED"),
    ("unknown verb",                   lambda d: d["permissions"]["repository"].__setitem__("delete", True), "PERMISSION_UNKNOWN_VERB"),
    ("permissions for unbound role",   lambda d: d["permissions"].__setitem__("retirement_x", {"read": True}), "PERMISSION_ORPHAN"),
    ("malformed permission block",     lambda d: d["permissions"].__setitem__("repository", "yes"), "PERMISSION_MALFORMED"),
    ("github token in manifest",       lambda d: d["providers"]["repository"].__setitem__("project", "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"), "SECRET"),
    ("opaque credential-shaped value", lambda d: d["providers"]["repository"].__setitem__("project", "aGVsbG93b3JsZGhlbGxvd29ybGRoZWxsb3dvcmxk"), "SECRET"),
    ("key named api_key",              lambda d: d["providers"]["repository"].__setitem__("api_key", "x"), "SECRET"),
    ("unknown top-level property",     lambda d: d.__setitem__("roadmap", {"items": {}}), "SCHEMA"),
    ("bad condition level",            lambda d: d["condition"].__setitem__("assessed", "L9"), "SCHEMA"),
    ("profile not in enum",            lambda d: d["condition"].__setitem__("profile", "GOVERNOR_TURBO"), "SCHEMA"),
    ("binding without adapter",        lambda d: d["providers"]["repository"].pop("adapter"), "SCHEMA"),
    ("bad transport kind",             lambda d: d["providers"]["repository"].__setitem__("transport", {"kind": "carrier-pigeon"}), "SCHEMA"),
    ("contract_version zero",          lambda d: d["providers"]["repository"].__setitem__("contract_version", 0), "SCHEMA"),
]

# Deny-by-default: (role, verb, expected)
PERM_CASES = [
    ("repository", "read", True),
    ("repository", "write", False),          # explicitly false
    ("repository", "create", False),         # absent verb => deny
    ("roadmap_authority", "transition", False),
    ("decision_history", "read", True),      # bound as of ADR-019 (two backends)
    ("decision_history", "write", True),     # the ONE write granted anywhere (ADR-019)
    ("architecture", "write", False),        # every other role stays read-only
    ("nonexistent", "read", False),          # unbound role => deny; all 8 real roles are now bound
]


def main():
    fails = 0
    print("Manifest loader — refusal cases\n")
    for label, fn, expect in CASES:
        d = mutate(fn)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(d, f)
            tmp = f.name
        m, errs = M.load(tmp)
        Path(tmp).unlink()
        if expect is None:
            ok = not errs and m is not None
            detail = "" if ok else f"unexpected: {errs[:2]}"
        else:
            ok = any(e.startswith(expect) or expect in e for e in errs) and m is None
            detail = "" if ok else f"expected {expect}, got {errs[:2] or 'no errors'}"
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<34}{'  ' + detail if detail else ''}")

    print("\nDeny by default\n")
    m, errs = M.load()
    assert not errs, errs
    for role, verb, expect in PERM_CASES:
        got, why = M.permitted(m, role, verb)
        ok = got == expect
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {role}.{verb:<11} -> {'ALLOW' if got else 'DENY'}   {why[:56]}")

    # A binding can be well-formed, reachable, and answer nothing. --validate
    # said READY_FOR_GOVERNANCE for exactly that, and it is the last check
    # before someone trusts the answers -- so a green verdict there is worse
    # than a red one, because the very next command says PROVIDER_UNAVAILABLE
    # and the operator has to decide which to believe (issue 51).
    print("\nA binding that cannot answer is not READY_FOR_GOVERNANCE\n")
    import copy as _copy, subprocess as _sp, tempfile as _tf, os as _os
    extra = 0

    def _validate(manifest_obj):
        with _tf.TemporaryDirectory() as td:
            r = pathlib.Path(td) / "repo"
            r.mkdir()
            _sp.run(["git", "init", "-q", str(r)], capture_output=True)
            (r / ".repo-governor.json").write_text(json.dumps(manifest_obj))
            env = dict(_os.environ); env["REPO_GOVERNOR_TARGET"] = str(r)
            return _sp.run([sys.executable, str(ROOT / "engine" / "manifest.py"), "--validate"],
                           capture_output=True, text=True, cwd=str(r), env=env, timeout=120).stdout

    base = json.loads((ROOT / ".repo-governor.json").read_text())
    stripped = _copy.deepcopy(base)
    stripped["providers"] = {k: v for k, v in base["providers"].items()
                             if k in ("repository", "roadmap_authority") or k.startswith("$")}
    stripped["permissions"] = {k: v for k, v in base["permissions"].items()
                               if k in ("repository", "roadmap_authority") or k.startswith("$")}
    kept = _copy.deepcopy(stripped)
    stripped["providers"]["roadmap_authority"] = dict(stripped["providers"]["roadmap_authority"])
    stripped["providers"]["roadmap_authority"].pop("env", None)

    out_bad = _validate(stripped)
    ok = "READY_FOR_GOVERNANCE" not in out_bad and "NOT_CONFIGURED" in out_bad
    extra += not ok
    print(f"  [{'PASS' if ok else 'FAIL'}] a binding with no declared identity is refused"
          + ("" if ok else f"\n         {out_bad.strip()[:180]}"))

    ok2 = "REPO_GOVERNOR_GH_REPO" in out_bad
    extra += not ok2
    print(f"  [{'PASS' if ok2 else 'FAIL'}] and the finding names the missing configuration"
          + ("" if ok2 else "\n         'not configured' without naming it is not actionable"))

    # Positive control. Without it, the check above passes for any manifest
    # that fails to validate for ANY reason.
    out_good = _validate(kept)
    ok3 = "READY_FOR_GOVERNANCE" in out_good
    extra += not ok3
    print(f"  [{'PASS' if ok3 else 'FAIL'}] control: the same binding WITH identity is ready"
          + ("" if ok3 else f"\n         {out_good.strip()[:180]}"))

    # The engine must not have learned an adapter's variable names.
    src = (ROOT / "engine" / "manifest.py").read_text()
    ok4 = "REPO_GOVERNOR_GH_REPO" not in src and "LINEAR_API_KEY" not in src
    extra += not ok4
    print(f"  [{'PASS' if ok4 else 'FAIL'}] the engine names no adapter's configuration (ADR-003)"
          + ("" if ok4 else "\n         adapter-specific knowledge must stay in the adapter"))

    fails += extra
    total = len(CASES) + len(PERM_CASES) + 4
    print(f"\n{total - fails}/{total} checks passed")
    print("MANIFEST LOADER: " + ("CONFORMANT" if not fails else f"NON-CONFORMANT ({fails})"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
