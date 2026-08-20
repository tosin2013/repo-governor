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

    print(f"\n{'BENCHMARK: CONFORMANT' if not fails else f'BENCHMARK: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
