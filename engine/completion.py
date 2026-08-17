#!/usr/bin/env python3
"""Compose STOP_COMPLETE from three providers (ADR-017, §40).

    authority   (roadmap provider)      is this work authorized?
  + criteria    (acceptance provider)   what counts as done?
  + evaluation  (repository provider)   is it actually done?
  = disposition

No single provider is asked a question it cannot answer. The engine composes.

Deterministic (ADR-002): given the same provider responses this returns the
same disposition every time. It performs no I/O of its own beyond invoking
adapters, and reads no clock.

Usage:  python3 engine/completion.py <authority-id> [--roadmap <adapter>]
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vocabulary as V  # noqa: E402
import manifest as MF  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENGINE_VERSION = "0.1.0"
try:
    MF_HASH = hashlib.sha256((ROOT / ".repo-governor.json").read_bytes()).hexdigest()[:16]
except OSError:
    MF_HASH = None


def call(adapter, role, fn, kw, env_extra=None, verb="query"):
    env = dict(os.environ)
    env.update(env_extra or {})
    args = [sys.executable, str(ROOT / adapter), verb, role, fn]
    args += [f"{k}={v}" for k, v in kw.items()]
    p = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env, timeout=310)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"type": "NON_JSON", "message": p.stdout[:120]}}


def _classify(u, profile="GOVERNOR_LITE"):
    """Attach dimension and blocking from the closed vocabulary (gate 7).

    An adapter may not decide whether its own unknown blocks. It names a
    reason; the engine classifies. A reason outside the closed set raises,
    because silently accepting an unclassifiable unknown would let a
    provider bypass the blocking rule entirely.
    """
    dim, blocking, desc = V.classify(u["reason"], profile)
    return {**u, "dimension": dim, "blocking": blocking, "meaning": desc}


def evaluate(authority_id, roadmap_adapter, roadmap_env):
    """Return the full governance decision for the completion axis."""
    unknowns = []
    provenance = []

    # 1. authority — is this authorized at all?
    auth = call(roadmap_adapter, "roadmap_authority", "get_authority", {"id": authority_id}, roadmap_env)
    if not auth.get("ok"):
        return {"decision": "UNKNOWN", "authority_id": authority_id,
                "unknowns": [{"dimension": "authority", "reason": auth["error"]["type"],
                              "detail": auth["error"]["message"], "blocking": True}],
                "provenance": []}
    if auth.get("unknown"):
        u = _classify(auth["unknown"])
        return {"decision": "UNKNOWN", "authority_id": authority_id,
                "unknowns": [u], "provenance": []}
    provenance += auth.get("provenance", [])
    authority = auth["value"]["authority"]
    if authority in ("CANCELLED", "WITHDRAWN", "REJECTED"):
        return {"decision": "AUTHORITY_WITHDRAWN", "authority_id": authority_id,
                "authority": authority, "unknowns": [], "provenance": provenance}
    if authority == "ADMITTED":
        return {"decision": "NO_EXECUTION_AUTHORITY", "authority_id": authority_id,
                "authority": authority,
                "detail": "Admitted to the roadmap but not cleared to execute (INV-002).",
                "unknowns": [], "provenance": provenance}

    # 2. criteria — what counts as done?
    crit = call("adapters/acceptance-file", "acceptance_criteria", "get_criteria", {"id": authority_id})
    if not crit.get("ok"):
        return {"decision": "UNKNOWN", "authority_id": authority_id, "authority": authority,
                "unknowns": [{"dimension": "acceptance", "reason": crit["error"]["type"],
                              "detail": crit["error"]["message"], "blocking": True}],
                "provenance": provenance}
    if crit.get("unknown"):
        # No criteria declared => no completion bar => CONTINUE, not STOP.
        u = _classify(crit["unknown"])
        unknowns.append(u)
        return {"decision": "CONTINUE", "authority_id": authority_id, "authority": authority,
                "stop_condition": {"acceptance_conditions_satisfied": "UNKNOWN"},
                "unknowns": unknowns, "provenance": provenance}
    provenance += crit.get("provenance", [])
    criteria = crit["value"]["criteria"]

    # 3. evaluation — is it actually done?
    results = []
    for c in criteria:
        ev = call("adapters/git", "repository", "evaluate_check",
                  {"check": c["check"], "target": c["target"]})
        if not ev.get("ok"):
            unknowns.append({"dimension": "evidence", "reason": ev["error"]["type"],
                             "detail": f"{c['check']} {c['target']}: {ev['error']['message']}",
                             "blocking": True})
            results.append({**c, "satisfied": None})
            continue
        if ev.get("unknown"):
            u = _classify(ev["unknown"])
            unknowns.append(u)
            results.append({**c, "satisfied": None})
            continue
        provenance += ev.get("provenance", [])
        results.append({**c, "satisfied": ev["value"]["satisfied"]})

    unresolved = [r for r in results if r["satisfied"] is None]
    unmet = [r for r in results if r["satisfied"] is False]

    if unresolved:
        # ADR-007: must not declare completion it cannot verify.
        decision, satisfied = "UNKNOWN", "UNKNOWN"
    elif unmet:
        decision, satisfied = "CONTINUE", False
    else:
        decision, satisfied = "STOP_COMPLETE", True

    return {"decision": decision, "authority_id": authority_id, "authority": authority,
            "criteria": results,
            "stop_condition": {"acceptance_conditions_satisfied": satisfied},
            "unknowns": unknowns, "provenance": provenance}


def _repo_is_public():
    """Drives the redaction default. Unknown visibility is treated as public --
    failing conservatively, per §51."""
    try:
        p = subprocess.run(["gh", "repo", "view", "--json", "visibility", "-q", ".visibility"],
                           capture_output=True, text=True, cwd=ROOT, timeout=20)
        if p.returncode == 0:
            return p.stdout.strip().upper() != "PRIVATE"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return True


def _redact(decision, provenance, public):
    """Hash plus typed facts plus explicit markers (ADR-019).

    Never a silent omission: an omitted snapshot is indistinguishable from
    there having been no snapshot, which is the absence-versus-unknown
    confusion ADR-003 rule 6 forbids in adapters.
    """
    snapshot = json.dumps(provenance, sort_keys=True)
    sha = hashlib.sha256(snapshot.encode()).hexdigest()
    facts = {k: decision.get(k) for k in ("decision", "authority") if decision.get(k) is not None}
    if not public:
        return sha, facts, False, None
    return sha, facts, True, ["provider_snapshots"]


def record(decision, roadmap_adapter):
    """Append the decision to the bound decision-history store, if permitted.

    Returns a dict describing what happened. Recording NEVER changes the
    disposition -- it is a side effect after the fact, so ADR-002's pure
    evaluation is untouched.

    The decision id is a content hash, not a timestamp. ADR-002 forbids clock
    reads in the evaluation path, and a content-derived id also makes recording
    idempotent: re-evaluating an unchanged state rewrites the same row.
    """
    m, errs = MF.load()
    if errs:
        return {"recorded": False, "why": "manifest invalid; refusing to record"}
    allowed, why = MF.permitted(m, "decision_history", "write")
    if not allowed:
        # ADR-005 rule 5: a permission failure is a disposition, not an exception.
        return {"recorded": False, "why": f"not permitted: {why}"}

    bindings = (m.get("providers") or {}).get("decision_history") or []
    writable = [b for b in bindings if b.get("type", "").startswith("decision-history-dolt")]
    if not writable:
        return {"recorded": False, "why": "no writable decision-history backend is bound"}

    public = _repo_is_public()
    sha, facts, redacted, fields = _redact(decision, decision.get("provenance", []), public)
    body = json.dumps(decision, sort_keys=True)
    did = "d-" + hashlib.sha256(body.encode()).hexdigest()[:24]

    disp = {"STOP_COMPLETE": "ACCEPTED", "CONTINUE": "ACCEPTED",
            "AUTHORITY_WITHDRAWN": "CANCELLED", "NO_EXECUTION_AUTHORITY": "DEFERRED",
            "UNKNOWN": "DEFERRED"}.get(decision["decision"])
    if disp is None:
        return {"recorded": False, "why": f"no decision-history mapping for {decision['decision']}"}

    kw = {"decision_id": did, "authority_id": decision["authority_id"],
          "disposition": disp, "reason": f"engine decision {decision['decision']}",
          "engine_version": ENGINE_VERSION, "manifest_hash": MF_HASH or "",
          "snapshot_sha256": sha, "typed_facts": json.dumps(facts, sort_keys=True),
          "redacted": str(redacted).lower(),
          "fields_redacted": json.dumps(fields) if fields else ""}
    r = call(writable[0]["adapter"], "decision_history", "record_decision", kw, verb="write")
    if not r.get("ok"):
        return {"recorded": False, "why": r.get("error", {}).get("message", "write failed")}
    return {"recorded": True, "decision_id": did, "redacted": redacted,
            "fields_redacted": fields, "committed": False}


def main(argv):
    if not argv:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    authority_id = argv[0]
    adapter = "adapters/file-roadmap"
    env = {}
    if "--roadmap" in argv:
        adapter = argv[argv.index("--roadmap") + 1]
    if adapter == "adapters/linear":
        env = {"REPO_GOVERNOR_LINEAR_FIXTURE": "conformance/fixtures/linear.json"}
    elif adapter == "adapters/github-projects":
        env = {"REPO_GOVERNOR_GH_FIXTURE": "conformance/fixtures/github-projects-scenarios.json"}
    result = evaluate(authority_id, adapter, env)
    if "--record" in argv:
        result["record"] = record(result, adapter)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
