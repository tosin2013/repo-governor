#!/usr/bin/env python3
"""Compile a ScopeEnvelope and rule on discoveries against it (§31, §32, ADR-024).

    roadmap provider    scope, non-goals, acceptance conditions
  + architecture        binding constraints
  = ScopeEnvelope       what may be done while satisfying THIS authorization

The envelope is **compiled from provider state at evaluation time, never
hand-authored**. A hand-maintained envelope would become a second roadmap
artifact and drift, which is ADR-022's failure in a smaller costume.

What this module must not do
----------------------------
ADR-002 keeps judgment out of the engine, and `necessary_incidental_work` is
where that rule is hardest to hold. This module never decides whether an action
is *really* necessary. The agent supplies a typed claim; the engine rules on it
against declared scope, and **refuses a claim it cannot substantiate**. An
unsupported necessity claim fails closed rather than being taken at its word --
otherwise `necessary_incidental_work` becomes a password an agent types to
unlock anything.

Usage:  python3 engine/envelope.py <authority-id>
        python3 engine/envelope.py <authority-id> --discovery <type>[:target]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bindings as B  # noqa: E402
import manifest as MF  # noqa: E402
import vocabulary as V  # noqa: E402
from version import ENGINE_VERSION  # noqa: E402

# §32's closed set. A discovery outside it is BAD_REQUEST, never guessed into
# the nearest neighbour -- the vocabulary is closed for the same reason the
# disposition set is (ADR-007).
DISCOVERY_TYPES = ("POSSIBLE_FEATURE", "BUG", "TECHNICAL_DEBT", "ARCHITECTURE_IMPLICATION",
                   "MAINTENANCE_SIGNAL", "RETIREMENT_SIGNAL", "RESEARCH_QUESTION",
                   "DUPLICATE", "UNKNOWN")

# Which review lane a discovery type routes to when it is NOT capture-only.
# Everything else defaults to CAPTURE_ONLY, which is a complete outcome (§32).
REVIEW_LANE = {
    "ARCHITECTURE_IMPLICATION": "ARCHITECTURE_REVIEW",
    "MAINTENANCE_SIGNAL": "MAINTENANCE_REVIEW",
    "RETIREMENT_SIGNAL": "RETIREMENT_REVIEW",
}


def _ask(role, fn, kw, manifest):
    """One provider call, reduced to (value, unknown_reason)."""
    r = B.call(role, fn, kw, manifest=manifest)
    if not r.get("ok"):
        return None, r.get("error", {}).get("type")
    if r.get("unknown"):
        return None, r["unknown"]["reason"]
    return r.get("value"), None


def compile_envelope(authority_id, manifest=None):
    """Build the §31 envelope from provider state. Never invents a field."""
    m = manifest
    if m is None:
        m, errs = MF.load()
        if errs:
            return {"authority_id": authority_id, "error": "MANIFEST_UNREADABLE", "detail": errs[0]}

    auth, auth_why = _ask("roadmap_authority", "get_authority", {"id": authority_id}, m)
    scope, scope_why = _ask("roadmap_authority", "get_scope", {"id": authority_id}, m)
    goals, goals_why = _ask("roadmap_authority", "get_non_goals", {"id": authority_id}, m)
    acc, acc_why = _ask("acceptance_criteria", "get_criteria", {"id": authority_id}, m)
    arch, arch_why = _ask("architecture", "get_constraints", {"id": authority_id}, m)

    env = {
        "authority_id": authority_id,
        "authority": (auth or {}).get("authority"),
        "required_outcome": (scope or {}).get("required_outcome"),
        "in_scope": (scope or {}).get("in_scope") or [],
        # Not compiled: necessity is decided per action, against this envelope,
        # at the moment an action is proposed. Precomputing it would mean
        # deciding in advance what has not been described yet.
        "necessary_incidental_work": "decided per action; see classify()",
        "non_goals": (goals or {}).get("non_goals") or [],
        "architecture_constraints": [c["id"] for c in (arch or {}).get("constraints") or []],
        "discovery_policy": "CAPTURE_ONLY unless proven necessary to the authorized outcome (INV-001)",
        "acceptance_conditions": (acc or {}).get("criteria") or [],
        "stop_condition": "acceptance conditions satisfied => STOP_COMPLETE (§40)",
        "unresolved": {k: v for k, v in (
            ("authority", auth_why), ("scope", scope_why), ("non_goals", goals_why),
            ("acceptance_conditions", acc_why), ("architecture", arch_why)) if v},
    }
    env["thinness"] = _thinness(env)
    return env


def _thinness(env):
    """How much of the envelope the providers could actually fill.

    This is the measurement issue #2 asks for, and it is reported rather than
    judged: a thin envelope is not an error, it is a fact about the tracker. The
    engine states it so a human can decide whether governing on it is worthwhile
    (§55) instead of discovering the weakness after trusting a verdict.
    """
    dims = {
        "required_outcome": bool(env["required_outcome"]),
        "in_scope": bool(env["in_scope"]),
        "non_goals": bool(env["non_goals"]),
        "architecture_constraints": bool(env["architecture_constraints"]),
        "acceptance_conditions": bool(env["acceptance_conditions"]),
    }
    filled = sum(dims.values())
    return {"filled": filled, "of": len(dims), "dimensions": dims,
            "verdict": "THIN" if filled <= 2 else "PARTIAL" if filled < len(dims) else "FULL"}


def _matches(text, patterns):
    """Substring match, stated plainly as the weak test it is.

    A real matcher would need to decide whether 'add caching' falls under a
    non-goal of 'performance work' -- a reading, which ADR-002 keeps out of the
    engine. So this matches literally and the envelope's non-goals are only as
    good as the words the tracker holds. That limitation is the honest one; a
    cleverer matcher here would be judgment wearing a regex.
    """
    low = (text or "").lower()
    return [p for p in patterns if p and p.lower() in low]


def discovery_id(authority_id, dtype, target):
    """Stable identity for one discovery. Same authority, type and target => same id.

    The target is hashed, never stored: §51 keeps repository content out of a
    public evidence chain, and `record` redacts the target for that reason. A
    hash is enough to recognise a rediscovery without recording what was
    discovered.
    """
    # Imported here, not at module scope. conformance/imports.py uses this
    # file's function-body `import hashlib` as its positive control that the
    # dependency audit walks the AST rather than grepping for `^import`;
    # hoisting it would make that control pass for the wrong reason.
    import hashlib  # noqa: PLC0415
    key = json.dumps([authority_id or "-", dtype, target or ""], sort_keys=True)
    return "disc-" + hashlib.sha256(key.encode()).hexdigest()[:24]


def prior_decision(authority_id, dtype, target, manifest=None):
    """Has this exact discovery been decided before? (record, error) or (None, None).

    §39: rediscovered work stays CAPTURE_ONLY unless its reversal condition is
    met. The engine wrote decisions and never read one back, so every
    rediscovery looked new -- an agent told no in one session could be told yes
    in the next by the same engine (issue 95).

    Absence is not an error. A repository with no decision_history bound, or
    with nothing recorded, behaves exactly as it did before.
    """
    m = manifest
    if m is None:
        m, errs = MF.load()
        if errs:
            return None, None
    if "decision_history" not in (m.get("providers") or {}):
        return None, None
    want = discovery_id(authority_id, dtype, target)
    r = B.call("decision_history", "get_decisions", {"id": str(authority_id or "-")},
               manifest=m)
    if not r.get("ok") or r.get("unknown"):
        # Unreadable or empty. Not an error, and deliberately not blocking: a
        # store that cannot be read must not stop work it knows nothing about.
        return None, None
    for rec in (r.get("value") or {}).get("decisions") or []:
        if rec.get("decision_id") == want:
            return rec, None
    return None, None


def classify(envelope, dtype, target=None, claimed_necessary=False, completed=False,
             prior=None):
    """Rule on one discovery against a compiled envelope. Deterministic.

    `claimed_necessary` is the agent's typed assertion that the authorized
    outcome is unreachable without this. It is a claim, never a conclusion --
    the engine substantiates it against declared scope or refuses it.
    """
    if dtype not in DISCOVERY_TYPES:
        return {"disposition": None, "error": "BAD_REQUEST",
                "detail": f"{dtype!r} is not a §32 discovery type: {list(DISCOVERY_TYPES)}"}

    reasons = []

    # §40, unconditional and checked FIRST. Once acceptance conditions are
    # satisfied nothing converts to execution -- including a discovery that is
    # correct, small, obviously beneficial, and genuinely necessary. Checking
    # necessity before completion would leave exactly one door open.
    if completed:
        return {"disposition": "CAPTURE_ONLY", "authority": "NONE",
                "reasons": ["authorization is exhausted (STOP_COMPLETE); §40 admits no exception"],
                "discovery_type": dtype, "target": target}

    hit = _matches(target, envelope.get("non_goals") or [])
    if hit:
        # A hard boundary. Explicit exclusion outranks any necessity claim,
        # because someone stated this is not part of the work.
        return {"disposition": "CAPTURE_ONLY", "authority": "NONE",
                "reasons": [f"matches a declared non-goal: {hit}"],
                "discovery_type": dtype, "target": target}

    # §39. A discovery decided before does not become executable by being
    # discovered again. Checked BEFORE necessity, for the same reason §40 is
    # checked before necessity: a rule with one door open is not a rule, and
    # re-claiming necessity is exactly the door.
    #
    # `prior` is data, never a provider call -- classify stays deterministic
    # and ADR-021 keeps spawning in bindings.py. main() reads it.
    if prior and prior.get("disposition") in ("DEFERRED", "REJECTED"):
        cond = prior.get("reversal_condition")
        why = [f"already decided: {prior['disposition']} "
               f"({prior.get('reason') or 'no reason recorded'})",
               "§39: rediscovered work stays CAPTURE_ONLY; discovering it again is "
               "not new evidence"]
        why.append(f"reversal condition: {cond}" if cond else
                   "no reversal condition was recorded, so nothing can establish that "
                   "this may be revisited -- that is a gap in the earlier decision, "
                   "not permission")
        if claimed_necessary:
            why.append("a necessity claim does not override a recorded decision; the "
                       "reversal condition is what does")
        return {"disposition": "CAPTURE_ONLY", "authority": "NONE", "reasons": why,
                "discovery_type": dtype, "target": target,
                "prior_decision": {"decision_id": prior.get("decision_id"),
                                   "disposition": prior.get("disposition"),
                                   "reversal_condition": cond}}

    if claimed_necessary:
        in_scope = _matches(target, envelope.get("in_scope") or [])
        if in_scope:
            return {"disposition": "EXECUTE", "authority": "NECESSARY_INCIDENTAL",
                    "reasons": [f"claimed necessary and falls within declared in_scope: {in_scope}"],
                    "discovery_type": dtype, "target": target}
        reasons.append("necessity was claimed but is unsupported: the target is outside declared "
                       "in_scope, so the claim cannot be substantiated from provider state")
        if not envelope.get("in_scope"):
            reasons.append("no in_scope was declared at all, so no necessity claim can be "
                           "substantiated for this authorization")

    lane = REVIEW_LANE.get(dtype, "CAPTURE_ONLY")
    reasons.append(f"§32 default for {dtype}: {lane}")
    return {"disposition": lane, "authority": "NONE", "reasons": reasons,
            "discovery_type": dtype, "target": target}


def record_discovery(result, manifest=None):
    """Persist a captured discovery through the decision_history provider.

    ADR-014 sketched a `.repo-governor/discoveries/` directory. That is
    superseded: ADR-019 gave decision_history a real backend, and writing
    discoveries to a file would rebuild the file-as-state pattern ADR-022 exists
    to forbid. A capture IS a recorded decision -- "considered, not authorized" --
    so it belongs in the same store as every other one.

    The id is a content hash, not a timestamp: ADR-002 forbids clock reads in the
    evaluation path, and it makes capture idempotent -- recapturing an unchanged
    discovery rewrites the same row rather than accumulating duplicates.
    """
    import hashlib
    m = manifest
    if m is None:
        m, errs = MF.load()
        if errs:
            return {"recorded": False, "why": "manifest invalid; refusing to record"}
    binding, err = B.writer_for("decision_history", "record_decision", m)
    if err:
        return {"recorded": False, "why": err["error"]["message"]}

    body = json.dumps(result, sort_keys=True)
    # IDENTITY, not content. This was a hash of the whole result, including
    # `reasons` -- so the moment a reason changed, the same rediscovered target
    # produced a different id and appended a second record, defeating the
    # idempotency `--record` promises. Identity is what the discovery IS:
    # authority, type, target. `snapshot_sha256` below still carries the full
    # content, so what was decided remains recoverable; only the key changed.
    did = discovery_id(result.get("authority_id"), result.get("discovery_type"),
                       result.get("target"))
    facts = {k: result.get(k) for k in ("disposition", "discovery_type", "authority")
             if result.get(k) is not None}
    kw = {"decision_id": did,
          "authority_id": result.get("authority_id") or "-",
          # A capture is a DEFERRAL: considered, recorded, not authorized. It is
          # not a rejection -- nobody decided against it (INV-005).
          "disposition": "DEFERRED",
          "reason": f"discovery {result.get('discovery_type')} -> {result.get('disposition')}",
          "engine_version": ENGINE_VERSION, "manifest_hash": "",
          "snapshot_sha256": hashlib.sha256(body.encode()).hexdigest(),
          "typed_facts": json.dumps(facts, sort_keys=True),
          "redacted": "true", "fields_redacted": json.dumps(["target"])}
    r = B.call("decision_history", "record_decision", kw, verb="write", manifest=m, binding=binding)
    if not r.get("ok"):
        return {"recorded": False, "why": r.get("error", {}).get("message", "write failed")}
    return {"recorded": True, "decision_id": did}


def main(argv):
    if not argv:
        print(__doc__.strip().splitlines()[-2].strip(), file=sys.stderr)
        return 2
    env = compile_envelope(argv[0])
    if "--discovery" in argv:
        spec = argv[argv.index("--discovery") + 1]
        dtype, _, target = spec.partition(":")
        completed = "--completed" in argv
        # Read before ruling. The engine wrote decisions and never read one
        # back, so §39 could not fire and every rediscovery looked new
        # (issue 95). Absence is silent: no decision_history bound, nothing
        # recorded, or an unreadable store all yield None and the verdict is
        # exactly what it was before.
        prior, _ = prior_decision(env["authority_id"], dtype, target or None)
        out = classify(env, dtype, target or None,
                       claimed_necessary="--necessary" in argv, completed=completed,
                       prior=prior)
        out["authority_id"] = env["authority_id"]
        if "--record" in argv:
            out["record"] = record_discovery(out)
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    print(json.dumps(env, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
