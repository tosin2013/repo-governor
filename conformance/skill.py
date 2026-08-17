#!/usr/bin/env python3
"""The shipped agent surface is checked, not just written.

`SKILL.md` and `AGENTS.md` are the two files an agent actually reads, and they
drift from the code silently. Both defects this suite exists for were shipped:

  1. every command in SKILL.md was a bare relative path (`python3 engine/...`),
     which cannot work from the repository being governed. The obvious repair --
     cd into the skill so the paths resolve -- makes the engine govern the skill
     directory, which is the defect ADR-027 had just fixed.

  2. SKILL.md told the agent to invoke an adapter directly, bypassing the
     permission chokepoint ADR-021 had just been accepted for.

Neither was a stale citation, so a citation checker would have missed both. What
catches them is asking whether the documented commands work in the posture an
agent would use them, and whether the entry points they name exist.

The half this cannot check is a document quietly contradicting a decision it
never names -- that is a reading, and ADR-002 keeps readings out of the engine.

Usage:  python3 conformance/skill.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
AGENTS = ROOT / "AGENTS.md"

CMD_RE = re.compile(r"```bash\n(.*?)```", re.S)
ADR_RE = re.compile(r"ADR-(\d{3})")
ENTRY_RE = re.compile(r"engine/([a-z_]+)\.py")


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"    {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def adr_status(num):
    for p in ROOT.glob(f"docs/adrs/{num}-*.md"):
        m = re.search(r"^\*\*Status\*\*:\s*(\w+)", p.read_text(), re.M)
        return m.group(1) if m else "UNSTATED"
    return None


def main():
    fails = 0
    skill = SKILL.read_text()
    agents = AGENTS.read_text() if AGENTS.exists() else ""

    print("The agent surface exists\n")
    fails += check("SKILL.md is present", SKILL.exists())
    fails += check("AGENTS.md is present — governance is pushed, not only pulled", AGENTS.exists())
    fails += check("CLAUDE.md points at AGENTS.md rather than duplicating it",
                   (ROOT / "CLAUDE.md").exists() and "AGENTS.md" in (ROOT / "CLAUDE.md").read_text())

    print("\nSKILL.md teaches an invocation that works from the governed repository\n")

    # 1. A bare relative engine path only resolves inside this checkout, which is
    #    the one repository you are almost never governing.
    bare = [ln.strip() for ln in skill.splitlines() if re.search(r"python3 engine/", ln)]
    fails += check("no bare `python3 engine/` path in SKILL.md", not bare, str(bare[:2]))

    # 2. Nor a bare adapter path -- that would also bypass the ADR-021 gate.
    bare_ad = [ln.strip() for ln in skill.splitlines() if re.search(r"python3 adapters/", ln)]
    fails += check("no direct adapter invocation in SKILL.md", not bare_ad, str(bare_ad[:2]))

    # 3. It must say how to locate the engine, or `$RG` is an unanswered question.
    fails += check("SKILL.md explains how to locate the skill directory",
                   "RG=" in skill and "base directory" in skill.lower())

    print("\nEvery entry point the surface names exists and runs\n")

    named = sorted(set(ENTRY_RE.findall(skill + agents)))
    missing = [n for n in named if not (ROOT / "engine" / f"{n}.py").exists()]
    fails += check(f"all {len(named)} named engine entry points exist", not missing, str(missing))

    # 4. Run the ones that need no argument, in the posture the docs describe:
    #    standing in a repository, engine addressed by absolute path.
    for entry, expect in (("manifest", "MANIFEST VALID"),):
        p = subprocess.run([sys.executable, str(ROOT / "engine" / f"{entry}.py")],
                           capture_output=True, text=True, cwd=str(ROOT), timeout=120)
        fails += check(f"engine/{entry}.py runs and reports {expect!r}",
                       expect in p.stdout, p.stdout[:100] or p.stderr[:100])

    # 5. And from a repository that is NOT governed, the documented failure is
    #    the one the surface promises -- naming the path it looked in.
    with tempfile.TemporaryDirectory() as td:
        p = subprocess.run([sys.executable, str(ROOT / "engine" / "manifest.py")],
                           capture_output=True, text=True, cwd=td, timeout=120)
        out = p.stdout + p.stderr
        fails += check("an ungoverned repository yields AUTHORITY_SOURCE_MISSING naming its path",
                       "AUTHORITY_SOURCE_MISSING" in out and td in out, out[:120])

    print("\nThe surface does not cite decisions that have moved\n")

    for doc, text in (("SKILL.md", skill), ("AGENTS.md", agents),
                      *[(f"references/{p.name}", p.read_text())
                        for p in sorted((ROOT / "references").glob("*.md"))]):
        for num in sorted(set(ADR_RE.findall(text))):
            st = adr_status(num)
            if st is None:
                fails += check(f"{doc} cites ADR-{num}, which exists", False, "no such ADR")
            elif st == "Superseded":
                fails += check(f"{doc} does not cite superseded ADR-{num}", False,
                               "superseded decisions must not be cited as current")
            elif st == "Proposed":
                # Citing an unaccepted decision is allowed only where the text
                # says so -- otherwise the release treats it as normative.
                marked = re.search(r"ADR-" + num + r"[^\n]{0,80}(Proposed|experimental|not implemented)",
                                   text, re.I) or re.search(
                    r"(Proposed|experimental|held)[^\n]{0,80}ADR-" + num, text, re.I)
                fails += check(f"{doc} marks proposed ADR-{num} as unaccepted", bool(marked),
                               "cited without saying it is Proposed")

    print(f"\n{'AGENT SURFACE: CONFORMANT' if not fails else f'AGENT SURFACE: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
