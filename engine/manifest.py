#!/usr/bin/env python3
"""Governance manifest loader (ADR-004, ADR-005, ADR-013, ADR-015, ADR-016).

Loads `.repo-governor.json` and fails closed. The manifest is the SOLE
artifact that binds providers to governance roles (INV-013) — a detected,
reachable, credentialed provider absent from this file has no role and is
never consulted.

Rules enforced here, beyond the schema:

  version gate     an unimplemented version refuses to evaluate, not guesses
  cardinality      single-valued authority roles vs multi-valued evidence roles
  no secrets       a token-shaped value fails the load outright
  adapter paths    must resolve inside the repository
  deny by default  unlisted role, unlisted verb, malformed block => deny
  execute reserved rejected at v1

Usage:  python3 engine/manifest.py [path]        validate and summarise
        python3 engine/manifest.py --explain <role> <verb>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jsonschema_mini import validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "manifest-v1.json"
DEFAULT = ROOT / ".repo-governor.json"

SUPPORTED_VERSIONS = (1,)

# ADR-013 cardinality. Roles answering "is this authorized?" are single-valued:
# two sources of authorization is no source of authorization.
SCALAR_ROLES = ("roadmap_authority", "execution", "repository", "acceptance_criteria")
ARRAY_ROLES = ("architecture", "change_signals", "retirement", "decision_history")

VERBS = ("read", "write", "create", "update", "archive", "comment", "transition")
RESERVED_VERBS = ("execute",)

# ADR-005 rule 3: credentials never live here. Detection is structural, not advisory.
SECRET_PREFIXES = ("ghp_", "gho_", "ghs_", "github_pat_", "lin_api_", "xox",
                   "sk-", "AKIA", "glpat-", "-----BEGIN")
SECRET_KEYS = re.compile(r"(token|secret|password|passwd|api_?key|credential)", re.I)


class ManifestError(ValueError):
    pass


def _looks_secret(key, value):
    if isinstance(value, str):
        if any(value.startswith(p) for p in SECRET_PREFIXES):
            return f"value at {key} starts with a known credential prefix"
        # High-entropy long opaque string in a config file is a smell -- but a
        # PATH is not opaque. `adapters/decision-history-github` is 32 chars and
        # matched the original pattern, which is the kind of false positive that
        # gets a security check switched off. Credentials do not contain path
        # separators or dots; require their absence before flagging.
        if (len(value) >= 32 and "/" not in value and "." not in value
                and re.fullmatch(r"[A-Za-z0-9+/=_-]{32,}", value)):
            return f"value at {key} looks like an opaque credential ({len(value)} chars)"
    if SECRET_KEYS.search(str(key)):
        return f"key {key!r} names a credential; credentials come from the environment"
    return None


def _scan_secrets(node, path="$"):
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            hit = _looks_secret(f"{path}.{k}", v)
            if hit:
                found.append(hit)
            found += _scan_secrets(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += _scan_secrets(v, f"{path}[{i}]")
    return found


def load(path=None):
    """Return (manifest, errors). A non-empty error list means DO NOT evaluate."""
    p = Path(path) if path else DEFAULT
    if not p.exists():
        # Absent manifest is not an error; the repository is un-onboarded.
        return None, [f"AUTHORITY_SOURCE_MISSING: no manifest at {p}"]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, [f"MALFORMED: {p} is not valid JSON: {e}"]

    # 1. version gate BEFORE schema, so a future version fails cleanly.
    ver = (data.get("repo_governor") or {}).get("version")
    if ver not in SUPPORTED_VERSIONS:
        return None, [f"UNSUPPORTED_VERSION: manifest version {ver!r}; "
                      f"this engine implements {list(SUPPORTED_VERSIONS)}. Refusing to guess."]

    errs = []

    # 2. schema
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs += [f"SCHEMA: {e}" for e in validate(data, schema)]

    # 3. secrets — structural, not advisory
    errs += [f"SECRET: {s}" for s in _scan_secrets(data)]

    providers = data.get("providers") or {}

    # 4. cardinality (ADR-013)
    for role in SCALAR_ROLES:
        if role in providers and isinstance(providers[role], list):
            errs.append(f"CARDINALITY: {role!r} is single-valued; got a list. "
                        "Two sources of authorization is no source of authorization.")
    for role in ARRAY_ROLES:
        if role in providers and not isinstance(providers[role], list):
            errs.append(f"CARDINALITY: {role!r} is multi-valued; got a scalar.")

    # 5. repository role always required
    if "repository" not in providers:
        errs.append("MISSING_ROLE: 'repository' is the only always-required role (ADR-003 rule 4).")

    # 6. adapter paths must stay inside the repository
    for role, binding in providers.items():
        if role.startswith("$"):
            continue
        for b in (binding if isinstance(binding, list) else [binding]):
            if not isinstance(b, dict):
                continue
            adapter = b.get("adapter", "")
            resolved = (ROOT / adapter).resolve()
            if not str(resolved).startswith(str(ROOT)):
                errs.append(f"ADAPTER_PATH: {role} adapter {adapter!r} escapes the repository.")
            elif not resolved.exists():
                errs.append(f"ADAPTER_MISSING: {role} adapter {adapter!r} does not exist.")

    # 7. permissions: closed verb set, reserved verbs rejected
    for role, block in (data.get("permissions") or {}).items():
        if role.startswith("$"):
            continue  # $comment and friends are annotations, not roles
        if role not in providers:
            errs.append(f"PERMISSION_ORPHAN: permissions declared for unbound role {role!r}.")
        if not isinstance(block, dict):
            errs.append(f"PERMISSION_MALFORMED: {role!r} block is not an object; resolves to deny.")
            continue
        for verb in block:
            if verb.startswith("$"):
                continue  # annotation, not a verb
            if verb in RESERVED_VERBS:
                errs.append(f"PERMISSION_RESERVED: {verb!r} is reserved and unimplemented at v1 "
                            "(ADR-005 rule 6).")
            elif verb not in VERBS:
                errs.append(f"PERMISSION_UNKNOWN_VERB: {verb!r} on {role!r}; "
                            f"closed set is {list(VERBS)}.")

    return (None if errs else data), errs


def permitted(manifest, role, verb):
    """Deny by default. Absence is denial, never inheritance or inference."""
    if not manifest:
        return False, "no manifest loaded"
    if role not in (manifest.get("providers") or {}):
        return False, f"role {role!r} is not bound"
    block = (manifest.get("permissions") or {}).get(role)
    if not isinstance(block, dict):
        return False, f"no permission block for {role!r} — absence is denial"
    if verb not in block:
        return False, f"verb {verb!r} not granted on {role!r} — absence is denial"
    if block[verb] is not True:
        return False, f"verb {verb!r} explicitly denied on {role!r}"
    return True, f"granted in manifest permissions.{role}.{verb}"


def check_adapters(manifest):
    """ADR-004 step 3: does each adapter actually satisfy its declared contract?

    A manifest can declare contract_version 1 for an adapter that implements
    something else. The declaration is a claim; this verifies it.
    """
    import subprocess
    findings = []
    for role, binding in (manifest.get("providers") or {}).items():
        if role.startswith("$"):
            continue
        for b in (binding if isinstance(binding, list) else [binding]):
            adapter = b["adapter"]
            declared = b.get("contract_version")
            try:
                p = subprocess.run([sys.executable, str(ROOT / adapter), "describe"],
                                   capture_output=True, text=True, cwd=ROOT, timeout=30)
                d = json.loads(p.stdout)
            except Exception as e:  # noqa: BLE001
                findings.append((role, adapter, "UNREACHABLE", str(e)[:60]))
                continue
            if d.get("role") != role:
                findings.append((role, adapter, "ROLE_MISMATCH",
                                 f"adapter serves {d.get('role')!r}, manifest binds it to {role!r}"))
            actual = d.get("contract_version")
            if declared is not None and actual != declared:
                findings.append((role, adapter, "CONTRACT_MISMATCH",
                                 f"manifest declares {declared}, adapter implements {actual}"))
            if not d.get("transport", {}).get("reachable", True):
                findings.append((role, adapter, "TRANSPORT_UNREACHABLE",
                                 "adapter advertises no capabilities; transport is not configured"))
    return findings


def main(argv):
    if argv and argv[0] == "--validate":
        m, errs = load()
        if errs:
            print("MANIFEST INVALID — cannot validate adapters\n")
            for e in errs:
                print(f"  {e}")
            return 1
        findings = check_adapters(m)
        for role, adapter, kind, detail in findings:
            print(f"  [{kind}] {role} -> {adapter}: {detail}")
        n = len(m["providers"]) 
        print(f"\n{'READY_FOR_GOVERNANCE' if not findings else 'PROVIDER_UNAVAILABLE'} "
              f"({n} bindings, {len(findings)} finding(s))")
        return 0 if not findings else 1

    if argv and argv[0] == "--explain":
        if len(argv) < 3:
            print("usage: --explain <role> <verb>", file=sys.stderr)
            return 2
        m, errs = load()
        ok, why = permitted(m, argv[1], argv[2])
        print(f"{'ALLOW' if ok else 'DENY '}  {argv[1]}.{argv[2]}  — {why}")
        return 0

    m, errs = load(argv[0] if argv else None)
    if errs:
        print(f"MANIFEST INVALID ({len(errs)} error(s)) — refusing to evaluate\n")
        for e in errs:
            print(f"  {e}")
        return 1
    p = m["providers"]
    print("MANIFEST VALID")
    print(f"  repository : {m['repository']['id']}")
    print(f"  condition  : {m['condition']['assessed']} / {m['condition']['profile']}")
    print(f"  bindings   : {len(p)} role(s)")
    for role in sorted(k for k in p if not k.startswith("$")):
        b = p[role]
        names = ", ".join(x["type"] for x in (b if isinstance(b, list) else [b]))
        print(f"    {role:<20} {names}")
    print("  permissions:")
    for role in sorted(k for k in m.get("permissions", {}) if not k.startswith("$")):
        granted = [v for v, on in m["permissions"][role].items() if on is True]
        print(f"    {role:<20} {', '.join(granted) or '(none granted)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
