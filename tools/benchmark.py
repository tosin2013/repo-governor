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
import time
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

_T0 = time.monotonic()


def dbg(on, msg):
    """Progress, to STDERR. Never stdout -- stdout is the JSON record, and a
    caller that pipes it into jq must not have to filter our chatter out."""
    if on:
        print(f"[{time.monotonic() - _T0:7.1f}s] {msg}", file=sys.stderr, flush=True)


def _echo_new(path, shown):
    """Echo transcript lines that appeared since last call. Returns the count."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return shown
    for line in lines[shown:]:
        dbg(True, "  | " + _event_line(line))
    return len(lines)


def _event_line(line):
    """One streamed transcript event, compressed to something readable."""
    try:
        e = json.loads(line)
    except json.JSONDecodeError:
        return line.rstrip()[:120]
    sub = e.get("subtype") or e.get("type") or "?"
    names = [b.get("name") for b in blocks(e) if b.get("type") == "tool_use"]
    return f"{sub}" + (f"  tool_use: {', '.join(n for n in names if n)}" if names else "")


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


def events(raw, tally=None):
    """Parsed events, skipping anything that is not a JSON object.

    A transcript is an EXTERNAL format that changes without notice -- the same
    premise the calibration refusal is built on -- and it can also be truncated
    mid-write. Neither may raise: the tool already knows how to say a run
    cannot be graded (UNPARSEABLE, VOID, exit 3), and a traceback is the one
    outcome that produces neither a grade nor a refusal while destroying the
    evidence as well (issue 109).
    """
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            if tally is not None:
                tally["unparsed_lines"] += 1
            continue
        if not isinstance(e, dict):
            # A bare string or number where an object was assumed. Skipping
            # silently would make this its own blind spot, so it is counted.
            if tally is not None:
                tally["skipped_events"] += 1
            continue
        yield e


def blocks(e):
    """Content blocks of an event, or none. Never raises on an odd shape.

    `message` was assumed to be a dict and `content` a list. Real transcripts
    carry neither guarantee, and `or {}` defends only against None -- which is
    why a `str` crashed a real 228-second run. The same expression existed in
    two places, and the duplication is why only one of them was ever noticed.
    """
    msg = e.get("message")
    if not isinstance(msg, dict):
        return []
    content = msg.get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict)]


def observe(raw):
    """Everything the transcript can tell us, without inference."""
    out = {"model": None, "skills": [], "tools": [], "hooks_fired": [],
           "calls": [], "parsed_events": 0, "text": [],
           "skills_reported": False, "unparsed_lines": 0, "skipped_events": 0}
    for e in events(raw, out):
        out["parsed_events"] += 1
        if e.get("subtype") == "init":
            out["model"] = e.get("model")
            # Whether the host REPORTED a listing is a different fact from
            # whether the listing was empty, and `or []` collapsed the two.
            # Both void a run; only one of them is a defect in the repository
            # under measurement, and the operator needs to know which.
            # A listing of the wrong type is not a listing. Treating
            # "skills": "not-a-list" as reported would claim the precondition
            # was checked when nothing checkable arrived.
            sk = e.get("skills")
            out["skills_reported"] = isinstance(sk, list)
            out["skills"] = sk if isinstance(sk, list) else []
            tl = e.get("tools")
            out["tools"] = tl if isinstance(tl, list) else []
        if e.get("subtype") == "hook_started":
            out["hooks_fired"].append(e.get("hook_name"))
        for block in blocks(e):
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


def install_into(dst, spec):
    """Install the skill into a prepared copy. Returns (ok, detail).

    Its exit status used to be discarded. A failed install then produced a
    VOID verdict reading "the host did not list repo-governor", which sends an
    operator to look at the skill when the cause was an install that never
    happened -- the exact misattribution issue 104 added the UNVERIFIED
    distinction to prevent, surviving one function away from the fix.
    """
    p = subprocess.run(["bash", str(SKILL / "tools" / "install-skill.sh"),
                        str(dst), spec["skills_dir"], "no", spec["installer_host"]],
                       capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=300)
    if p.returncode != 0:
        return False, ((p.stderr or p.stdout or "").strip() or
                       f"exit {p.returncode}, no output")[-800:]
    return True, ""


def prepare(target, host, debug=False):
    """A fresh single-root copy, skill installed, no hook, un-onboarded.

    Returns (tmp, dst, error). The copy is wholesale and can take minutes on a
    target carrying node_modules, with nothing on screen -- which is most of
    why issue 107 was filed. It cannot be narrowed: the agent has to see the
    same repository, so an ignore list would change what is measured.
    """
    tmp = Path(tempfile.mkdtemp(prefix="rg-bench-"))
    dst = tmp / Path(target).name
    dbg(debug, f"copying {target} -> {dst}")
    dbg(debug, "  (wholesale, including any node_modules; this is the slow part)")
    t = time.monotonic()
    shutil.copytree(target, dst, symlinks=True,
                    ignore=shutil.ignore_patterns(".repo-governor.json"))
    dbg(debug, f"copied in {time.monotonic() - t:.1f}s")
    spec = HOSTS[host]
    for stale in (dst / spec["skills_dir"] / "repo-governor",):
        if stale.exists():
            shutil.rmtree(stale)
    ok, detail = install_into(dst, spec)
    if not ok:
        return tmp, dst, f"the skill did not install: {detail}"
    dbg(debug, f"installed into {spec['skills_dir']}")
    return tmp, dst, None


def run_once(host, target, prompt, model=None, timeout=900, debug=False):
    spec = HOSTS[host]
    if not shutil.which(spec["cmd"]):
        return None, f"{spec['cmd']} is not on PATH"
    tmp, dst, err = prepare(target, host, debug)
    if err:
        # A setup failure is a RUN ERROR, not a void measurement. It did not
        # fail to measure; it failed to get as far as measuring, and the two
        # send an operator to different places.
        return None, err
    argv = [spec["cmd"]] + [a.replace("{prompt}", prompt) for a in spec["argv"]]
    if model:
        argv += [spec["model_flag"], model]
    # The transcript is written to disk BEFORE it is parsed, and under
    # --debug as each line arrives. A parse defect must not be able to destroy
    # a session: issue 109 cost a real 228-second run whose transcript existed
    # only in memory, so the event that crashed the parser could not even be
    # examined afterwards. Re-parsing a saved file costs nothing, and a saved
    # file is what a fixture is made from.
    tpath = tmp / "transcript.jsonl"
    dbg(debug, f"workdir {dst}")
    dbg(debug, f"transcript {tpath}")
    dbg(debug, "exec " + " ".join(argv))
    # ONE path, whatever --debug says. The child writes straight to the
    # transcript and to a stderr file: no pipes, so nothing can deadlock on a
    # full buffer, and no watchdog thread, because polling never blocks.
    #
    # It used to be two paths, and the one without --debug lost the transcript
    # on a timeout -- subprocess.run raises before the write. Persistence was
    # added by issue 109 so that a run could never be lost again, and it was
    # conditional on a flag whose purpose is unrelated. The 900s run behind
    # this repository's first calibration survived by that coincidence.
    #
    # --debug now decides only whether the file is echoed while it grows.
    epath = tmp / "host-stderr.txt"
    t0 = time.monotonic()
    timed_out = False
    try:
        with open(tpath, "w", encoding="utf-8") as fh, \
                open(epath, "w", encoding="utf-8") as efh:
            proc = subprocess.Popen(argv, stdout=fh, stderr=efh, text=True,
                                    cwd=str(dst), stdin=subprocess.DEVNULL)
            shown = 0
            while True:
                rc = proc.poll()
                if debug:
                    shown = _echo_new(tpath, shown)
                if rc is not None:
                    break
                if time.monotonic() - t0 > timeout:
                    proc.kill()
                    proc.wait()
                    timed_out = True
                    break
                time.sleep(0.25)
        out = tpath.read_text(encoding="utf-8")
        errtxt = epath.read_text(encoding="utf-8")
        if timed_out:
            raise subprocess.TimeoutExpired(argv, timeout)
        dbg(debug, f"host exited; {len(out.splitlines())} transcript lines")
        return {"raw": out, "stderr": errtxt[-2000:], "workdir": str(dst),
                "transcript": str(tpath), "argv": argv}, None
    except subprocess.TimeoutExpired:
        # The transcript is already on disk and is worth more than this
        # message. Naming it is the minimum that makes persistence useful --
        # without --debug nothing else would ever print the path. Returning a
        # partial RECORD rather than an error is issue 111 and stays there.
        return None, (f"timed out after {timeout}s -- the transcript up to that "
                      f"point is at {tpath}")


def measure(host, target, prompt, model=None, control=False, debug=False):
    """One prompt, one fresh session, one record. Returns (record, error).

    Extracted from main() for issue 105: a suite is this, twenty-three times.
    Keeping it in main() would have meant a second copy of the void rules, and
    a second copy is how the batch path quietly stops honouring them.
    """
    res, err = run_once(host, target, prompt, model, debug=debug)
    if err:
        return None, err
    obs = observe(res["raw"])
    g, why = grade(obs, control=control)
    out = {
        "host": host,
        "model": obs["model"],
        "prompt": prompt,
        "control": control,
        "grade": g,
        "why": why,
        "instrument": "headless CLI (tools/benchmark.py)",
        "calibrated": rate_reportable(host),
        "rate_reportable": rate_reportable(host),
        "preconditions": {
            "skills_reported": obs["skills_reported"],
            "skill_listed": "repo-governor" in (obs["skills"] or []),
            "competing_skills": [s for s in obs["skills"] if s != "repo-governor"],
            "hooks_fired": obs["hooks_fired"],
        },
        "evidence": {"tool_calls": [c["name"] for c in obs["calls"]],
                     "parsed_events": obs["parsed_events"],
                     "unparsed_lines": obs["unparsed_lines"],
                     "skipped_events": obs["skipped_events"]},
        "workdir": res["workdir"],
        "transcript": res.get("transcript"),
    }
    out["warnings"] = void_reasons(obs)
    if out["warnings"]:
        # UNPARSEABLE keeps its own name -- references/harnesses.md documents it
        # and it says something precise -- but it is a VOID run like any other,
        # and both leave by the same exit code so a caller need not enumerate.
        out["grade"] = "UNPARSEABLE" if obs["parsed_events"] == 0 else "VOID"
    return out, None


PROTOCOL = SKILL / "docs" / "research" / "activation-protocol.md"


def load_suite(path):
    """Read a prompt set and check it still matches the protocol. (doc, error).

    The verbatim check is the point of this function. Twenty prompts now live
    in two places -- prose that explains them and JSON that runs them -- and
    the failure mode is silent: an edited prompt still runs, still grades, and
    produces numbers that are not comparable with anything measured before it.
    So a drifted suite refuses to load rather than quietly measuring something
    else.
    """
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return None, f"cannot read suite {path}: {e}"
    prompts = doc.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        return None, f"{path} declares no prompts"
    for i, pr in enumerate(prompts):
        if not isinstance(pr, dict) or not pr.get("text") or "id" not in pr:
            return None, f"{path} prompt {i} needs an id and a text"
    if not PROTOCOL.is_file():
        return None, (f"{PROTOCOL} is missing, so no prompt here can be checked "
                      "against the protocol that defines it. An install prunes "
                      "docs/research/; run a suite from a source checkout.")
    proto = PROTOCOL.read_text(encoding="utf-8")
    drifted = [pr["id"] for pr in prompts if f"`{pr['text']}`" not in proto]
    if drifted:
        return None, (f"prompts {drifted} are not in {PROTOCOL} verbatim. Edit the "
                      "protocol and re-extract; a suite that has drifted from it "
                      "measures something no earlier result is comparable with.")
    return doc, None


def suite_plan(doc, host, target, path):
    """What a run WOULD do. Costs nothing; a real arm costs hours."""
    prompts = doc["prompts"]
    return {
        "suite": str(path),
        "arm": doc.get("arm"),
        "host": host,
        "target": target,
        "prompts": len(prompts),
        "controls": sum(1 for p in prompts if p.get("control")),
        "measured": sum(1 for p in prompts if not p.get("control")),
        # Not a field saying "the check passed" -- load_suite already refused
        # if it had not, so such a field would restate itself and could never
        # be false. This names WHAT was checked against, which is a fact.
        "checked_against": str(PROTOCOL),
        "sessions": (f"{len(prompts)} -- one per prompt. prepare() copies the target "
                     "and spawns a fresh process each time, which is what keeps the "
                     "protocol's one-prompt-per-session rule rather than breaking it."),
        "ids": [p["id"] for p in prompts],
    }


def run_suite(host, target, doc, path, out_dir=None, model=None, debug=False):
    """Every prompt, each in its own session. Returns (summary, exit_code).

    Records stream to disk as they complete when --out is given. Twenty-three
    sessions is long enough that losing the lot to one timeout is a real cost,
    and writing at the end is how that happens.
    """
    if out_dir:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
    records, errors = [], []
    for n, pr in enumerate(doc["prompts"], 1):
        dbg(debug, f"--- prompt {pr['id']} ({n}/{len(doc['prompts'])}): "
                   f"{pr['text'][:60]}")
        rec, err = measure(host, target, pr["text"], model,
                           bool(pr.get("control")), debug=debug)
        if err:
            errors.append({"id": pr["id"], "error": err})
            print(f"  {pr['id']:<4} ERROR   {err}", file=sys.stderr)
            continue
        rec["id"] = pr["id"]
        rec["lane"] = pr.get("lane")
        records.append(rec)
        if out_dir:
            (Path(out_dir) / f"{pr['id']}.json").write_text(
                json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
            # The transcript travels with the record. The temp trees are left
            # for inspection but nothing promises how long they last, and a
            # record whose evidence has been reaped is an assertion.
            src = rec.get("transcript")
            if src and Path(src).is_file():
                shutil.copyfile(src, Path(out_dir) / f"{pr['id']}.transcript.jsonl")
        print(f"  {pr['id']:<4} {rec['grade']:<13} {pr['text'][:56]}", file=sys.stderr)

    void = [r for r in records if r["warnings"]]
    good = [r for r in records if not r["warnings"]]
    measured = [r for r in good if not r["control"]]
    controls = [r for r in good if r["control"]]
    hist = {}
    for r in measured:
        hist[r["grade"]] = hist.get(r["grade"], 0) + 1
    chist = {}
    for r in controls:
        chist[r["grade"]] = chist.get(r["grade"], 0) + 1

    # A rate is the one output that travels without its caveats, so every
    # reason to withhold it is checked, and all of them are reported.
    withheld = []
    if not rate_reportable(host):
        withheld.append(f"{host} has no calibration record with agree: true")
    if void:
        withheld.append(f"{len(void)} run(s) measured nothing; the arm is not complete")
    if errors:
        withheld.append(f"{len(errors)} prompt(s) did not run at all")
    consulted = hist.get("FULL", 0) + hist.get("PARTIAL", 0)

    summary = {
        "suite": str(path), "arm": doc.get("arm"), "host": host,
        "prompts": len(doc["prompts"]),
        "measured": len(measured), "controls": len(controls),
        "void": len(void), "errors": len(errors),
        "grades": hist, "control_grades": chist,
        "void_ids": [r["id"] for r in void],
        "error_ids": [e["id"] for e in errors],
        "rate": (None if withheld else
                 {"consulted": consulted, "of": len(measured),
                  "definition": "FULL + PARTIAL over non-control runs that measured "
                                "something; PARTIAL counts because the agent did "
                                "consult, whatever it did next"}),
        "rate_withheld_because": withheld,
        "records_at": str(out_dir) if out_dir else
                      "not written -- pass --out to keep them",
    }
    code = EXIT_VOID if void else (EXIT_ERROR if errors else EXIT_OK)
    return summary, code


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--host")
    ap.add_argument("--target")
    ap.add_argument("--prompt")
    ap.add_argument("--model")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--suite", help="a prompt set, e.g. docs/research/prompts/arm-a.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --suite: validate and print the plan, spawn nothing")
    ap.add_argument("--out", help="with --suite: directory to write one record per prompt")
    ap.add_argument("--debug", action="store_true",
                    help="progress and the live transcript, to stderr; stdout stays JSON")
    a = ap.parse_args(argv)

    if a.suite:
        if a.host not in HOSTS:
            print(f"unknown host {a.host!r}: {list(HOSTS)}", file=sys.stderr)
            return EXIT_USAGE
        doc, err = load_suite(a.suite)
        if err:
            print(json.dumps({"error": err}, indent=2))
            return EXIT_USAGE
        dbg(a.debug, f"suite {a.suite}: {len(doc['prompts'])} prompts")
        if a.dry_run:
            print(json.dumps(suite_plan(doc, a.host, a.target, a.suite),
                             indent=2, sort_keys=True))
            return EXIT_OK
        if not a.target:
            print(json.dumps({"error": "--suite needs --target"}, indent=2))
            return EXIT_USAGE
        summary, code = run_suite(a.host, a.target, doc, a.suite, a.out,
                                  a.model, a.debug)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return code

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

    # Announced BEFORE the slow part, not from inside it. The first thing this
    # does is copy the target wholesale, which on a large repository is minutes
    # of silence -- so a debug flag whose output only begins once that is
    # finished answers "is it hung?" exactly when the question has stopped
    # being asked.
    dbg(a.debug, f"{a.host}: one prompt against {a.target}"
                 + (f" (model {a.model})" if a.model else "")
                 + (" [control]" if a.control else ""))
    out, err = measure(a.host, a.target, a.prompt, a.model, a.control, a.debug)
    if err:
        print(json.dumps({"error": err}, indent=2))
        return EXIT_ERROR
    if a.calibrate:
        out["calibration"] = {
            "headless_grade": out["grade"],
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
    dbg(a.debug, f"grade {out['grade']}"
                 + (f" -- VOID: {out['warnings'][0][:70]}" if out["warnings"] else ""))
    print(json.dumps(out, indent=2, sort_keys=True))
    return EXIT_VOID if out["warnings"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
