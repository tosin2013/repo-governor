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

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def call(adapter, role, fn, kw, env_extra=None):
    env = dict(os.environ)
    env.update(env_extra or {})
    args = [sys.executable, str(ROOT / adapter), "query", role, fn]
    args += [f"{k}={v}" for k, v in kw.items()]
    p = subprocess.run(args, capture_output=True, text=True, cwd=ROOT, env=env, timeout=310)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"type": "NON_JSON", "message": p.stdout[:120]}}


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
        u = dict(auth["unknown"]); u["dimension"] = "authority"
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
        u = dict(crit["unknown"]); u["dimension"] = "acceptance"
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
            u = dict(ev["unknown"]); u["dimension"] = "evidence"
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
    print(json.dumps(evaluate(authority_id, adapter, env), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
