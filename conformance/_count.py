"""One number, reported the same way by every suite.

Issue 67. Eight assertions in `conformance/onboarding.py` were unreachable --
a guard tested a path the code above it had renamed away -- and the suite
reported PASS throughout. Nothing counted how many assertions a suite actually
EXECUTED, so a suite running fewer than it contains read identically to one
running all of them.

The first attempt at fixing this was to grep `[PASS]`/`[FAIL]` lines out of
each suite's output. That was the wrong instinct and it failed immediately: a
survey built that way reported four suites emitting counts, when the fourth was
`conformance/skill.py` printing a check whose LABEL quoted the string
`'14/14 pass'` from the pull-request template. The measurement was contaminated
by output that merely looked like what it counted, inside one command.

So: a declared contract, not inference from prose. Every suite calls `tally()`
once per assertion and prints `line()` at the end. `conformance/coverage.py`
reads that line and FAILS on any suite that does not emit one -- a suite
silently dropping out of coverage is the failure mode this exists to close.

WHAT THIS DOES NOT DO. It makes a DROP visible: if a suite executed 90
assertions yesterday and 82 today, something stopped running. It does not
prove every assertion in a file is reachable, and it would NOT have found the
original defect, whose count was always 79 and never fell. Finding
pre-existing dead code needs per-site reachability, which is unsolved here
because the suites share no assertion helper. `sites()` records which lines
fired so that work has somewhere to start; nothing consumes it yet, and
pretending otherwise would be the vacuity this file exists to prevent.
"""

from __future__ import annotations

import sys
from pathlib import Path

_executed = 0
_failed = 0
_lines: set[tuple[str, int]] = set()

MARKER = "CONFORMANCE-COUNT"


def tally(ok):
    """Record one executed assertion. Returns `ok` so it composes inline."""
    global _executed, _failed
    _executed += 1
    if not ok:
        _failed += 1
    # Attribute to the OUTERMOST frame inside conformance/, so the site is the
    # assertion itself rather than whichever helper happened to call this.
    # Depth varies between the three reporting styles in use, so counting
    # frames would be wrong for at least one of them.
    # The site is the frame that CALLED the reporting helper. Taking the
    # outermost conformance frame instead finds the module-level
    # `sys.exit(main())` line every time, which reported one site per suite --
    # a counter that counted itself.
    HELPERS = {"tally", "check", "add"}
    try:
        f = sys._getframe(1)
        while f:
            p = Path(f.f_code.co_filename)
            if (p.parent.name == "conformance" and not p.name.startswith("_")
                    and f.f_code.co_name not in HELPERS):
                _lines.add((p.name, f.f_lineno))
                break
            f = f.f_back
    except Exception:  # noqa: BLE001 -- counting must never break a suite
        pass
    return ok


def counts():
    return {"executed": _executed, "failed": _failed, "sites": len(_lines)}


def sites():
    """(file, line) of every assertion that fired. For future reachability work."""
    return sorted(_lines)


def line(suite):
    """The declared, fixed-format line every suite ends with."""
    return f"{MARKER} suite={suite} executed={_executed} failed={_failed} sites={len(_lines)}"
