"""Shared adapter-protocol helpers for the Python adapters (ADR-003).

A Go or shell adapter would not import this — the protocol is the JSON on
stdout, not this module. It exists only to keep the Python adapters short.

Wire protocol
-------------
    $ADAPTER describe                       -> capability manifest
    $ADAPTER query <role> <function> [k=v]  -> typed response (read)
    $ADAPTER write <role> <function> [k=v]  -> typed response (mutate)

`query` and `write` are separate verbs so the read/write split ADR-005 cares
about is visible at the protocol level rather than buried in a function name.
An adapter that declares no writers rejects `write` outright. The ENGINE still
checks the manifest before calling either -- an adapter offering a writer is
capability, not permission (INV-014).

Every response is a single JSON object on stdout. Exit code 0 means "the
adapter ran"; it does NOT mean the query succeeded — check `ok`. This split
exists because ADR-008 requires an unreachable backend to produce a typed
failure rather than a plausible-looking empty result.

Determinism note (ADR-002): adapters do not stamp timestamps into provenance.
The engine stamps the decision record. Timestamps here would break the
byte-identical replay that ADR-009 depends on.
"""

from __future__ import annotations

import json
import sys

CONTRACT_VERSION = 1

# Typed error vocabulary. Closed set — see ADR-007's reasoning for dispositions.
ERRORS = (
    "PROVIDER_UNAVAILABLE",     # backend unreachable / unreadable
    "NOT_FOUND",                # the object genuinely does not exist
    "UNSUPPORTED_FUNCTION",     # not part of this adapter's advertised capability
    "MALFORMED_SOURCE",         # backend reachable but its data is unparseable
    "BAD_REQUEST",              # caller error: missing/invalid argument
)


def emit(obj) -> None:
    json.dump(obj, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def ok(role, function, value, provenance, unknown=None):
    """A successful typed response.

    `provenance` is mandatory and must be non-empty (ADR-012): a fact with no
    citation is treated as unknown, not as true.
    """
    if not provenance:
        return fail(role, function, "MALFORMED_SOURCE", "fact produced without provenance")
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "role": role,
        "function": function,
        "value": value,
        "provenance": provenance,
        "unknown": unknown,
    }


def unknown(role, function, reason, detail, resolution, blocking=True):
    """Evidence could not be resolved. Distinct from absence (ADR-003 rule 5)."""
    return {
        "ok": True,
        "contract_version": CONTRACT_VERSION,
        "role": role,
        "function": function,
        "value": None,
        "provenance": [],
        "unknown": {
            "reason": reason,
            "detail": detail,
            "resolution": resolution,
            "blocking": blocking,
        },
    }


def fail(role, function, etype, message):
    assert etype in ERRORS, f"undeclared error type {etype}"
    return {
        "ok": False,
        "contract_version": CONTRACT_VERSION,
        "role": role,
        "function": function,
        "error": {"type": etype, "message": message},
    }


def cite(source, ref, field=None):
    """One provenance entry. No timestamp — see module docstring."""
    c = {"source": source, "ref": ref}
    if field:
        c["field"] = field
    return c


def parse_args(argv):
    """`query <role> <function> [k=v ...]` -> (role, function, {k: v})."""
    if len(argv) < 2:
        return None, None, {}
    role, function = argv[0], argv[1]
    kw = {}
    for tok in argv[2:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            kw[k] = v
    return role, function, kw


def main(role, capabilities, functions, describe_extra=None, properties=None, probe=None,
         writers=None):
    """Standard entry point. `functions` maps name -> callable(kw) -> response.

    `capabilities` are claims that MUST be exercisable by a conformance probe
    (ADR-008 C2). `properties` are declarative traits that cannot be probed —
    persistence, provenance quality. Keeping them apart is what makes an
    honest-advertisement check meaningful rather than vacuous.

    `probe` is a zero-arg callable returning whether the transport is usable.
    When it returns false, `describe` advertises NO capabilities. This follows
    LSP's rule that a missing property means absence of the capability: an
    adapter that cannot reach its backend can serve nothing, so it must claim
    nothing. Without this an unconfigured adapter advertises capabilities it
    will fail every query for (issue #17).
    """
    argv = sys.argv[1:]
    if not argv:
        emit(fail(role, "-", "BAD_REQUEST", "usage: describe | query <role> <function> [k=v]"))
        return 0
    if argv[0] == "describe":
        reachable = True if probe is None else bool(probe())
        d = {
            "contract_version": CONTRACT_VERSION,
            "role": role,
            # LSP rule: missing means absent. Unreachable transport => no claims.
            "capabilities": capabilities if reachable else {},
            "properties": properties or {},
            "functions": sorted(functions),
            "writers": sorted(writers or {}),
            "transport": {"reachable": reachable},
        }
        if describe_extra:
            d.update(describe_extra)
        emit(d)
        return 0
    if argv[0] not in ("query", "write"):
        emit(fail(role, "-", "BAD_REQUEST", f"unknown verb {argv[0]!r}"))
        return 0
    verb = argv[0]
    req_role, function, kw = parse_args(argv[1:])
    if req_role != role:
        emit(fail(role, function or "-", "BAD_REQUEST", f"this adapter serves role {role!r}, not {req_role!r}"))
        return 0
    table = (writers or {}) if verb == "write" else functions
    fn = table.get(function)
    if fn is None:
        if verb == "write" and not writers:
            emit(fail(role, function or "-", "UNSUPPORTED_FUNCTION",
                      "this adapter declares no writers; it is read-only"))
        else:
            emit(fail(role, function or "-", "UNSUPPORTED_FUNCTION", f"{function!r} not advertised"))
        return 0
    emit(fn(kw))
    return 0
