#!/usr/bin/env python3
"""Provider pluggability is a checked property, not a described one (ADR-021).

The provider architecture was called complete while `engine/completion.py`
named five adapters directly and spawned every one of them without consulting
`permitted()`. Documentation cannot prevent that from growing back; a test can.

Each check below fails loudly if the engine reacquires knowledge it should not
have, or if the permission gate stops being a gate.

Usage:  python3 conformance/bindings.py
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
import bindings as B  # noqa: E402
import manifest as MF  # noqa: E402

BASE = json.loads((ROOT / ".repo-governor.json").read_text())

# Only this module may spawn an adapter. `onboard.py` may NAME adapter paths --
# it proposes bindings for a human to accept (ADR-010) -- but it must never run
# one, and `completion.py` must not even name one.
SPAWNER = "bindings.py"
DECISION_PATH = ("completion.py",)


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"    {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def with_manifest(mutate):
    d = copy.deepcopy(BASE)
    mutate(d)
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(d, f)
    f.close()
    m, errs = MF.load(f.name)
    Path(f.name).unlink()
    return m, errs


def main():
    fails = 0
    print("Engine holds no adapter knowledge\n")

    # 1. The decision path names no adapter at all.
    for name in DECISION_PATH:
        text = (ROOT / "engine" / name).read_text()
        fails += check(f"engine/{name} contains no 'adapters/' literal",
                       "adapters/" not in text)

    # 2. Exactly one module spawns an adapter. Detected structurally: an adapter
    #    spawn is `sys.executable` pointed at a repository-relative path.
    spawners = []
    for p in sorted((ROOT / "engine").glob("*.py")):
        t = p.read_text()
        if "sys.executable" in t and "ROOT /" in t:
            spawners.append(p.name)
    fails += check(f"only {SPAWNER} spawns an adapter", spawners == [SPAWNER],
                   f"also spawning: {[s for s in spawners if s != SPAWNER]}")

    print("\nThe gate is a gate\n")

    # 3. A denied read returns a disposition and never reaches the provider.
    #    Asserted by pointing the binding at an adapter that does not exist: if
    #    the call were to spawn, it would fail with something other than
    #    PERMISSION_DENIED. Denial must win before resolution is even attempted.
    m, errs = with_manifest(lambda d: (
        d["permissions"]["architecture"].__setitem__("read", False),
        d["providers"]["architecture"][0].__setitem__("adapter", "adapters/adr")))
    r = B.call("architecture", "get_constraints", {"id": "x"}, manifest=m)
    fails += check("denied read returns PERMISSION_DENIED, not provider output",
                   r.get("error", {}).get("type") == "PERMISSION_DENIED",
                   json.dumps(r)[:120])

    # 4. Denial is a disposition, not an exception (ADR-005 rule 5).
    fails += check("denial is a typed envelope, not a raise", r.get("ok") is False)

    # 5. An unbound role is refused by name, not by crashing on a missing key.
    r = B.call("retirement_x", "anything", {}, manifest=BASE)
    fails += check("unbound role returns UNBOUND_ROLE or PERMISSION_DENIED",
                   r.get("error", {}).get("type") in ("UNBOUND_ROLE", "PERMISSION_DENIED"),
                   json.dumps(r)[:120])

    # 6. A role bound but never granted any verb is denied, so adding a binding
    #    is not itself a grant. This is INV-014 at the engine boundary: the
    #    provider is present and reachable, and still may not be used.
    m_ungranted, _ = with_manifest(lambda d: d["permissions"].pop("architecture", None))
    r = B.call("architecture", "get_constraints", {"id": "x"}, manifest=m_ungranted)
    fails += check("a bound role with no permission block is denied",
                   r.get("error", {}).get("type") == "PERMISSION_DENIED",
                   json.dumps(r)[:120])

    print("\nWriter selection is by capability, never by name\n")

    m, errs = MF.load()
    assert not errs, errs

    # 7. The chosen writer is one that ADVERTISES the function.
    b, err = B.writer_for("decision_history", "record_decision", m)
    ok = err is None and "record_decision" in (B.describe(b).get("writers") or {})
    fails += check("selected writer advertises record_decision", ok,
                   json.dumps(err or {})[:120])

    # 8. A function nothing advertises is refused, rather than sent to the first
    #    binding and failing deep inside the adapter.
    b2, err2 = B.writer_for("decision_history", "delete_everything", m)
    fails += check("unadvertised writer function is refused up front",
                   b2 is None and err2["error"]["type"] == "NO_WRITABLE_PROVIDER")

    # 9. Selection does not depend on the adapter's name. Renaming the type must
    #    not change the outcome -- this is the specific regression that the old
    #    `startswith("decision-history-dolt")` test would have produced.
    m_renamed, _ = with_manifest(
        lambda d: d["providers"]["decision_history"][0].__setitem__("type", "zzz-anonymous-store"))
    b3, err3 = B.writer_for("decision_history", "record_decision", m_renamed)
    fails += check("renaming the adapter type does not change selection",
                   err3 is None and b3 is not None and b3["adapter"] == b["adapter"],
                   json.dumps(err3 or {})[:120])

    print("\nConfiguration comes from the manifest, not from engine code\n")

    # 10. Binding `env` reaches the adapter process.
    m_env, _ = with_manifest(
        lambda d: d["providers"]["architecture"][0].__setitem__("env", {"RG_PROBE": "seen"}))
    env = B._env_for(m_env["providers"]["architecture"][0])
    fails += check("binding.env reaches the adapter environment", env.get("RG_PROBE") == "seen")

    # 11. The whole binding is offered as structured config, so an adapter can
    #     read a declared admission signal without the engine knowing its name.
    fails += check("REPO_GOVERNOR_BINDING carries the binding as JSON",
                   json.loads(env["REPO_GOVERNOR_BINDING"]).get("adapter") is not None)

    # 12. A credential cannot be smuggled in through the new field.
    _, errs_secret = with_manifest(
        lambda d: d["providers"]["architecture"][0].__setitem__(
            "env", {"TOKEN": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"}))
    fails += check("secret-shaped value in binding.env fails the load",
                   any("SECRET" in e for e in errs_secret), str(errs_secret)[:120])

    print(f"\n{'BINDINGS: CONFORMANT' if not fails else f'BINDINGS: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
