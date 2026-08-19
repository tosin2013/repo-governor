#!/usr/bin/env python3
"""The hook is exercised on real payloads, because its defects only appear there.

Two were found this way while it was being written, and neither would have
survived contact with a fixture that shared the implementation's assumptions:

  1. the disposition regex missed every real payload, because hosts nest the
     engine's stdout as an ESCAPED JSON string -- `\\"disposition\\"`, not
     `"disposition"`. The capture silently recorded `null`.

  2. worse, a null disposition fell through to a scope check that returned
     "outside declared in_scope" for every path. A real compiled envelope for a
     real GitHub issue has `in_scope: []`, so that branch produced a confident
     refusal with a fabricated reason on every write. In blocking mode it would
     have blocked all editing while stating something untrue.

The second is why this suite asserts what the hook must NOT say as carefully as
what it must. A governance tool that refuses confidently for the wrong reason is
worse than one that stays quiet.

Usage:  python3 conformance/hooks.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "tools" / "hooks" / "governance-hook.py"
TEMPLATES = ROOT / "tools" / "hooks"

REFUSAL = ("NO_EXECUTION_AUTHORITY", "AUTHORITY_WITHDRAWN", "CONFLICT", "UNKNOWN")


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"    {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def run(moment, payload, *flags, cwd=None, env=None):
    e = None
    if env:
        import os
        e = {**os.environ, **env}
    p = subprocess.run([sys.executable, str(HOOK), moment, *flags],
                       input=json.dumps(payload), capture_output=True,
                       text=True, cwd=cwd or str(ROOT), env=e)
    try:
        out = json.loads(p.stdout) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        out = {"__unparseable__": p.stdout}
    return p.returncode, out, p.stderr


def main():
    fails = 0
    print("HOOK CONFORMANCE\n")

    fails += check("hook exists and is executable", HOOK.exists())
    if not HOOK.exists():
        return 1

    # --- silence where there is no authority to speak from -----------------
    with tempfile.TemporaryDirectory() as td:
        rc, out, _ = run("prompt", {"session_id": "t", "cwd": td}, cwd=td)
        fails += check("ungoverned repository: prompt moment says nothing",
                       rc == 0 and out == {}, f"rc={rc} out={out}")
        rc, out, _ = run("write", {"session_id": "t", "cwd": td,
                                   "tool_input": {"file_path": f"{td}/x.py"}}, cwd=td)
        fails += check("ungoverned repository: write moment never blocks",
                       rc == 0 and out == {}, f"rc={rc} out={out}")

    # --- the push surface, which is the whole point ------------------------
    rc, out, _ = run("prompt", {"session_id": "t", "cwd": str(ROOT)})
    ctx = out.get("additionalContext", "")
    fails += check("governed repository: prompt moment injects the requirement",
                   rc == 0 and bool(ctx))
    fails += check("injected text names the engine entry point",
                   "completion.py" in ctx)
    fails += check("injected text states admission is not authorization",
                   "INV-002" in ctx)
    fails += check("prompt moment never blocks, whatever it says",
                   rc == 0 and "permissionDecision" not in json.dumps(out))

    # --- operator-visible delivery proof -----------------------------------
    # An agent that has merely READ .claude/settings.json can describe the
    # hooks convincingly. systemMessage is rendered by the host to the
    # operator, so it distinguishes "the hook ran" from "the model inferred it".
    rc, out, _ = run("prompt", {"session_id": "t", "cwd": str(ROOT)})
    fails += check("delivery proof is off by default", "systemMessage" not in out)
    rc, out, _ = run("prompt", {"session_id": "t", "cwd": str(ROOT)},
                     env={"RG_HOOK_VERBOSE": "1"})
    fails += check("RG_HOOK_VERBOSE=1 emits an operator-visible systemMessage",
                   "systemMessage" in out and "governance injected" in out.get("systemMessage", ""),
                   f"got {out.get('systemMessage')!r}")
    with tempfile.TemporaryDirectory() as td:
        rc, out, _ = run("prompt", {"session_id": "t", "cwd": td}, cwd=td,
                         env={"RG_HOOK_VERBOSE": "1"})
        fails += check("verbose mode still says nothing in an ungoverned repository",
                       out == {}, f"got {out}")

    # --- capture: the escaped-quote defect ---------------------------------
    sess = ROOT / ".repo-governor" / "sessions"
    # The engine is RUN, not imitated. A hand-written fixture here passed while
    # the hook searched for "disposition" and completion.py emits "decision".
    real = subprocess.run([sys.executable, str(ROOT / "engine" / "completion.py"), "36"],
                          capture_output=True, text=True, cwd=str(ROOT)).stdout
    fails += check("engine produced output to capture from", bool(real.strip()))
    real_disp = json.loads(real).get("decision") if real.strip() else None

    for shape, label in (
        ({"stdout": real}, "real-engine-output-nested"),
        (real, "real-engine-output-plain"),
    ):
        sid = re.sub(r"[^A-Za-z0-9_.-]", "_", f"conf_{label}")
        run("capture", {"session_id": sid, "cwd": str(ROOT),
                        "tool_input": {"command": "python3 engine/completion.py 36"},
                        "tool_response": shape})
        f = sess / f"{sid}.json"
        got = json.loads(f.read_text())["disposition"] if f.exists() else None
        fails += check(f"capture reads the verdict from {label}",
                       got is not None and got == real_disp,
                       f"got {got!r}, engine said {real_disp!r}")

        # --- the fabricated-reason defect ----------------------------------
        rc, out, _ = run("write", {"session_id": sid, "cwd": str(ROOT),
                                   "tool_input": {"file_path": "README.md"}})
        said = json.dumps(out)
        fails += check(f"write under a refusal ({label}) names the real verdict",
                       real_disp in said if real_disp in REFUSAL else True)
        fails += check(f"write under a refusal ({label}) invents no scope claim",
                       "in_scope" not in said and "envelope" not in said,
                       "claimed a scope verdict the providers cannot support")
        if f.exists():
            f.unlink()

    # --- an unreadable verdict must produce silence, not a guess -----------
    sid = "conf_noverdict"
    (sess).mkdir(parents=True, exist_ok=True)
    (sess / f"{sid}.json").write_text(json.dumps({"authority_id": "36", "disposition": None}))
    rc, out, _ = run("write", {"session_id": sid, "cwd": str(ROOT),
                               "tool_input": {"file_path": "README.md"}})
    fails += check("no readable verdict: the hook stays quiet rather than guessing",
                   rc == 0 and out == {}, f"said {out}")
    (sess / f"{sid}.json").unlink()

    # --- advisory is the default, and it must not block --------------------
    sid = "conf_advisory"
    (sess / f"{sid}.json").write_text(json.dumps(
        {"authority_id": "36", "disposition": "NO_EXECUTION_AUTHORITY"}))
    rc, out, _ = run("write", {"session_id": sid, "cwd": str(ROOT),
                               "tool_input": {"file_path": "README.md"}}, "--exit2-on-deny")
    enforcing = (json.loads((ROOT / ".repo-governor.json").read_text())
                 .get("repo_governor", {}).get("enforcement", "advisory")) == "blocking"
    fails += check("advisory manifest: --exit2-on-deny alone does not block",
                   rc == 0 and "permissionDecision" not in json.dumps(out) if not enforcing else True,
                   f"rc={rc}; the flag must not override the manifest")

    # --- the completion firewall -------------------------------------------
    (sess / f"{sid}.json").write_text(json.dumps(
        {"authority_id": "5", "disposition": "STOP_COMPLETE"}))
    rc, out, _ = run("write", {"session_id": sid, "cwd": str(ROOT),
                               "tool_input": {"file_path": "README.md"}})
    fails += check("STOP_COMPLETE is surfaced before a write (ADR-023)",
                   "STOP_COMPLETE" in json.dumps(out))
    (sess / f"{sid}.json").unlink()

    # --- AUTHORITY_SOURCE_MISSING is not a governance refusal --------------
    # Tested by BEHAVIOUR, not by reading the constant. The first version of
    # this check compared the suite's own copy of REFUSAL against itself and
    # survived a mutation that added AUTHORITY_SOURCE_MISSING to the hook --
    # the same tautology shape as PR 43's `wrong == dict(wrong)`.
    src = HOOK.read_text()
    (sess / f"{sid}.json").write_text(json.dumps(
        {"authority_id": "36", "disposition": "AUTHORITY_SOURCE_MISSING"}))
    rc, out, _ = run("write", {"session_id": sid, "cwd": str(ROOT),
                               "tool_input": {"file_path": "README.md"}}, "--exit2-on-deny")
    said = json.dumps(out)
    fails += check("AUTHORITY_SOURCE_MISSING does not refuse a write",
                   rc == 0 and "permissionDecision" not in said
                   and "does not carry execution authority" not in said,
                   "an onboarding disposition treated as a governance refusal "
                   "would stop all editing in every un-onboarded repository")
    (sess / f"{sid}.json").unlink()

    # --- per-host templates -------------------------------------------------
    for host, ev in (("claude", "UserPromptSubmit"), ("cursor", "beforeSubmitPrompt"),
                     ("codex", None)):
        t = TEMPLATES / f"{host}.json"
        fails += check(f"{host} config template exists", t.exists())
        if t.exists():
            try:
                cfg = json.loads(t.read_text())
                fails += check(f"{host} template is valid JSON", True)
                fails += check(f"{host} template invokes the shared script",
                               "governance-hook.py" in json.dumps(cfg))
                if ev:
                    fails += check(f"{host} template registers its prompt-time event ({ev})",
                                   ev in json.dumps(cfg))
            except json.JSONDecodeError as e:
                fails += check(f"{host} template is valid JSON", False, str(e))

    # --- stdlib only (ADR-011) ----------------------------------------------
    third_party = [l for l in src.splitlines()
                   if l.startswith("import ") or l.startswith("from ")]
    bad = [l for l in third_party
           if not any(m in l for m in ("json", "os", "re", "subprocess", "sys",
                                       "pathlib", "__future__", "engine"))]
    fails += check("hook imports stdlib only (ADR-011)", not bad, str(bad))

    print(f"\n{'HOOKS: CONFORMANT' if not fails else f'HOOKS: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
