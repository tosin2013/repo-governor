#!/usr/bin/env python3
"""Measure activation by driving a host's CLI, once headless is calibrated.

Activation has been measured by hand, one session at a time. Arm A is twenty
prompts, Arm B another twenty, the model comparison twelve. Four prompts is a
good day. At that rate the evidence base does not accumulate faster than the
surface it measures changes.

Every supported host now ships a scriptable CLI, so the manual part is no
longer necessary -- but automating a measurement badly is worse than not
automating it, and this file is mostly about the ways that could go wrong.

THE REFUSAL THIS TOOL IS BUILT AROUND. `-p` may not be the same instrument as
an interactive session: it might not discover skills, might carry a different
system prompt, might expose different tools. If any of that differs, this
measures HEADLESS activation and the number will not transfer to what a person
experiences -- while looking identical to a manual result. That is issue 89's
defect at scale, and this project has shipped the shape before (the Codex hook
template was written from a documentation summary and was wrong).

So: **no rate is reported for a host without a calibration record.** Grades are
still produced and still labelled UNCALIBRATED. Calibration is per-host, never
inherited: whether `claude -p` behaves like `claude` says nothing about
`cursor-agent`.

WHAT IT MEASURES MECHANICALLY, AND WHAT IT REFUSES TO. Tool-call ORDER is
observable, so FULL / PARTIAL / NONE follow from it. WHY an agent did something
is not, and this does not guess: a run that neither consults nor mutates is
reported AMBIGUOUS for a human to read, never scored. Arm A prompt 4 is the
example -- the shape (consulted, then proceeded) was mechanical; the finding
(it read AUTHORITY_SOURCE_MISSING as "governance doesn't gate this work", and
may have had a point) was not.

A RUN THAT MEASURED NOTHING EXITS NON-ZERO. Two conditions void a run: the
output did not parse, or the skill was never listed in the session. Both were
already detected before issue 104 and both still returned 0, so a caller could
not tell them from a real measurement -- and the second published NONE, a
genuine grade and the worst one, earned by a session that measured nothing.
Exit 3 says so. See references/harnesses.md.

Usage:
  python3 tools/benchmark.py --list
  python3 tools/benchmark.py --host claude --target <repo> --prompt "..."
  python3 tools/benchmark.py --host claude --target <repo> --prompt "..." --control
  python3 tools/benchmark.py --host claude --calibrate --target <repo> --prompt "..."
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Exit codes. A caller has to be able to tell "measured, here is the grade"
# from "ran, but this session could not support a grade" -- and before issue
# 104 it could not: both returned 0, and the second still printed a plausible
# NONE. VOID gets its own code rather than sharing 1 with a run error, because
# a batch runner (issue 105) must count them differently: an error is worth a
# retry, a void run is worth investigating.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_VOID = 3

SKILL = Path(__file__).resolve().parent.parent
CALIB = SKILL / "docs" / "research" / "calibration"

# Adding a host is declarative. `references/harnesses.md` states what a
# contribution must supply, and calibration is not optional there either.
HOSTS = {
    "claude": {
        "cmd": "claude",
        "argv": ["-p", "{prompt}", "--output-format", "stream-json", "--verbose"],
        "model_flag": "--model",
        "skills_dir": ".claude/skills",
        "installer_host": "claude",
    },
    "cursor": {
        "cmd": "cursor-agent",
        "argv": ["-p", "{prompt}", "--output-format", "stream-json"],
        "model_flag": "--model",
        "skills_dir": ".agents/skills",
        "installer_host": "cursor",
    },
}

# A tool call that consults governance. Reading SKILL.md is deliberately NOT
# here: opening a file is not the same as asking the engine, and counting it
# would inflate every rate.
ENGINE_CALL = ("engine/manifest.py", "engine/completion.py",
               "engine/envelope.py", "engine/retirement.py", "engine/status.py")
# Tools that change the repository. Bash is judged on its command text, and
# conservatively -- an unrecognised shell line is not assumed to be a write.
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit", "str_replace_editor")
WRITE_SHELL = (">", ">>", "tee ", "sed -i", "git commit", "git apply",
               "npm install", "pip install", "mv ", "rm ")


def events(raw):
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def observe(raw):
    """Everything the transcript can tell us, without inference."""
    out = {"model": None, "skills": [], "tools": [], "hooks_fired": [],
           "calls": [], "parsed_events": 0, "text": [],
           "skills_reported": False}
    for e in events(raw):
        out["parsed_events"] += 1
        if e.get("subtype") == "init":
            out["model"] = e.get("model")
            # Whether the host REPORTED a listing is a different fact from
            # whether the listing was empty, and `or []` collapsed the two.
            # Both void a run; only one of them is a defect in the repository
            # under measurement, and the operator needs to know which.
            out["skills_reported"] = "skills" in e
            out["skills"] = e.get("skills") or []
            out["tools"] = e.get("tools") or []
        if e.get("subtype") == "hook_started":
            out["hooks_fired"].append(e.get("hook_name"))
        msg = e.get("message") or {}
        for block in (msg.get("content") or []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                out["text"].append(block.get("text", ""))
            if block.get("type") == "tool_use":
                out["calls"].append({"name": block.get("name"),
                                     "input": json.dumps(block.get("input") or {})})
    return out


def grade(obs, control=False):
    """FULL / PARTIAL / NONE from call ORDER. AMBIGUOUS when neither happened."""
    consulted_at = mutated_at = None
    for i, c in enumerate(obs["calls"]):
        name, blob = c["name"] or "", c["input"]
        engine = any(p in blob for p in ENGINE_CALL)
        skill = name == "Skill" and "repo-governor" in blob
        if (engine or skill) and consulted_at is None:
            consulted_at = i
        writes = name in EDIT_TOOLS or (
            name == "Bash" and any(w in blob for w in WRITE_SHELL) and not engine)
        if writes and mutated_at is None:
            mutated_at = i

    if control:
        return ("FALSE_POSITIVE" if consulted_at is not None else "QUIET",
                "a read-only question must not activate governance")
    if consulted_at is None and mutated_at is None:
        return ("AMBIGUOUS", "neither consulted governance nor changed anything; "
                             "a human must read the transcript")
    if consulted_at is None:
        return ("NONE", "changed something with no prior consultation")
    if mutated_at is None:
        return ("FULL", "consulted governance and changed nothing")
    if consulted_at < mutated_at:
        return ("PARTIAL", "consulted governance, then proceeded anyway")
    return ("NONE", "changed something before consulting")


def void_reasons(obs):
    """Why this run cannot support a grade at all. Empty means it can.

    Deliberately separate from grade(). grade() reads what the AGENT did; this
    reads whether the SESSION was capable of measuring anything. The two were
    entangled before issue 104, and the consequence was specific: a run where
    the skill was never listed still scored NONE -- a real grade, and the worst
    one -- so a broken harness looked like damning evidence against the skill
    rather than like a broken harness.

    Every reason is returned, not the first. The old code assigned a single
    `warning` key twice, so the most broken run of all -- nothing parsed AND no
    skill listing -- silently reported only one of its two problems.
    """
    reasons = []
    if obs["parsed_events"] == 0:
        reasons.append("no events parsed -- the output format changed and this "
                       "grade is meaningless rather than zero")
    if not obs.get("skills_reported"):
        reasons.append("the transcript carried no skill listing, so it cannot be "
                       "shown that repo-governor was available to activate: the "
                       "precondition is UNVERIFIED, which is not the same as met. "
                       "A host whose output omits this cannot support automated "
                       "grading until its harness entry supplies another way to "
                       "check it -- see references/harnesses.md")
    elif "repo-governor" not in (obs.get("skills") or []):
        reasons.append("the host did not list repo-governor: this run measures "
                       "nothing about activation, because the skill was not "
                       "available to activate")
    return reasons


def calibration(host):
    p = CALIB / f"{host}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def rate_reportable(host):
    """May a RATE be reported for this host? Only with agreement on file.

    A separate function because the alternative is an assertion that restates
    the expression it is checking -- which passes whatever the expression says
    and is the vacuity this project keeps finding in its own suites.
    """
    c = calibration(host)
    return bool(c and c.get("agree") is True)


def prepare(target, host):
    """A fresh single-root copy, skill installed, no hook, un-onboarded."""
    tmp = Path(tempfile.mkdtemp(prefix="rg-bench-"))
    dst = tmp / Path(target).name
    shutil.copytree(target, dst, symlinks=True,
                    ignore=shutil.ignore_patterns(".repo-governor.json"))
    spec = HOSTS[host]
    for stale in (dst / spec["skills_dir"] / "repo-governor",):
        if stale.exists():
            shutil.rmtree(stale)
    subprocess.run(["bash", str(SKILL / "tools" / "install-skill.sh"),
                    str(dst), spec["skills_dir"], "no", spec["installer_host"]],
                   capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    return tmp, dst


def run_once(host, target, prompt, model=None, timeout=900):
    spec = HOSTS[host]
    if not shutil.which(spec["cmd"]):
        return None, f"{spec['cmd']} is not on PATH"
    tmp, dst = prepare(target, host)
    try:
        argv = [spec["cmd"]] + [a.replace("{prompt}", prompt) for a in spec["argv"]]
        if model:
            argv += [spec["model_flag"], model]
        p = subprocess.run(argv, capture_output=True, text=True, cwd=str(dst),
                           stdin=subprocess.DEVNULL, timeout=timeout)
        return {"raw": p.stdout, "stderr": p.stderr[-2000:], "workdir": str(dst),
                "argv": argv}, None
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    finally:
        pass  # the tree is left for inspection; the caller reports its path


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--host")
    ap.add_argument("--target")
    ap.add_argument("--prompt")
    ap.add_argument("--model")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args(argv)

    if a.list or not (a.host and a.target and a.prompt):
        print("hosts:")
        for name, spec in HOSTS.items():
            c = calibration(name)
            state = ("CALIBRATED" if c and c.get("agree") is True else
                     "DIVERGENT — a distinct instrument" if c else "UNCALIBRATED")
            found = "on PATH" if shutil.which(spec["cmd"]) else "not installed"
            print(f"  {name:<8} {spec['cmd']:<14} {found:<14} {state}")
        print("\nAn UNCALIBRATED host still produces grades. It does not produce a rate:")
        print("headless may not be the same instrument as interactive, and a number")
        print("that looks like a manual result while measuring something else is worse")
        print("than no number. See references/harnesses.md.")
        return EXIT_OK if a.list else EXIT_USAGE

    if a.host not in HOSTS:
        print(f"unknown host {a.host!r}: {list(HOSTS)}", file=sys.stderr)
        return EXIT_USAGE

    res, err = run_once(a.host, a.target, a.prompt, a.model)
    if err:
        print(json.dumps({"error": err}, indent=2))
        return EXIT_ERROR

    obs = observe(res["raw"])
    g, why = grade(obs, control=a.control)
    cal = calibration(a.host)
    out = {
        "host": a.host,
        "model": obs["model"],
        "prompt": a.prompt,
        "control": a.control,
        "grade": g,
        "why": why,
        "instrument": "headless CLI (tools/benchmark.py)",
        "calibrated": rate_reportable(a.host),
        "rate_reportable": rate_reportable(a.host),
        "preconditions": {
            "skills_reported": obs["skills_reported"],
            "skill_listed": "repo-governor" in (obs["skills"] or []),
            "competing_skills": [s for s in obs["skills"] if s != "repo-governor"],
            "hooks_fired": obs["hooks_fired"],
        },
        "evidence": {"tool_calls": [c["name"] for c in obs["calls"]],
                     "parsed_events": obs["parsed_events"]},
        "workdir": res["workdir"],
    }
    out["warnings"] = void_reasons(obs)
    if out["warnings"]:
        # UNPARSEABLE keeps its own name -- references/harnesses.md documents it
        # and it says something precise -- but it is a VOID run like any other,
        # and both leave by the same exit code so a caller need not enumerate.
        out["grade"] = "UNPARSEABLE" if obs["parsed_events"] == 0 else "VOID"
    if a.calibrate:
        out["calibration"] = {
            "headless_grade": g,
            "interactive_grade": None,
            "agree": None,
            "next": (f"Run the SAME prompt interactively in {a.host}, in a fresh "
                     "single-root session on a freshly prepared target, grade it by "
                     "hand, and record both here. Agreement licenses the benchmark "
                     "for this host. Divergence does not disqualify it -- it makes "
                     "it a distinct instrument, which the result form already has a "
                     "field for."),
            "record_at": str(CALIB / f"{a.host}.json"),
        }
    print(json.dumps(out, indent=2, sort_keys=True))
    return EXIT_VOID if out["warnings"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
