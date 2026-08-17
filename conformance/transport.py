#!/usr/bin/env python3
"""Transport equivalence — issue #18 option C.

Asserts that an adapter which can both fetch for itself (option A) and accept
raw provider output on stdin (option C) produces byte-identical results either
way. If that holds, the transport can move outside the adapter without
changing what the engine sees — which is the whole claim of option C.

Usage:  python3 conformance/transport.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SUITE = [
    {
        "adapter": "adapters/linear",
        "fetcher": "adapters/linear-fetch",
        "role": "roadmap_authority",
        "env": {"REPO_GOVERNOR_LINEAR_FIXTURE": "conformance/fixtures/linear.json"},
        "ids": ["ENG-100", "ENG-101", "ENG-102", "ENG-103", "ENG-104", "ENG-105", "ENG-106"],
        "functions": ["get_authority", "get_status", "get_work", "get_decision_history",
                      "get_non_goals", "get_parent_or_goal"],
        # Raw payloads that look plausible but are not the real thing. Each must
        # be refused, never normalized (#18 Q2).
        "substitutes": [
            ('{"summary": "ENG-102 is ready to start"}', "an LLM summary"),
            ('{"data": {"other": []}}', "the wrong query"),
            ("not json at all", "non-JSON"),
            ('{"data": {"issues": {}}}', "truncated payload"),
        ],
    },
]


def run(cmd, env_extra, stdin=None):
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                          env=env, input=stdin, timeout=30)


def main():
    failures = 0
    checks = 0
    for spec in SUITE:
        a_path = str(ROOT / spec["adapter"])
        f_path = str(ROOT / spec["fetcher"])
        env = spec["env"]
        print(f"{spec['adapter']}  <->  {spec['fetcher']}")

        raw = run([sys.executable, f_path], env).stdout

        for wid in spec["ids"]:
            for fn in spec["functions"]:
                base = [sys.executable, a_path, "query", spec["role"], fn, f"id={wid}"]
                a = run(base, env).stdout
                c = run(base + ["--input", "-"], env, stdin=raw).stdout
                checks += 1
                if a != c:
                    failures += 1
                    print(f"  [FAIL] {wid} {fn}: A and C differ")
        print(f"  [{'PASS' if not failures else 'FAIL'}] {checks} A/C comparisons byte-identical")

        # substitute payloads must be refused
        sub_ok = True
        for payload, label in spec["substitutes"]:
            base = [sys.executable, a_path, "query", spec["role"], "get_authority",
                    "id=ENG-102", "--input", "-"]
            out = run(base, env, stdin=payload).stdout
            if '"MALFORMED_SOURCE"' not in out:
                print(f"  [FAIL] accepted {label} instead of refusing it")
                sub_ok = False
                failures += 1
        if sub_ok:
            print(f"  [PASS] {len(spec['substitutes'])} substitute payloads refused as MALFORMED_SOURCE")

    print(f"\nTRANSPORT EQUIVALENCE: {'CONFIRMED' if not failures else f'BROKEN ({failures})'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
