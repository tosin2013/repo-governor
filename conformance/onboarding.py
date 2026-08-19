#!/usr/bin/env python3
"""Onboarding simulation RG-SIM-ONBOARDING-v0.1 — gate 1 (#7).

Materializes fixtures A–C from `fixtures/onboarding.json` into isolated
temp repositories, runs `engine/onboard.py` against each, and asserts the
expectations in §58–§60.

Also validates gates 2, 3 and 4, which have no separate build:

    gate 2  fixture C emits PROVIDER_CONFLICT and halts (#8)
    gate 3  fixture A needs no providers beyond Git (#9)
    gate 4  detection proposes; the engine never reads the proposal (#10)

Usage:  python3 conformance/onboarding.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
import onboard as O  # noqa: E402

SPEC = json.loads((ROOT / "conformance" / "fixtures" / "onboarding.json").read_text())


def materialize(name, fx, into: Path):
    repo = into / name
    repo.mkdir(parents=True)
    for rel, content in fx["files"].items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    if fx.get("remote"):
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", fx["remote"]], check=True)
    return repo


class R:
    def __init__(self):
        self.rows = []

    def add(self, fx, check, ok, detail=""):
        self.rows.append((fx, check, ok, detail))

    def fails(self):
        return [r for r in self.rows if not r[2]]


def run_fixture(name, fx, tmp, rep):
    repo = materialize(name, fx, tmp)
    res = O.onboard(repo)
    exp = fx["expect"]
    got_roles = set(res["roles_detected"])

    if "condition" in exp:
        rep.add(name, f"condition == {exp['condition']}",
                res["condition"]["suggested"] == exp["condition"],
                f"got {res['condition']['suggested']} ({res['condition']['reason']})")
    if "profile" in exp:
        rep.add(name, f"profile == {exp['profile']}",
                res["condition"]["profile"] == exp["profile"],
                f"got {res['condition']['profile']}")

    rep.add(name, f"state == {exp['state']}", res["state"] == exp["state"],
            f"got {res['state']}")

    if "roles_detected" in exp:
        want = set(exp["roles_detected"])
        rep.add(name, f"roles == {sorted(want)}", got_roles == want,
                f"got {sorted(got_roles)}")

    for role in exp.get("must_not_detect", []):
        rep.add(name, f"does NOT detect {role}", role not in got_roles,
                f"unexpectedly detected {role}")

    for role, disp in exp.get("dispositions", {}).items():
        actual = [c["disposition"] for c in res["candidates"].get(role, [])]
        rep.add(name, f"{role} disposition {disp}", disp in actual, f"got {actual}")

    if exp.get("conflict_role"):
        cf = [c for c in res["conflicts"] if c["role"] == exp["conflict_role"]]
        rep.add(name, f"PROVIDER_CONFLICT on {exp['conflict_role']}", bool(cf),
                "no conflict raised")
        if cf:
            rep.add(name, "conflict names both candidates",
                    set(cf[0]["candidates"]) == set(exp["conflict_candidates"]),
                    f"got {cf[0]['candidates']}")
            rep.add(name, "no ranking applied (gate 2)",
                    "No ranking" in cf[0]["required"], "")

    # Every candidate must cite evidence (ADR-010 rule 3).
    uncited = [c["type"] for cs in res["candidates"].values() for c in cs if not c["evidence"]]
    rep.add(name, "every candidate cites evidence", not uncited, f"uncited: {uncited}")

    # Detection must never authenticate (ADR-010 rule 4).
    rep.add(name, "detection states it used no credentials",
            any("No credentials" in n for n in res["notes"]), "")

    return repo, res


def main():
    rep = R()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repos = {}
        for name, fx in SPEC["fixtures"].items():
            repos[name], _ = run_fixture(name, fx, tmp, rep)

        # gate 4: proposal is written but the ENGINE never reads it.
        a = repos["A-greenfield"]
        subprocess.run([sys.executable, str(ROOT / "engine" / "onboard.py"), str(a), "--write"],
                       capture_output=True, check=True)
        wrote = (a / O.PROPOSAL).exists()
        rep.add("gate-4", "onboard --write emits a proposal", wrote, "")
        src = (ROOT / "engine" / "manifest.py").read_text()
        rep.add("gate-4", "manifest loader never reads the proposal",
                "proposed" not in src, "loader references the proposal file")
        # Renaming the proposal to the real name is the ONLY way to bind.
        rep.add("gate-4", "binding requires promotion by a human",
                O.PROPOSAL != ".repo-governor.json", "")

        # --- the proposal path is run end to end, because it never had been -------
        # Until 2026-08-19 both onboard.py's docstring and its emitted $comment said
        # "rename to .repo-governor.json and commit". Doing that yields
        # UNSUPPORTED_VERSION: the proposal is a candidates document with no version,
        # no providers block and no permissions. A whole documented workflow, wrong
        # at the last step, because nothing had ever executed it.
        import subprocess as _sp, tempfile as _tf, pathlib as _pl
        ROOT_ = Path(__file__).resolve().parent.parent
        with _tf.TemporaryDirectory() as td:
            tgt = _pl.Path(td) / "r"
            tgt.mkdir()
            _sp.run(["git", "init", "-q", str(tgt)], capture_output=True)
            _sp.run(["git", "-C", str(tgt), "remote", "add", "origin",
                     "https://github.com/acme/widget.git"], capture_output=True)
            _sp.run(["git", "-C", str(tgt), "-c", "user.email=t@t", "-c", "user.name=t",
                     "commit", "-q", "--allow-empty", "-m", "i"], capture_output=True)

            # 1. detection's own proposal must NOT masquerade as bindable
            _sp.run([sys.executable, str(ROOT_ / "engine" / "onboard.py"), str(tgt), "--write"],
                    capture_output=True)
            prop = tgt / ".repo-governor.proposed.json"
            rep.add("proposal-e2e", "detection writes a proposal", prop.exists())
            if prop.exists():
                body = prop.read_text()
                rep.add("proposal-e2e", "the proposal says renaming it does not bind",
                               "DOES NOT BIND" in body.upper(),
                               "it told people to rename it, and that produced an invalid manifest")
                prop.rename(tgt / ".repo-governor.json")
                r = _sp.run([sys.executable, str(ROOT_ / "engine" / "manifest.py"), "--validate"],
                            capture_output=True, text=True, cwd=str(tgt))
                rep.add("proposal-e2e", "a renamed detection proposal is correctly REJECTED",
                               "INVALID" in r.stdout, "it is evidence, not a manifest")
                (tgt / ".repo-governor.json").unlink()

            # 2. the interactive tool must produce something that actually validates
            r = _sp.run([sys.executable, str(ROOT_ / "tools" / "onboard-interactive.py"), str(tgt)],
                        input="1\n1\n", capture_output=True, text=True)
            prop = tgt / ".repo-governor.proposed.json"
            rep.add("proposal-e2e", "onboard-interactive writes a proposal", prop.exists(), r.stderr[:120])
            if prop.exists():
                prop.rename(tgt / ".repo-governor.json")
                r = _sp.run([sys.executable, str(ROOT_ / "engine" / "manifest.py"), "--validate"],
                            capture_output=True, text=True, cwd=str(tgt))
                rep.add("proposal-e2e", "its output VALIDATES as a manifest",
                               "READY_FOR_GOVERNANCE" in r.stdout,
                               r.stdout.strip()[:160])
                m = json.loads((tgt / ".repo-governor.json").read_text())
                rep.add("proposal-e2e", "it declares an admission signal (ADR-018)",
                               bool(m["providers"]["roadmap_authority"].get("admission", {}).get("signal")))
                perms = m.get("permissions") or {}
                rep.add("proposal-e2e", "it declares a permissions block at all",
                               bool(perms),
                               "manifest.py rejects a manifest without one")
                rep.add("proposal-e2e", "it grants no write anywhere (ADR-005 deny by default)",
                               not any(v.get("write") for v in perms.values()
                                       if isinstance(v, dict)))
                rep.add("proposal-e2e", "it reads the repository id from the remote",
                               m["repository"]["id"] == "acme/widget",
                               f"got {m['repository']['id']!r}")
                (tgt / ".repo-governor.json").unlink()

            # ADR-028 is only exercised where there IS no remote. The first
            # version of this check asserted the id on a repo that had one, so a
            # hardcoded fallback sailed straight through -- the default it
            # existed to forbid sat on a path the fixture never reached.
            bare = _pl.Path(td) / "bare"
            bare.mkdir()
            _sp.run(["git", "init", "-q", str(bare)], capture_output=True)
            # Feed VALID answers. With no remote the tool must ASK, so the first
            # answer is consumed as the id. A hardcoded fallback would skip the
            # question and stamp its own value instead -- which is precisely the
            # defect ADR-028 exists for, and precisely what an earlier version of
            # this check missed by asserting on a repo that had a remote.
            r = _sp.run([sys.executable, str(ROOT_ / "tools" / "onboard-interactive.py"),
                         str(bare)], input="me/mine\n1\n1\n", capture_output=True, text=True)
            bp = bare / ".repo-governor.proposed.json"
            got = json.loads(bp.read_text())["repository"]["id"] if bp.exists() else None
            rep.add("proposal-e2e", "no remote: it asks rather than defaulting (ADR-028)",
                    got == "me/mine",
                    f"got {got!r} -- a value it was never told is a defaulted identity")


    cur = None
    for fx, check, ok, detail in rep.rows:
        if fx != cur:
            print(f"\n{fx}")
            cur = fx
        print(f"  [{'PASS' if ok else 'FAIL'}] {check}" + (f"\n         {detail}" if detail and not ok else ""))

    f = rep.fails()
    print(f"\n{len(rep.rows) - len(f)}/{len(rep.rows)} checks passed")
    print("RG-SIM-ONBOARDING-v0.1: " + ("PASS" if not f else f"FAIL ({len(f)})"))
    return 0 if not f else 1


if __name__ == "__main__":
    sys.exit(main())
