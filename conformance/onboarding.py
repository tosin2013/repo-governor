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



def _parse_form(path):
    """(ok, detail). Needs a YAML parser; names the missing one rather than skipping.

    Same rule as conformance/_preflight.py: an absent dependency makes a verdict
    red WITH ITS CAUSE, never green by omission. A malformed issue form is
    exactly the defect worth catching -- GitHub does not reject it, it quietly
    serves a blank issue box instead, so the template looks installed while
    asking nothing.
    """
    import subprocess as sp
    try:
        import yaml
        d = yaml.safe_load(path.read_text())
    except ImportError:
        rb = sp.run(["ruby", "-ryaml", "-rjson", "-e",
                     f"print YAML.load_file({str(path)!r}).to_json"],
                    capture_output=True, text=True)
        if rb.returncode != 0:
            return False, ("no YAML parser available -- install pyyaml or ruby. "
                           "Skipping would report a malformed form as conformant.")
        d = json.loads(rb.stdout)
    except Exception as e:
        return False, f"YAML does not parse: {e}"

    for k in ("name", "description", "body"):
        if k not in d:
            return False, f"missing required top-level key: {k}"
    for i, b in enumerate(d["body"]):
        t = b.get("type")
        if t not in ("markdown", "input", "textarea", "dropdown", "checkboxes"):
            return False, f"field {i}: unknown type {t!r}"
        if t == "markdown":
            continue
        if not b.get("id"):
            return False, f"field {i} ({t}): no id"
        if not (b.get("attributes") or {}).get("label"):
            return False, f"field {i} ({t}): no attributes.label"
        if t == "dropdown" and not b["attributes"].get("options"):
            return False, f"dropdown {b['id']}: no options"
    return True, ""


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
                # Two checks, because the generator emitted admission.signal --
                # which the adapter ignores -- and no env block at all,
                # producing a manifest that validated as READY_FOR_GOVERNANCE
                # and then answered PROVIDER_UNAVAILABLE for every id.
                #
                # 1. the vars whose ABSENCE makes the adapter refuse. Only these
                #    are required; the adapter reads three others that are
                #    optional, and demanding all five was this check's first,
                #    wrong version.
                import re as _re2
                adp = (ROOT_ / "adapters" / "github-projects").read_text()
                env_ = m["providers"]["roadmap_authority"].get("env", {})
                for var, why in (("REPO_GOVERNOR_GH_REPO",
                                  "an adapter that cannot tell which repository it "
                                  "reads must not answer (ADR-028)"),
                                 ("REPO_GOVERNOR_GH_ADMISSION",
                                  "the admission signal is declared, never assumed "
                                  "(ADR-018)")):
                    rep.add("proposal-e2e", f"the manifest supplies {var}",
                            bool(env_.get(var)), why)

                # 2. and nothing the adapter does not read -- generic drift catch
                #    in the other direction: a key nobody consumes is dead config
                #    that looks like configuration.
                known = set(_re2.findall(
                    r'os\.environ\.get\(\s*"(REPO_GOVERNOR_GH_[A-Z_]+)"', adp))
                stray = sorted(set(env_) - known)
                rep.add("proposal-e2e", "the manifest sets no env the adapter ignores",
                        not stray, f"{stray} is dead config that reads as configuration")

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
            # The tool prints a URL. A URL that 404s is worse than no URL: it
            # tells someone their tracker is a gap AND that nobody wants to hear
            # about it. Check the template exists and that the two names agree.
            # Every issue form is parsed, not grepped. A malformed one does not
            # error -- GitHub serves a blank issue box instead, so it looks
            # installed while asking none of its questions.
            for name in ("adapter-request.yml", "activation-result.yml", "config.yml"):
                f = ROOT_ / ".github" / "ISSUE_TEMPLATE" / name
                rep.add("templates", f"{name} exists", f.exists())
                if f.exists() and name != "config.yml":
                    ok_f, why_f = _parse_form(f)
                    rep.add("templates", f"{name} is a well-formed issue form", ok_f, why_f)
                    rep.add("templates", f"{name} carries the public-repo rule (51)",
                            "51" in f.read_text() and "public" in f.read_text().lower())

            # The activation form must not invite a run that cannot be scored.
            av = (ROOT_ / ".github" / "ISSUE_TEMPLATE" / "activation-result.yml").read_text()
            for phrase, why in (
                ("One prompt per session", "batching measures persistence, not activation"),
                ("did not correct the agent", "a rescued miss is destroyed data"),
                ("never named Repo Governor", "naming it guarantees activation"),
                ("competing", "a rate without its field cannot be compared"),
            ):
                rep.add("templates", f"activation form asks about: {phrase}",
                        phrase.lower() in av.lower(), why)

            # The self-test must not become a mechanical checklist. Its whole
            # point is that the mechanical half proves nothing: a skill can be
            # installed, a manifest valid, and the model still never consult it.
            st = (ROOT_ / "tools" / "selftest.py")
            rep.add("templates", "selftest exists", st.exists())
            if st.exists():
                sb = st.read_text()
                rep.add("templates", "selftest says the mechanical half is insufficient",
                        "nowhere near sufficient" in sb,
                        "a green checklist that does not measure activation is the "
                        "exact failure ADR-001 names")
                rep.add("templates", "selftest carries a control prompt",
                        "CONTROL" in sb and "false positive" in sb,
                        "without one, a skill that fires on everything scores perfectly")
                rep.add("templates", "selftest tells the user what to do at <3/3",
                        "AGENTS.md" in sb and "hook" in sb,
                        "a diagnostic with no remedy is a complaint")
                rep.add("templates", "selftest links the report form",
                        "activation-result.yml" in sb)
                r_st = _sp.run([sys.executable, str(st), td], capture_output=True, text=True)
                rep.add("templates", "selftest runs on an ungoverned repo without crashing",
                        r_st.returncode == 0 and "not onboarded" in r_st.stdout,
                        r_st.stderr[:120])

            # The PR form must carry the two defects this repository actually has.
            pr = (ROOT_ / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text()
            rep.add("templates", "PR template asks whether the test was mutated",
                    "mutated" in pr.lower(),
                    "PR 43 shipped a tautology that passed and looked like coverage")
            rep.add("templates", "PR template warns about closing keywords",
                    "closing verb" in pr.lower(),
                    "this repository has closed the same issue twice by accident")
            rep.add("templates", "PR template asks which authority admits the work",
                    "Authority:" in pr, "INV-002: admission is not authorization")

            tmpl = ROOT_ / ".github" / "ISSUE_TEMPLATE" / "adapter-request.yml"
            tool_src = (ROOT_ / "tools" / "onboard-interactive.py").read_text()
            rep.add("proposal-e2e", "the adapter-request template exists", tmpl.exists(),
                    "onboard-interactive.py links to it")
            rep.add("proposal-e2e", "the tool links to the template that exists",
                    tmpl.name in tool_src,
                    "a 404 tells someone their tracker is a gap and nobody wants to hear it")
            if tmpl.exists():
                body = tmpl.read_text()
                rep.add("proposal-e2e", "the template asks what ADMITTED means (ADR-018)",
                        "ADMITTED mean" in body,
                        "the one question detection can never answer")
                rep.add("proposal-e2e", "the template asks how work is WITHDRAWN",
                        "WITHDRAWN" in body,
                        "an agent working on withdrawn work is the failure this prevents")
                # PARSE it, not just grep it. A malformed issue form does not
                # error -- GitHub silently falls back to a blank issue box, so
                # the template appears to work while asking none of its
                # questions. String checks cannot see that.
                ok_parse, why = _parse_form(tmpl)
                rep.add("proposal-e2e", "the template is a well-formed GitHub issue form",
                        ok_parse, why)
                rep.add("proposal-e2e", "the template carries the public-repo warning",
                        "51" in body and "public" in body,
                        "requesters must not paste private workspace content")

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
