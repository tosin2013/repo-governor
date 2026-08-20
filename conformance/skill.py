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

import _count as _CNT  # noqa: E402 -- alias avoids `C`, already bound to
# `completion` in two suites, where the collision silently rebound it (issue 67).
_CNT.watch("skill")


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
        # REPO_GOVERNOR_TARGET must be cleared. It declares the governed
        # repository (ADR-027) and outranks cwd -- so when this suite runs
        # THROUGH the engine, which sets it, the inherited value made an
        # ungoverned directory report MANIFEST VALID and this check fail. The
        # check was correct; its environment was not isolated from its caller.
        import os as _os2
        clean = {k: v for k, v in _os2.environ.items() if k != "REPO_GOVERNOR_TARGET"}
        p = subprocess.run([sys.executable, str(ROOT / "engine" / "manifest.py")],
                           capture_output=True, text=True, cwd=td, timeout=120, env=clean)
        out = p.stdout + p.stderr
        fails += check("an ungoverned repository yields AUTHORITY_SOURCE_MISSING naming its path",
                       "AUTHORITY_SOURCE_MISSING" in out and td in out, out[:120])

    print("\nNo third-party workspace content is carried in this public repository\n")

    # §51 forbids cross-repository leakage, and this repository is public. The
    # rule was asserted all through the Linear work and was ALREADY broken --
    # ADR-016 quoted a real issue identifier from a private workspace, found
    # only when the check was finally run rather than repeated. Synthetic
    # prefixes (ENG-, SIM-) are fine; a real workspace prefix is not.
    import subprocess as _sp3
    leaked = _sp3.run(["git", "grep", "-lIE", r"\bTOS-[0-9]{2,}"],
                      capture_output=True, text=True, cwd=str(ROOT)).stdout.split()
    fails += check("no real Linear workspace identifier is committed", not leaked, str(leaked))

    print("\nAny stated ADR count matches the ledger\n")

    # A count is a duplicated derivable fact, and duplicated state eventually
    # disagrees: AGENTS.md said "21 of 26 Accepted" after the ledger said 23,
    # because the line predated a ratification pass and nothing recomputed it.
    # Any "N of M Accepted"-shaped claim on the surface must match a recount
    # of the ledger itself -- or better, not exist at all.
    statuses = {}
    for f in sorted((ROOT / "docs" / "adrs").glob("[0-9][0-9][0-9]-*.md")):
        m = re.search(r"^\*\*Status\*\*:\s*(\w+)", f.read_text(), re.M)
        st = m.group(1) if m else "UNSTATED"
        statuses[st] = statuses.get(st, 0) + 1
    accepted, total = statuses.get("Accepted", 0), sum(statuses.values())
    count_docs = [("README.md", (ROOT / "README.md").read_text()),
                  ("AGENTS.md", agents),
                  ("docs/adrs/README.md", (ROOT / "docs" / "adrs" / "README.md").read_text())]
    for doc, text in count_docs:
        # A finditer that matches nothing runs its body zero times and the
        # suite goes green having checked NOTHING. That is the defect class
        # this whole file exists to catch, one level up: if a document is
        # rephrased, or a pattern rots, the check stops looking and never says
        # so. AGENTS.md deliberately carries no ADR count, so the floor is
        # per-document rather than global.
        seen_claims = 0
        for m in re.finditer(r"(\d+)\s+of\s+(\d+)\s+ADRs?[^.\n]{0,40}Accepted|"
                             r"(\d+)\s+ADRs?\s+—\s+\*\*(\d+)\s+Accepted|"
                             r"\*\*(\d+)\s+of\s+(\d+)\s+ADRs are Accepted|"
                             r"(\d+)\s+architectural decisions\s+\((\d+)\s+Accepted\)", text):
            nums = [g for g in m.groups() if g]
            claim = tuple(int(n) for n in nums)
            ok_claim = accepted in claim and total in claim
            seen_claims += 1
            fails += check(f"{doc} count claim {claim} matches ledger ({accepted} of {total})",
                           ok_claim, f"ledger says {accepted} Accepted of {total}")
        # README.md and docs/adrs/README.md both state a count today. If either
        # stops matching, that is a pattern that went blind, not a document
        # that got simpler -- and it must be reported as a failure.
        if doc != "AGENTS.md":
            fails += check(f"{doc} still states an ADR count this suite can read",
                           seen_claims > 0,
                           "found 0 count claims -- either the claim was removed "
                           "or the pattern stopped matching it; both need a human")

    print("\nThe decision index accounts for every decision\n")

    # A reader who finds ADR-024 and ADR-027 and nothing between has to guess
    # whether two decisions were deleted -- which would be the INV-005 failure
    # this project exists to prevent, reported by absence rather than by error.
    index = (ROOT / "docs" / "adrs" / "README.md").read_text()
    files = sorted(p.name[:3] for p in (ROOT / "docs" / "adrs").glob("[0-9][0-9][0-9]-*.md"))
    unindexed = [n for n in files if f"({n}-" not in index and f"~~{n}~~" not in index]
    fails += check(f"all {len(files)} ADR files appear in the index", not unindexed, str(unindexed))

    lo, hi = int(files[0]), int(files[-1])
    gaps = [f"{n:03d}" for n in range(lo, hi + 1) if f"{n:03d}" not in files]
    undocumented = [g for g in gaps if f"~~{g}~~" not in index]
    fails += check(f"every gap in the sequence is explained ({len(gaps)} gap(s))",
                   not undocumented, f"unexplained: {undocumented}")

    print("\nThe surface does not cite decisions that have moved\n")

    surface = [("SKILL.md", skill), ("AGENTS.md", agents),
               *[(f"references/{p.name}", p.read_text())
                 for p in sorted((ROOT / "references").glob("*.md"))],
               *[(f"docs/workflows/{p.name}", p.read_text())
                 for p in sorted((ROOT / "docs" / "workflows").glob("*.md"))]]

    # The workflow pages teach humans what to ask, so they are agent surface too
    # (issue 29's lesson: the instructions ARE the product). Same rules: no bare
    # relative engine path a reader could copy into the wrong repository.
    for doc, text in surface:
        if doc.startswith("docs/workflows/"):
            bare_wf = [ln.strip() for ln in text.splitlines()
                       if re.search(r"python3 (engine|adapters)/", ln)]
            fails += check(f"{doc} has no bare relative invocation", not bare_wf, str(bare_wf[:1]))

    for doc, text in surface:
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
            elif st == "Accepted":
                # The mirror, and the one ratification itself creates: a document
                # that called a decision `Proposed` becomes wrong the moment the
                # decision is accepted. Staleness runs in both directions and
                # only one of them is obvious.
                stale = re.search(r"ADR-" + num + r"[^\n]{0,60}`?Proposed`?", text) or re.search(
                    r"`?Proposed`?[^\n]{0,60}ADR-" + num, text)
                fails += check(f"{doc} does not still call accepted ADR-{num} proposed", not stale,
                               "ratification made this line stale")

    # --- the README's install instructions must be the ones that work --------
    # For 83 commits the README said "Clone it into a skills directory". That
    # drags this repository's own AGENTS.md, CLAUDE.md and .repo-governor.json
    # into someone else's project, and the manifest makes the engine resolve the
    # INSTALL directory as the repository under governance (ADR-027) -- it then
    # answers confidently about the wrong project. tools/install-skill.sh was
    # written to prevent exactly that and the README never mentioned it.
    rd = (ROOT / "README.md").read_text()
    fails += check("README has an Install section", "\n## Install" in rd)
    fails += check("README install uses the script", "install-skill.sh" in rd,
                   "a plain clone installs this repo's manifest into someone else's repo")
    bad = re.search(r"[Cc]lone (it |this )?into a skills director", rd)
    fails += check("README does not tell people to clone into a skills directory",
                   not bad, bad.group(0) if bad else "")
    for tool in ("onboard-interactive.py", "selftest.py"):
        fails += check(f"README points at {tool}", tool in rd)

    print("\nThe two activation instruments cannot be reported as one number\n")

    # selftest runs four prompts with a parameterized first; the protocol runs
    # twenty per arm with fixed wording. The intake form asked only for "the
    # rate", so a 3/3 and a 3/20 landed in the same field and nothing
    # downstream could tell them apart -- while those results ARE the evidence
    # base for issues 5, 42 and the model comparison (issue 89).
    form = ROOT / ".github" / "ISSUE_TEMPLATE" / "activation-result.yml"
    fails += check("the activation-result form exists", form.is_file())
    if form.is_file():
        f = form.read_text(encoding="utf-8")
        fails += check("the form asks which instrument was run",
                       "id: instrument" in f,
                       "without it a self-test score and a protocol rate pool into "
                       "one field and the difference is unrecoverable")
        fails += check("and requires it",
                       f.split("id: instrument", 1)[1].split("- type:", 1)[0].count("required: true") == 1,
                       "an optional instrument field is the same defect with extra steps")
        fails += check("it offers both instruments as choices",
                       "selftest.py" in f and "Arm A" in f and "Arm B" in f)
        # The surface issue 86 missed: the hook precondition reached the
        # recording sheet, the protocol and selftest, but not the form -- which
        # is the intake for the people least likely to know the rule exists.
        fails += check("the form carries the no-hook precondition",
                       "No hook was installed" in f,
                       "issue 86 fixed the surfaces the maintainer reads and missed "
                       "the one strangers read")

    st = (ROOT / "tools" / "selftest.py").read_text(encoding="utf-8")
    fails += check("selftest says its score is not a protocol rate",
                   "NOT A PROTOCOL RATE" in st,
                   "a user scoring 3/3 has every reason to report it as one")

    print("\nAn integration contract exists, and leads with the rule that matters\n")

    # The product is tool-independent by thesis, which only holds if somebody
    # else can wire in a tracker without touching the engine. The contract was
    # scattered across storage-backends.md (decision_history-shaped), ADR-003,
    # ADR-008 and the suites, and the single most important rule -- that an
    # integration carries governance through rather than reinventing it -- was
    # written down nowhere.
    integ = ROOT / "references" / "integrations.md"
    fails += check("references/integrations.md exists", integ.is_file())
    if integ.is_file():
        text = integ.read_text(encoding="utf-8")
        fails += check("it states the pass-through rule",
                       "does not reinvent it" in text.lower()
                       or "carries governance through" in text.lower(),
                       "an integration that reinterprets state is the failure Layer 2 "
                       "exists to catch, and it must be named first")
        fails += check("it names the 'task says READY' failure specifically",
                       "Ready, so I should work on it" in text,
                       "the abstract rule is forgettable; the concrete failure is not")
        fails += check("it cites INV-002 (admission is not authorization)",
                       "INV-002" in text)
        fails += check("it names both conformance layers as the bar",
                       "layer1.py" in text and "layer2.py" in text,
                       "a contract checked by review rather than by suite is a "
                       "contract nobody outside this repository can meet")
        fails += check("it describes all three integration tiers",
                       all(k in text for k in ("filesystem", "Dolt", "Beads")))
        fails += check("it marks Beads as NOT admitted",
                       "not admitted" in text.lower(),
                       "documenting a contract must not read as deciding to build it")
        fails += check("providers.md points at it",
                       "integrations.md" in (ROOT / "references" / "providers.md").read_text(encoding="utf-8"),
                       "the roles table must not be the only thing an implementer finds")

    print("\nThe lanes point at the governed repository's own conventions\n")

    # Repo Governor rules on authority and says nothing about house style --
    # which is correct, and was silently total: no workflow page mentioned
    # CONTRIBUTING.md, AGENTS.md, commits or pull requests at all. An agent
    # got a correct verdict and no signal to branch, to run the repository's
    # own checks, or to respect its commit rules. Every one of those happened
    # HERE only because this repository's AGENTS.md points at its
    # CONTRIBUTING.md, and that chain exists nowhere else.
    for page in ("starting-work.md", "finishing-work.md"):
        text = (ROOT / "docs" / "workflows" / page).read_text(encoding="utf-8")
        fails += check(f"{page} names the governed repository's CONTRIBUTING.md",
                       "CONTRIBUTING.md" in text,
                       "the lane that starts or lands work must say whose rules apply")
        fails += check(f"{page} names its AGENTS.md too",
                       "AGENTS.md" in text,
                       "not every harness loads it automatically")
        fails += check(f"{page} says the repository is the GOVERNED one, not the skill",
                       "governed" in text.lower(),
                       "an install carries files with the same names; naming which "
                       "repository is meant is the whole point (ADR-027)")

    print("\nThe conformance suite set is one fact, not six\n")

    # Same defect as the ADR counts above, different noun. The suite count has
    # been published as 7, 10, 11 and "eleven" simultaneously while disk held
    # 12. A count is a DERIVABLE fact, and a derivable fact restated in prose
    # is duplicated state that eventually disagrees.
    #
    # Three sources must agree, not two. Checking the filesystem against prose
    # alone would go vacuous the moment the pasted loops are replaced by a call
    # to tools/run-conformance.sh -- the runner deletes the very enumeration
    # the check inspects. So the RUNNER's own arrays are the third source, and
    # they are what catches a new suite file nobody wired in.
    truth = {f.stem for f in sorted((ROOT / "conformance").glob("[a-z]*.py"))
             if "sys.exit(main(" in f.read_text(encoding="utf-8")}

    # Floor control. If the glob breaks, every regex below also finds nothing
    # and the whole section would pass having established nothing.
    fails += check(f"the suite set was actually derived ({len(truth)} found)",
                   len(truth) >= 8 and "layer1" in truth,
                   f"{sorted(truth)} -- a broken glob reads as a clean repository")

    runner = ROOT / "tools" / "run-conformance.sh"
    fails += check("a single runner exists for CI and contributors to share",
                   runner.is_file(),
                   "without one, every document pastes its own loop and they drift")
    if runner.is_file():
        rsrc = runner.read_text(encoding="utf-8")
        declared = set()
        for arr in re.finditer(r"^(?:HERMETIC|LIVE)=\(([^)]*)\)", rsrc, re.M):
            declared |= set(arr.group(1).split())
        fails += check("the runner names every suite on disk, and no others",
                       declared == truth,
                       f"runner-only={sorted(declared - truth)} "
                       f"disk-only={sorted(truth - declared)} -- a suite the runner "
                       "does not name never runs, and nothing else would notice")

    # Any loop still pasted into prose is a second source of truth. The runner
    # replaced them; one surviving is drift waiting to happen.
    for doc in ("AGENTS.md", "CONTRIBUTING.md", "docs/installation.md",
                "docs/adrs/README.md", ".github/PULL_REQUEST_TEMPLATE.md"):
        f = ROOT / doc
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        stale = re.search(r"for s in\s+layer1[^\n]*", text)
        fails += check(f"{doc} pastes no suite loop of its own",
                       not stale,
                       (stale.group(0)[:80] if stale else "") +
                       " -- call tools/run-conformance.sh instead")

    # Adapters drift exactly the same way, and did: adding one made three
    # README claims stale at once (12 adapters, 12 provider adapters, 136
    # checks) and nothing noticed. Same derivation shape as above -- recount
    # ground truth, then check every prose claim against it -- deliberately
    # sharing this section rather than adding a second implementation, since
    # two of "recount, then compare" would themselves eventually disagree.
    adapters = {p.name for p in (ROOT / "adapters").iterdir()
                if p.is_file() and not p.name.startswith("_")
                and not p.name.endswith(".pyc")}
    fails += check(f"the adapter set was actually derived ({len(adapters)} found)",
                   len(adapters) >= 8 and "git" in adapters,
                   f"{sorted(adapters)} -- a broken glob reads as a clean repository")

    ADAPTER_CLAIM = re.compile(r"(\d+)\s+(?:provider\s+)?adapters?\b", re.I)
    adapter_claims = 0
    for doc in ("README.md", "AGENTS.md", "CONTRIBUTING.md", "docs/installation.md"):
        f = ROOT / doc
        if not f.is_file():
            continue
        for m in ADAPTER_CLAIM.finditer(f.read_text(encoding="utf-8")):
            adapter_claims += 1
            fails += check(f"{doc}: '{m.group(0).strip()}' matches the {len(adapters)} on disk",
                           int(m.group(1)) == len(adapters),
                           f"disk has {len(adapters)}")
    fails += check("at least one document states an adapter count",
                   adapter_claims > 0,
                   "found 0 -- either every count was removed or the pattern went blind")

    # Counts, anchored on the word so that "ADR-011" is not read as an 11.
    WORDS = {"seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
             "twelve": 12, "thirteen": 13}
    COUNT = re.compile(r"(\d+|" + "|".join(WORDS) + r")\s+(?:conformance\s+)?suites?\b"
                       r"|(\d+)\s*/\s*(\d+)\s+pass"
                       r"|Expect\s+\**(\d+)\s*/\s*(\d+)"
                       r"|(\d+)\s+of\s+(\d+)\s+conformance\s+suites?", re.I)
    total_claims = 0
    for doc in ("README.md", "AGENTS.md", "CONTRIBUTING.md", "docs/installation.md",
                "docs/adrs/README.md", ".github/PULL_REQUEST_TEMPLATE.md"):
        f = ROOT / doc
        if not f.is_file():
            continue
        for m in COUNT.finditer(f.read_text(encoding="utf-8")):
            raw = [g for g in m.groups() if g]
            # "4 of 12 conformance suites fail" -- the TOTAL is the last number.
            val = raw[-1]
            n = WORDS.get(val.lower(), None) if not val.isdigit() else int(val)
            if n is None:
                continue
            total_claims += 1
            fails += check(f"{doc}: '{m.group(0).strip()}' matches the {len(truth)} on disk",
                           n == len(truth),
                           f"disk has {len(truth)}: {sorted(truth)}")
    fails += check("at least one document still states a suite count",
                   total_claims > 0,
                   "found 0 -- either every count was removed, or the pattern went "
                   "blind; a check that matches nothing is not a passing check")

    print(f"\n{'AGENT SURFACE: CONFORMANT' if not fails else f'AGENT SURFACE: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
