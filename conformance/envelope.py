#!/usr/bin/env python3
"""ScopeEnvelope compilation and the completion firewall (§31, §32, §40, ADR-024).

§40 says its worked example "should be implemented verbatim as an acceptance
test". This is that test, plus the classification paths around it.

The property that matters is not that discoveries are captured -- it is that
**nothing converts them to execution once the authorization is satisfied**,
including a discovery that is correct, small, obviously beneficial, and
genuinely necessary. A firewall with one exception is not a firewall.

Usage:  python3 conformance/envelope.py
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
import envelope as E  # noqa: E402
import vocabulary as V  # noqa: E402

import _count as _CNT  # noqa: E402 -- alias avoids `C`, already bound to
# `completion` in two suites, where the collision silently rebound it (issue 67).
_CNT.watch("envelope")

# A rich envelope. Real trackers rarely supply this much -- which is issue #2,
# measured by `thinness` rather than assumed away.
RICH = {
    "authority_id": "SIM-1",
    "authority": "AUTHORIZED",
    "required_outcome": "Persistent state recovery",
    "in_scope": ["state/recovery.py", "state/snapshot.py"],
    "non_goals": ["Admin UI", "multi-team support"],
    "architecture_constraints": ["ADR-002"],
    "acceptance_conditions": [{"check": "tests_pass", "target": "state/"}],
}

# §40 verbatim: authorized work completed, three things discovered along the way.
SECTION_40 = [
    ("Admin UI", "POSSIBLE_FEATURE", "CAPTURE_ONLY"),
    ("Multi-team support", "POSSIBLE_FEATURE", "CAPTURE_ONLY"),
    # §40 permits CAPTURE_ONLY *or* MAINTENANCE_REVIEW for the refactor.
    ("Refactor", "TECHNICAL_DEBT", ("CAPTURE_ONLY", "MAINTENANCE_REVIEW")),
]


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"    {detail}" if detail and not ok else ""))
    return 0 if ok else 1


def main():
    fails = 0
    print("§40 worked example, verbatim\n")

    for target, dtype, expect in SECTION_40:
        got = E.classify(RICH, dtype, target, completed=True)["disposition"]
        want = expect if isinstance(expect, tuple) else (expect,)
        fails += check(f"{target:<20} -> {got}", got in want, f"expected one of {want}")

    print("\nThe firewall admits no exception\n")

    # The whole point. Each of these would be a reasonable-sounding door.
    for label, kw in (
        ("a discovery claimed necessary", dict(claimed_necessary=True)),
        ("a discovery inside declared in_scope",
         dict(target="state/recovery.py", claimed_necessary=True)),
        ("a bug, which always feels urgent", dict(dtype="BUG")),
    ):
        args = {"dtype": "TECHNICAL_DEBT", "target": "something", **kw}
        got = E.classify(RICH, completed=True, **args)["disposition"]
        fails += check(f"{label} still captures", got == "CAPTURE_ONLY", f"got {got}")

    print("\nBefore completion: necessity is substantiated, never asserted\n")

    r = E.classify(RICH, "TECHNICAL_DEBT", "state/recovery.py cleanup", claimed_necessary=True)
    fails += check("necessary + inside in_scope may execute", r["disposition"] == "EXECUTE",
                   f"got {r['disposition']}")

    r = E.classify(RICH, "TECHNICAL_DEBT", "unrelated/module.py", claimed_necessary=True)
    fails += check("necessary claim OUTSIDE in_scope fails closed",
                   r["disposition"] == "CAPTURE_ONLY", f"got {r['disposition']}")

    r = E.classify(RICH, "POSSIBLE_FEATURE", "Admin UI redesign", claimed_necessary=True)
    fails += check("a declared non-goal outranks any necessity claim",
                   r["disposition"] == "CAPTURE_ONLY", f"got {r['disposition']}")

    thin = {**RICH, "in_scope": [], "non_goals": []}
    r = E.classify(thin, "TECHNICAL_DEBT", "anything", claimed_necessary=True)
    fails += check("with no declared in_scope, no necessity claim can be substantiated",
                   r["disposition"] == "CAPTURE_ONLY", f"got {r['disposition']}")

    print("\nVocabulary and routing\n")

    for dtype, want in (("ARCHITECTURE_IMPLICATION", "ARCHITECTURE_REVIEW"),
                        ("MAINTENANCE_SIGNAL", "MAINTENANCE_REVIEW"),
                        ("RETIREMENT_SIGNAL", "RETIREMENT_REVIEW"),
                        ("RESEARCH_QUESTION", "CAPTURE_ONLY")):
        got = E.classify(RICH, dtype, "x")["disposition"]
        fails += check(f"{dtype} routes to {want}", got == want, f"got {got}")

    bad = E.classify(RICH, "NOT_A_TYPE", "x")
    fails += check("a discovery type outside §32 is refused, not guessed",
                   bad.get("error") == "BAD_REQUEST")

    emitted = {E.classify(RICH, d, "x")["disposition"] for d in E.DISCOVERY_TYPES}
    emitted |= {"EXECUTE"}
    undeclared = sorted(d for d in emitted if d not in V.EXECUTION + V.REVIEW)
    fails += check("every disposition it can emit is in the closed vocabulary",
                   not undeclared, str(undeclared))

    print("\nThinness is measured, not assumed away (issue #2)\n")

    full = E._thinness(RICH)
    fails += check("a fully-declared envelope reads FULL", full["verdict"] == "FULL",
                   str(full))
    bare = E._thinness({k: ([] if isinstance(v, list) else None) for k, v in RICH.items()})
    fails += check("an envelope no provider could fill reads THIN", bare["verdict"] == "THIN",
                   str(bare))

    print(f"\n{'ENVELOPE: CONFORMANT' if not fails else f'ENVELOPE: NON-CONFORMANT ({fails})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
