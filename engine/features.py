#!/usr/bin/env python3
"""Which authority governs a Spec Kit feature? Only what was declared (ADR-037).

Spec Kit names work by feature directory (`specs/001-add-auth/`). The engine
names it by authority id. The link between the two is a committed file a human
wrote, `.repo-governor/speckit-features.json`, validated against
`schemas/speckit-features-v1.json`:

    {"features": {"001-add-auth": "142", "checkout-flow": "ENG-7"}}

WHAT THIS DOES NOT DO, and must never do:

  It does not infer. `001-add-auth` does not mean issue 1, a branch called
  `142-auth` does not mean issue 142, and a spec that mentions "#142" means
  nothing at all. Each of those is an authority id derived from content, which
  ADR-028 forbids for provider identity and ADR-029 constraint 1 forbids for
  hooks. A guess that happens to be right is indistinguishable from one that is
  wrong until it governs the wrong work.

  It does not decide. It answers "which id?", never "may I?". The caller asks
  `completion.py` about the id it returns.

Three ways it answers UNKNOWN, each with its own reason:

  MAPPING_ABSENT    no mapping file. A configuration gap: reported, blocks
                    nothing (ADR-031's engine rule). The caller discloses that
                    authority was not checked.
  MAPPING_INVALID   the file exists and does not satisfy the schema. Blocking:
                    a file somebody wrote and got wrong is not the same as no
                    file, and reading past it would be reading a guess.
  FEATURE_UNMAPPED  the file exists and does not name this feature. Blocking:
                    this repository maps its features, and this one has no
                    declared authority.

A path is accepted in place of a name, because Spec Kit's own scripts report
the feature as a directory path. Only the final component is used; it is the
same identity, not a derived one.

Usage:  python3 engine/features.py <feature-name-or-dir>
Output: JSON on stdout. Exit 0 whenever an answer was produced, UNKNOWN
        included; 2 on bad arguments.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import manifest as M  # noqa: E402
from jsonschema_mini import validate  # noqa: E402

SCHEMA = M.ROOT / "schemas" / "speckit-features-v1.json"
REL = Path(".repo-governor") / "speckit-features.json"


def mapping_path(root=None):
    return Path(root or M.target()) / REL


def check(root=None):
    """(path, data, errors). data is None when the file is absent or invalid."""
    p = mapping_path(root)
    if not p.exists():
        return p, None, []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return p, None, [f"not valid JSON: {e}"]
    errs = validate(data, json.loads(SCHEMA.read_text(encoding="utf-8")))
    return p, (None if errs else data), errs


def _unknown(feature, reason, blocking, detail, resolution):
    return {"feature": feature, "authority_id": None,
            "unknowns": [{"reason": reason, "blocking": blocking,
                          "detail": detail, "resolution": resolution}]}


def resolve(feature, root=None):
    name = Path(feature).name if ("/" in feature or "\\" in feature) else feature
    p, data, errs = check(root)
    if not p.exists():
        return _unknown(name, "MAPPING_ABSENT", False,
                        f"No feature map at {REL}. Which authority governs {name!r} is "
                        "undeclared, so authority was not checked.",
                        f"Declare the feature in {REL}, or proceed knowing this work is "
                        "ungoverned.")
    if errs:
        return _unknown(name, "MAPPING_INVALID", True,
                        f"{REL} does not satisfy schemas/speckit-features-v1.json: "
                        + "; ".join(errs[:3]),
                        f"Fix {REL}; engine/manifest.py --validate reports the same errors.")
    authority = data["features"].get(name)
    if authority is None:
        return _unknown(name, "FEATURE_UNMAPPED", True,
                        f"{REL} declares {len(data['features'])} feature(s) and not "
                        f"{name!r}. No authority id is inferred from the name.",
                        f"Add {name!r} to {REL} with the authority id that governs it.")
    return {"feature": name, "authority_id": authority, "unknowns": [],
            "cites": [{"source": "speckit-features", "path": str(REL),
                       "key": f"features.{name}"}]}


def main(argv):
    if len(argv) != 1 or not argv[0] or argv[0].startswith("-"):
        print(__doc__ if argv[:1] in (["-h"], ["--help"]) else
              "usage: features.py <feature-name-or-dir>",
              file=sys.stdout if argv[:1] in (["-h"], ["--help"]) else sys.stderr)
        return 0 if argv[:1] in (["-h"], ["--help"]) else 2
    print(json.dumps(resolve(argv[0]), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
