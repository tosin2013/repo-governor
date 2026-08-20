#!/usr/bin/env python3
"""The benchmark refuses to report a rate it has not earned (issue 96).

Automating a measurement badly is worse than not automating it. `-p` may not be
the same instrument as an interactive session -- it might not discover skills,
might carry a different system prompt -- and if it differs, the harness measures
HEADLESS activation while producing a number indistinguishable from a manual
result. That is issue 89's defect at scale.

So the property under test is not that grading works. It is that the tool
**withholds** a rate for an uncalibrated host, and that its grader refuses to
guess where the transcript does not say.

Every check drives the real functions against synthetic transcripts. None of
this spawns a CLI: a suite that needed `claude` on PATH would be unrunnable in
CI and would quietly stop testing anything.

Usage:  python3 conformance/benchmark.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import _count as _CNT  # noqa: E402
_CNT.watch("benchmark")

import benchmark as B  # noqa: E402


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"\n         {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def transcript(*calls, model="m-1", skills=("repo-governor",)):
    """A synthetic stream-json transcript: init, then one tool call per entry."""
    lines = [json.dumps({"type": "system", "subtype": "init",
                         "model": model, "skills": list(skills), "tools": ["Bash", "Edit"]})]
    for name, inp in calls:
        lines.append(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "input": inp}]}}))
    return "\n".join(lines)


ENGINE = ("Bash", {"command": "python3 .claude/skills/repo-governor/engine/completion.py 27"})
SKILL_LOAD = ("Skill", {"name": "repo-governor"})
EDIT = ("Edit", {"file_path": "src/x.py"})
READ = ("Read", {"file_path": "SKILL.md"})


def main():
    fails = 0
    print("Grades follow the ORDER of tool calls\n")

    for label, calls, want in (
        ("consulted and changed nothing", [ENGINE], "FULL"),
        ("loaded the skill and changed nothing", [SKILL_LOAD], "FULL"),
        ("consulted, then proceeded", [ENGINE, EDIT], "PARTIAL"),
        ("changed something with no consultation", [EDIT], "NONE"),
        ("consulted only after changing", [EDIT, ENGINE], "NONE"),
    ):
        g, _ = B.grade(B.observe(transcript(*calls)))
        fails += check(f"{label} -> {want}", g == want, f"got {g}")

    print("\nIt refuses to guess where the transcript does not say\n")
    g, _ = B.grade(B.observe(transcript(READ)))
    fails += check("neither consulted nor changed -> AMBIGUOUS", g == "AMBIGUOUS",
                   f"got {g} -- scoring silence invents a result")
    fails += check("reading SKILL.md is not consulting",
                   B.grade(B.observe(transcript(READ, EDIT)))[0] == "NONE",
                   "opening a file is not asking the engine, and counting it would "
                   "inflate every rate")

    print("\nControls invert the meaning of activation\n")
    fails += check("activating on a control is a FALSE_POSITIVE",
                   B.grade(B.observe(transcript(ENGINE)), control=True)[0] == "FALSE_POSITIVE")
    fails += check("staying quiet on a control is correct",
                   B.grade(B.observe(transcript(READ)), control=True)[0] == "QUIET")

    print("\nThe transcript supplies what an operator used to write down\n")
    obs = B.observe(transcript(ENGINE, model="claude-opus-5",
                               skills=("repo-governor", "simplify")))
    fails += check("the model is read from the transcript", obs["model"] == "claude-opus-5",
                   "the field whose absence makes an earlier 20/20 unattributable")
    fails += check("the skill listing is read from the same session",
                   "repo-governor" in obs["skills"],
                   "so the precondition no longer needs a session that must be discarded")
    fails += check("competing skills are enumerated", "simplify" in obs["skills"])

    print("\nUnparseable output is not a zero\n")
    obs2 = B.observe("this is not json at all\nnor is this\n")
    fails += check("nothing parses -> no events", obs2["parsed_events"] == 0,
                   "a changed output format must not read as a perfect miss rate")

    print("\nA rate is withheld until the host is calibrated\n")
    # The property this file exists for. Read through the real function, so a
    # calibration file appearing later is honoured and one that says the
    # instruments DIVERGED does not silently license a rate.
    # Driven through fixtures, not restated. The first version of this check
    # compared `bool(cal and cal.get("agree") is True)` to itself and could not
    # fail -- written into the very suite whose subject is refusing to report a
    # number it has not earned.
    import tempfile as _tf, json as _j
    real = B.CALIB
    with _tf.TemporaryDirectory() as td:
        B.CALIB = Path(td)
        try:
            fails += check("no calibration on file -> no rate", not B.rate_reportable("claude"),
                           "an uncalibrated host must not produce a rate")
            (Path(td) / "claude.json").write_text(_j.dumps({"agree": False}))
            fails += check("a DIVERGENT calibration -> still no rate",
                           not B.rate_reportable("claude"),
                           "divergence makes it a distinct instrument, not a licensed one")
            (Path(td) / "claude.json").write_text(_j.dumps({"agree": True}))
            fails += check("agreement on file -> a rate may be reported",
                           B.rate_reportable("claude"),
                           "otherwise calibration could never license anything and the "
                           "checks above would pass trivially")
            (Path(td) / "claude.json").write_text("{not json")
            fails += check("an unreadable calibration -> no rate",
                           not B.rate_reportable("claude"),
                           "a corrupt record must not read as agreement")
        finally:
            B.CALIB = real

    src = (ROOT / "tools" / "benchmark.py").read_text(encoding="utf-8")
    fails += check("the tool states the refusal where a reader meets it",
                   "no rate is reported for a host without a calibration record" in src.lower(),
                   "a refusal nobody can find is a refusal nobody honours")

    print("\nAdding a harness is documented, and calibration is not optional there\n")
    doc = ROOT / "references" / "harnesses.md"
    fails += check("references/harnesses.md exists", doc.is_file())
    if doc.is_file():
        d = doc.read_text(encoding="utf-8")
        fails += check("it says calibration is per-host and not inherited",
                       "never inherited" in d,
                       "calibrating one CLI licenses nothing about another")
        fails += check("it says divergence does not disqualify a host",
                       "does not\ndisqualify" in d or "does not disqualify" in d,
                       "a host where headless differs is still worth measuring")
        fails += check("it says an unparseable grade is not a zero", "UNPARSEABLE" in d)
        fails += check("providers.md points at it",
                       "harnesses.md" in (ROOT / "references" / "providers.md").read_text(encoding="utf-8"))

    print("\nA void run must FAIL, not publish a plausible grade\n")
    # Issue 104. Both conditions below were already DETECTED -- each set a
    # warning -- and each still returned 0. So a caller could not tell a real
    # measurement from a session where the skill was never available to
    # activate, and the second publishes "NONE": a genuine grade, the worst
    # one, earned by a run that measured nothing. Batching that (issue 105)
    # turns one silent failure into twenty and reports them as a clean sweep.
    #
    # Driven through main() with a stubbed run_once, so the EXIT CODE is the
    # thing under test. Everything above this line tests grading and would
    # pass unchanged while main() returned 0 for all of it -- which is exactly
    # how this shipped.
    def run_main(raw, argv=("--host", "claude", "--target", ".", "--prompt", "p")):
        import contextlib
        import io
        real_run = B.run_once
        B.run_once = lambda *a, **k: ({"raw": raw, "stderr": "",
                                       "workdir": "/t", "argv": []}, None)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = B.main(list(argv))
        finally:
            B.run_once = real_run
        try:
            return rc, json.loads(buf.getvalue())
        except json.JSONDecodeError:
            return rc, {}

    rc, out = run_main(transcript(ENGINE))
    fails += check("a healthy run still exits 0", rc == 0, f"got {rc}")
    fails += check("...and still reports its grade", out.get("grade") == "FULL",
                   f"got {out.get('grade')}")

    rc, out = run_main("not json at all\nnor is this\n")
    fails += check("unparseable output exits non-zero", rc != 0,
                   "output-format drift that exits 0 reads as clean data")
    fails += check("unparseable exits VOID, not the usage or error code",
                   rc == getattr(B, "EXIT_VOID", None),
                   f"got {rc}; a run error is 1 and bad arguments are 2, so void "
                   "needs its own code or a caller cannot tell the three apart")

    rc, out = run_main(transcript(EDIT, skills=("simplify",)))
    fails += check("the skill absent from the listing exits VOID",
                   rc == getattr(B, "EXIT_VOID", None),
                   f"got {rc}; this is the run that otherwise publishes NONE")
    fails += check("...and it is not awarded a publishable grade",
                   out.get("grade") == "VOID",
                   f"got {out.get('grade')}; NONE is the worst activation result "
                   "and handing it to a session where the skill was never present "
                   "inflates the measured miss rate")

    rc, out = run_main(transcript(ENGINE, skills=()))
    fails += check("an EMPTY skill listing is the skill being absent",
                   rc == getattr(B, "EXIT_VOID", None), f"got {rc}")

    # The other branch, and the one that nearly shipped untested: a host whose
    # init event omits `skills` altogether. `or []` used to collapse it into
    # "listed nothing", which reads as a defect in the repository under test
    # when it is really a limit of the harness. Unverified is not unmet.
    no_listing = json.dumps({"type": "system", "subtype": "init", "model": "m-1"})
    rc, out = run_main(no_listing)
    fails += check("a host that never reports a listing exits VOID too",
                   rc == getattr(B, "EXIT_VOID", None),
                   f"got {rc}; a grade whose precondition is unverifiable is the "
                   "row above wearing a better disguise")
    fails += check("...and says the precondition is UNVERIFIED, not unmet",
                   any("UNVERIFIED" in w for w in (out.get("warnings") or [])),
                   "blaming the repository for a gap in the harness sends an "
                   "operator to fix the wrong thing")

    print("\nEvery void reason survives; none clobbers another\n")
    rc, out = run_main("")          # no init event AND nothing parses: void twice
    ws = out.get("warnings")
    fails += check("warnings is a list", isinstance(ws, list),
                   f"got {type(ws).__name__}")
    fails += check("a run that is void twice reports both reasons",
                   isinstance(ws, list) and len(ws) >= 2,
                   "one scalar key meant the second assignment overwrote the "
                   "first, losing a signal in the most broken run of all")

    print(f"\n{'BENCHMARK: CONFORMANT' if not fails else f'BENCHMARK: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
