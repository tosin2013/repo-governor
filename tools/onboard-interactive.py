#!/usr/bin/env python3
"""Ask the questions detection cannot answer, and emit a manifest that validates.

`engine/onboard.py --write` produces a CANDIDATES document: what was found on
disk, with evidence, and `PROVIDER_UNCONFIRMED` wherever it would have to guess.
That file is evidence, not a manifest -- renaming it yields
`UNSUPPORTED_VERSION: manifest version None`, which was the documented
instruction until 2026-08-19 and had never been run end to end.

The gap is not ceremony. A manifest declares **which provider is the roadmap
authority and what signal means admission** (ADR-018), and neither is visible on
the filesystem. Whether admission means a milestone, a label or a project column
is a fact about how a team works. Detection must not guess it; a person can just
say it. So: ask.

Nothing here binds. Output is `.repo-governor.proposed.json` in manifest shape,
which a human reviews and renames. The engine never reads a proposal, which is
why silent binding stays unimplementable rather than merely forbidden.

Usage:  python3 tools/onboard-interactive.py <repo-path>
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
PROPOSAL = ".repo-governor.proposed.json"

# Roadmap providers with a shipped adapter. "Something else" is a first-class
# answer: a tracker we do not support is a contribution signal, not a dead end.
ROADMAP = [
    ("github-projects", "adapters/github-projects", "GitHub"),
    ("linear",          "adapters/linear",          "Linear (MCP transport)"),
    ("file-roadmap",    "adapters/file-roadmap",    "A file in the repository"),
]
GH_SIGNALS = [
    ("milestone",      "Milestone membership means admitted"),
    ("project_status", "A Project column/status means admitted"),
    ("label",          "A specific label means admitted"),
    ("none",           "Every open issue is admitted (rare -- says nothing is triage)"),
]


def ask(prompt, options, allow_other=True, unavailable=None):
    """options: list of (value, description). Returns a value, or None for other.

    `unavailable` maps value -> why. Those options KEEP THEIR POSITION and are
    refused if chosen. Removing them renumbers the list, and renumbering turned
    "picked an impossible option" into "picked a different option" on the very
    next run -- the same keystroke, a different meaning, and a manifest bound to
    the wrong signal without anyone noticing.
    """
    unavailable = unavailable or {}
    print(f"\n{prompt}")
    for i, (val, desc) in enumerate(options, 1):
        mark = f"   -- UNAVAILABLE: {unavailable[val]}" if val in unavailable else ""
        print(f"  {i}. {desc}{mark}")
    if allow_other:
        print(f"  {len(options) + 1}. Something else / not listed")
    while True:
        raw = input("> ").strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                val = options[n - 1][0]
                if val in unavailable:
                    print(f"  {val} cannot work here: {unavailable[val]}.")
                    print("  Nothing would ever be admitted under it. Pick another.")
                    continue
                return val
            if allow_other and n == len(options) + 1:
                return None
        print("Pick a number.")


def repo_id(repo: Path):
    """owner/repo from the git remote. Never defaulted -- ADR-028 exists because
    an adapter once fell back to the author's repository."""
    try:
        url = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                             capture_output=True, text=True).stdout.strip()
    except Exception:
        url = ""
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


REPO = "tosin2013/repo-governor"
TEMPLATE = "adapter-request.yml"


def contribute(repo, what):
    print(f"\n  No adapter ships for {what}.")
    print("  That is a gap worth recording rather than a reason to stop -- the")
    print("  provider abstraction exists so a tracker can be added without")
    print("  touching the engine (ADR-003).\n")
    # The form asks what an adapter must be able to answer -- above all what
    # ADMITTED means in that system, which is the one thing detection can never
    # see (ADR-018). Someone who can answer it has most of the design already.
    print("  File it (a form asks the questions an adapter has to answer):")
    print(f"    https://github.com/{REPO}/issues/new?template={TEMPLATE}")
    print("\n  Or from the terminal:")
    print(f"    gh issue create --repo {REPO} --template {TEMPLATE}")
    print("\n  Or write one: adapters/_protocol.py is the contract, and every")
    print("  shipped adapter is a single file. See CONTRIBUTING.md.")



def _survey(rid):
    """Show which admission signals actually EXIST, with the operator's consent.

    Detection must never probe a remote (ADR-010 rule 4): a probe that succeeds
    because a token happens to be present is capability implying permission.
    This is a different act. A person is asking to look at their own repository,
    the result only informs THEIR choice, and nothing is bound or inferred from
    it -- the answer to the next question is still theirs to give.

    It exists because four consecutive onboarding attempts declared
    project_status on a repository with zero Projects. Every id then read
    NOT_ON_BOARD while validation stayed green. Asking someone to declare a
    signal without showing them which signals exist is a question with a trap in
    it.
    """
    if input(f"\nLook up which admission signals exist in {rid}? "
             "Runs `gh`, reads counts only, changes nothing. [y/N] ").strip().lower() \
            not in ("y", "yes"):
        return None
    try:
        ms = json.loads(subprocess.run(
            ["gh", "api", f"repos/{rid}/milestones", "--jq",
             "[.[] | {t:.title, o:.open_issues, c:.closed_issues}]"],
            capture_output=True, text=True, timeout=25).stdout or "[]")
        pj = json.loads(subprocess.run(
            ["gh", "api", "graphql", "-f", "query=query{repository(owner:\"%s\","
             "name:\"%s\"){projectsV2(first:10){totalCount}}}" % tuple(rid.split("/", 1)),
             "--jq", ".data.repository.projectsV2.totalCount"],
            capture_output=True, text=True, timeout=25).stdout.strip() or "0")
        lb = json.loads(subprocess.run(
            ["gh", "api", f"repos/{rid}/labels", "--jq", "length"],
            capture_output=True, text=True, timeout=25).stdout.strip() or "0")
    except Exception as e:
        print(f"  lookup failed ({e}); choose from what you know.")
        return None

    print()
    if ms:
        names = ", ".join(m["t"] for m in ms[:4])
        live = sum(m["o"] for m in ms)
        print(f"  milestones : {len(ms)} ({names}) -- {live} open issues carry one")
    else:
        print("  milestones : none  <-- option 1 cannot work here")
    print(f"  Projects   : {pj}" + ("" if pj else "  <-- option 2 cannot work here"))
    print(f"  labels     : {lb}" + (""    if lb else "  <-- option 3 cannot work here"))
    print("\n  Existing is not the same as MEANING admitted. A repository can have"
          "\n  milestones that are release buckets rather than admission. Only you"
          "\n  know which. This just rules out the ones that cannot work.")
    return {"milestone": len(ms), "project_status": int(pj), "label": int(lb)}



LEVELS = [("L0", "GOVERNOR_GREENFIELD"), ("L1", "GOVERNOR_LITE"),
          ("L2", "GOVERNOR_STANDARD"), ("L3", "GOVERNOR_FULL"),
          ("L4", "GOVERNOR_HIGH_ASSURANCE")]


def _confirm_condition(level, profile, floors, ind):
    """Show the evidence, then let a person set the level. The script never decides.

    assess() is deliberately mechanical (ADR-002) and therefore crude: a floor
    fires on `"export "` appearing in any of 60 source files, which is true of
    essentially every TypeScript repository. Its own docstring says it reports a
    SUGGESTED level and a human decides -- but nothing in the flow ever asked.

    Printing the indicators is the point. A person can weigh them, and so can an
    agent running this on someone's behalf; neither can weigh a bare verdict.
    """
    print(f"\nCondition assessed: {level} / {profile}")
    if floors:
        print(f"  floor raised by : {', '.join(floors)}")
    interesting = [k for k, v in ind.items() if v not in (False, 0, None)]
    print(f"  indicators      : {', '.join(f'{k}={ind[k]}' for k in interesting) or 'none'}")
    if floors:
        print("\n  A floor means other people depend on this repository's shapes, so")
        print("  compatibility obligations exist. It may be RAISED but never lowered.")
    print("\n  Governance depth follows this (ADR-006): an L1 repository never loads")
    print("  L4 policy. Too high is friction; too low is a repository governed more")
    print("  loosely than its obligations warrant.")

    names = [l for l, _ in LEVELS]
    floor_at = names.index(level) if floors else 0
    allowed = names[floor_at:]
    if len(allowed) == 1:
        # The floor is already at the maximum. Offering a choice of one is not a
        # choice; say why there is nothing to decide and move on.
        print(f"\n  {level} is the highest level and the floor is already there,")
        print("  so there is nothing to choose. Recorded as assessed.")
        return level, profile
    print(f"\n  Accept {level}, or choose one of: {', '.join(allowed)}")
    raw = input(f"  [{level}] > ").strip().upper()
    if not raw:
        return level, profile
    if raw not in allowed:
        if raw in names:
            print(f"  {raw} is below the floor and cannot be set. Keeping {level}.")
        else:
            print(f"  Not a level. Keeping {level}.")
        return level, profile
    return raw, dict(LEVELS)[raw]


def _assessed(repo: Path):
    """(level, profile, floors, indicators) from engine/onboard.py. Never defaulted."""
    r = subprocess.run(
        [sys.executable, str(SKILL / "engine" / "onboard.py"), str(repo), "--json"],
        capture_output=True, text=True)
    try:
        c = json.loads(r.stdout)["condition"]
        return (c["suggested"], c["profile"], c.get("floor") or [],
                c.get("indicators") or {})
    except Exception:
        # No silent fallback to a level. A condition nobody assessed is not a
        # condition, and guessing one is the defect this function replaced.
        print("Could not read the assessed condition from engine/onboard.py.",
              file=sys.stderr)
        raise SystemExit(1)


def main(argv):
    if not argv:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    repo = Path(argv[0]).resolve()
    if not (repo / ".git").exists():
        print(f"not a git repository: {repo}", file=sys.stderr)
        return 1
    if (repo / ".repo-governor.json").exists():
        print(f"{repo} is already onboarded. Refusing to overwrite a binding manifest.",
              file=sys.stderr)
        return 1

    print(f"Onboarding proposal for {repo}")
    print("This writes a PROPOSAL. Nothing governs until you review and rename it.")

    # Detection first: it answers what it can, and its evidence is worth seeing.
    print("\n--- detected ---")
    subprocess.run([sys.executable, str(SKILL / "engine" / "onboard.py"), str(repo)])

    rid = repo_id(repo)
    if not rid:
        print("\nCould not read owner/repo from the git remote.")
        rid = input("Repository id (owner/repo): ").strip()
        if not rid:
            print("A repository id is required; it is never defaulted (ADR-028).",
                  file=sys.stderr)
            return 1
    else:
        print(f"\nRepository id, from the git remote: {rid}")

    choice = ask("Which system is the ROADMAP AUTHORITY -- the one that says what "
                 "work is admitted?", [(v, d) for v, _, d in ROADMAP])
    if choice is None:
        contribute(repo, "roadmap_authority")
        return 1
    adapter = next(a for v, a, _ in ROADMAP if v == choice)

    admission = None
    if choice == "github-projects":
        counts = _survey(rid)
        # Do NOT offer a signal that provably cannot work. The survey printed
        # "Projects: 0 <-- option 2 cannot work here" directly above this
        # question and the option was chosen anyway, five times running. A
        # warning the reader must notice is not a control -- which is this
        # project's own thesis, applied to its own tooling.
        opts, unavail = GH_SIGNALS, {}
        if counts:
            opts = [(v, f"{d}   [{counts[v]} exist]" if counts.get(v) else d)
                    for v, d in GH_SIGNALS]
            unavail = {v: "none exist in this repository"
                       for v, _ in GH_SIGNALS if v != "none" and not counts.get(v)}
        admission = ask("What does ADMITTED mean in that repository? Detection cannot "
                        "see this, and guessing it is how a second roadmap of record "
                        "gets created (ADR-018).", opts, allow_other=False,
                        unavailable=unavail)
        # Asked HERE, while the choice is on screen. It used to be asked after
        # the condition question, three screens later, where it read as a
        # continuation of something else.
        label = ""
        if admission == "label":
            label = input("  Which label means admitted? ").strip()

    # Take the ASSESSED condition, never a default. This wrote "L1" /
    # GOVERNOR_LITE unconditionally, with a comment telling the reader to fix it
    # by hand -- on a repository detection had assessed L4 because three floor
    # indicators fired. The engine's own rule is that a floor "may not be
    # overridden downward", so the tool was committing the violation it printed
    # a warning about two screens earlier. The profile decides governance depth
    # (ADR-006); writing L1 over an L4 under-governs a repository that has
    # compatibility obligations.
    level, profile, floors, ind = _assessed(repo)
    level, profile = _confirm_condition(level, profile, floors, ind)
    prov = {
        "repository": {"type": "git", "adapter": "adapters/git", "contract_version": 1},
        "roadmap_authority": {"type": choice, "adapter": adapter, "contract_version": 1},
    }
    if admission:
        prov["roadmap_authority"]["admission"] = {"signal": admission}
    if choice == "github-projects":
        prov["roadmap_authority"]["transport"] = {"kind": "cli", "command": "gh"}
        # The adapter reads its configuration from this env block, not from the
        # fields above. Omitting it produced a manifest that validated as
        # READY_FOR_GOVERNANCE and then answered PROVIDER_UNAVAILABLE for every
        # id: "no repository declared ... an adapter that cannot tell which
        # repository it is reading must not answer" (ADR-028). That refusal is
        # correct; generating a manifest without the field was the defect.
        env = {"REPO_GOVERNOR_GH_REPO": rid}
        if admission:
            env["REPO_GOVERNOR_GH_ADMISSION"] = admission
        if admission == "label":
            if not label:
                print("A label signal needs the label named; it is never assumed "
                      "(ADR-018).", file=sys.stderr)
                return 1
            env["REPO_GOVERNOR_GH_ADMISSION_LABEL"] = label
        prov["roadmap_authority"]["env"] = env

    # Deny by default (ADR-005). Every bound role gets read, nothing gets write.
    # The engine rules; it does not act. A proposal that granted write would be
    # asking a reviewer to notice an escalation buried in generated JSON.
    perms = {"$comment": "Deny by default (ADR-005). Read-only: Repo Governor rules, "
                         "it does not act. Grant write only with a reason written beside it."}
    perms.update({role: {"read": True, "write": False} for role in prov})

    out = {
        "$comment": ("PROPOSAL in manifest shape. Review every line, then rename to "
                     ".repo-governor.json and commit. The engine never reads this file "
                     "(ADR-010 rule 1). Roles beyond these two are optional -- add them "
                     "as you bind them; a role absent here has no governance function "
                     "however reachable the system is (INV-013)."),
        "repo_governor": {"version": 1, "engine_min_version": "0.1.0"},
        "repository": {"id": rid},
        "condition": {
            "assessed": level, "profile": profile,
            "$comment": ("Assessed by engine/onboard.py, not defaulted."
                         + (f" Floor indicators present ({', '.join(floors)}); per the"
                            " engine's rule this may not be overridden downward."
                            if floors else
                            " No floor indicator; a human may raise it if the"
                            " repository's obligations exceed what is observable.")),
        },
        "permissions": perms,
        "providers": prov,
    }
    p = repo / PROPOSAL
    p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {p}")
    print("\nVerify it before binding:")
    print(f"  cd {repo} && mv {PROPOSAL} .repo-governor.json")
    print(f"  python3 {SKILL / 'engine' / 'manifest.py'} --validate")
    print("\nIf validation fails, rename it back. Nothing governs until it passes.")
    # --validate does NOT catch a wrong admission signal, or a binding that
    # cannot answer at all (issue 51). Only asking a real question does. Three
    # separate onboarding attempts declared project_status on a repository with
    # no Project; every id then read NOT_ON_BOARD, and validation stayed green
    # throughout.
    print("\nTHEN ASK IT A REAL QUESTION -- validation does not catch a wrong signal:")
    print(f"  python3 {SKILL / 'engine' / 'completion.py'} <an open issue number>")
    print("\n  A real verdict (EXECUTE, CONTINUE, NO_EXECUTION_AUTHORITY,")
    print("  STOP_COMPLETE) means the binding works.")
    print("  UNKNOWN with the SAME reason for every id you try means the")
    print("  admission signal is probably wrong -- NOT_ON_BOARD when there is no")
    print("  Project, NOT_ADMITTED for everything when nothing carries the")
    print("  milestone or label you named. Re-run this tool and pick again.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
