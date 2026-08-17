#!/usr/bin/env python3
"""Closed vocabularies and the blocking classifier — gate 7 (ADR-007).

Three closed sets, and the rule that decides whether an unknown stops work.

Closed means closed: an unrecognised value is a defect, not an extension
point. ADR-007 rule 1 makes the disposition alphabet engine-owned precisely
so cross-provider portability (§53) is measurable — two providers can only
be compared if the output alphabet is fixed. The same argument applies to
unknown reasons, or a provider could invent a reason the engine cannot
classify as blocking or not.

The reason set below was harvested from what the adapters and engine
actually emit, then closed around it. Adding a reason requires touching
this file, which is the point.
"""

from __future__ import annotations

# --- §41 governance dispositions ------------------------------------------
EXECUTION = ("EXECUTE", "CONTINUE", "STOP_COMPLETE")
REVIEW = ("CAPTURE_ONLY", "ROADMAP_REVIEW", "ARCHITECTURE_REVIEW",
          "MAINTENANCE_REVIEW", "RETIREMENT_REVIEW")
REFUSAL = ("NO_EXECUTION_AUTHORITY", "AUTHORITY_WITHDRAWN", "CONFLICT", "UNKNOWN")
DISPOSITIONS = EXECUTION + REVIEW + REFUSAL

# --- §42 onboarding dispositions — a SEPARATE alphabet --------------------
# Different state machine, different consumer (a human running onboarding,
# not an agent mid-task). These never appear in a governance decision.
ONBOARDING = ("PROVIDER_DETECTED", "PROVIDER_UNCONFIRMED", "PROVIDER_CONFIGURED",
              "PROVIDER_UNAVAILABLE", "PROVIDER_CONFLICT", "AUTHORITY_SOURCE_MISSING",
              "READY_FOR_GOVERNANCE", "PROPOSAL_READY")

# --- typed adapter errors (ADR-003) ---------------------------------------
ERRORS = ("PROVIDER_UNAVAILABLE", "NOT_FOUND", "UNSUPPORTED_FUNCTION",
          "MALFORMED_SOURCE", "BAD_REQUEST")

# --- unknown reasons, with the dimension each belongs to and whether it blocks
#
# BLOCKING means: this unknown sits on the critical path to EXECUTE, so the
# engine must not proceed. NON-BLOCKING means it is real uncertainty that
# does not gate the current decision. That split is what keeps INV-012 from
# colliding with §54's "turns all discoveries into human review" failure
# condition (ADR-007 rule 4).
#
# The distinction is NOT "how serious is this" — it is "does the current
# decision depend on it".
REASONS = {
    # authority — always blocking: without admission there is no authorization
    "AUTHORITY_UNSTATED":            ("authority", True,
                                      "The work item declares no authority value."),
    "NOT_ADMITTED":                  ("authority", True,
                                      "Filed but never admitted to the roadmap (e.g. Linear triage)."),
    "NOT_ON_BOARD":                  ("authority", True,
                                      "Not an item on any Project, so admission cannot be read."),

    # acceptance — non-blocking: absence means no completion bar, not danger
    "NO_CRITERIA_DECLARED":          ("acceptance", False,
                                      "No acceptance criteria declared; STOP_COMPLETE unavailable."),
    "ACCEPTANCE_UNSTATED":           ("acceptance", False,
                                      "Provider cannot supply machine-checkable acceptance conditions."),
    "NON_GOALS_UNSTATED":            ("scope", False,
                                      "No non-goals declared; the scope envelope will be thin."),
    "SCOPE_NOT_STRUCTURED":          ("scope", False,
                                      "Scope exists only as free prose, which may not become typed facts."),

    # architecture — non-blocking: UNKNOWN architecture constrains nothing
    "NO_ARCHITECTURE_EVIDENCE":      ("architecture", False,
                                      "No architecture decisions found."),
    "NO_ACCEPTED_DECISIONS":         ("architecture", False,
                                      "Decisions exist but none is Accepted; state is INFERRED, not DEFINED."),
    "STATUS_UNSTATED":               ("architecture", False,
                                      "Decision files carry no Status line."),

    # execution — non-blocking: execution state never authorizes (INV-002)
    "NO_HANDOFF_RECORDED":           ("execution", False,
                                      "No handoff state; agent continuity is not recoverable."),
    "HISTORY_NOT_RETAINED":          ("execution", False,
                                      "Provider stores current state only, not an append-only history."),

    # evidence — blocking: a check that cannot be evaluated cannot be claimed
    "CHECK_TIMED_OUT":               ("evidence", True,
                                      "An acceptance check did not finish."),
    "NOT_DERIVABLE_FROM_SOURCE":     ("evidence", False,
                                      "Requires analysis the bound provider cannot perform."),

    # retirement — blocking: unresolved obligations must never permit removal
    "NOT_VISIBLE_TO_STATIC_ANALYSIS": ("retirement", True,
                                       "Dynamic loading, runtime usage or public contracts are invisible to grep."),

    # change signals — non-blocking: a signal is not work (INV-006)
    "IMPACT_NOT_ASSESSED":           ("change_signals", False,
                                      "Whether this change matters here is a judgement, not a supplied fact."),

    # transport / provider health — blocking
    "PROVIDER_UNREACHABLE":          ("provider", True,
                                      "The bound provider could not be reached."),
    "TRANSPORT_UNCONFIGURED":        ("provider", True,
                                      "No transport is configured, so the provider advertises nothing."),
}

DIMENSIONS = ("authority", "acceptance", "scope", "architecture", "execution",
              "evidence", "retirement", "change_signals", "provider")

# Profiles may only make a non-blocking reason blocking, never the reverse.
# Loosening a blocking reason would let a profile permit EXECUTE on evidence
# the engine could not resolve.
PROFILE_ESCALATIONS = {
    "GOVERNOR_HIGH_ASSURANCE": ("NON_GOALS_UNSTATED", "ACCEPTANCE_UNSTATED",
                                "NO_CRITERIA_DECLARED", "NO_ACCEPTED_DECISIONS"),
    "GOVERNOR_FULL": ("NO_CRITERIA_DECLARED",),
}


class VocabularyError(ValueError):
    pass


def classify(reason, profile="GOVERNOR_LITE"):
    """Return (dimension, blocking, description). Raises on an unknown reason."""
    if reason not in REASONS:
        raise VocabularyError(
            f"{reason!r} is not in the closed reason vocabulary. "
            "Adding one requires editing engine/vocabulary.py — a provider may not invent reasons.")
    dim, blocking, desc = REASONS[reason]
    if not blocking and reason in PROFILE_ESCALATIONS.get(profile, ()):
        return dim, True, desc + f" (escalated to blocking by {profile})"
    return dim, blocking, desc


def is_disposition(value):
    return value in DISPOSITIONS


def check_alphabets_disjoint():
    """Governance and onboarding alphabets must not overlap (ADR-007 rule 6).

    PROVIDER_UNAVAILABLE is deliberately shared with the ERRORS set: it is an
    adapter-level error type AND an onboarding disposition. It is not a
    governance disposition, which is the separation that matters.
    """
    overlap = set(DISPOSITIONS) & set(ONBOARDING)
    if overlap:
        raise VocabularyError(f"governance and onboarding alphabets overlap: {sorted(overlap)}")
    return True


if __name__ == "__main__":
    check_alphabets_disjoint()
    print(f"governance dispositions : {len(DISPOSITIONS)}")
    print(f"onboarding dispositions : {len(ONBOARDING)}")
    print(f"adapter error types     : {len(ERRORS)}")
    print(f"unknown reasons         : {len(REASONS)}")
    print(f"dimensions              : {len(DIMENSIONS)}")
    blocking = [r for r, (_, b, _) in REASONS.items() if b]
    print(f"  blocking              : {len(blocking)}")
    print(f"  non-blocking          : {len(REASONS) - len(blocking)}")
