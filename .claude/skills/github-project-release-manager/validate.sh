#!/usr/bin/env bash
# validate.sh — local structural validation for this skill.
# Mirrors what skill-creator's quick_validate.py checks, with no dependencies
# beyond python3. Run from anywhere.
set -uo pipefail
cd "$(dirname "$0")"

fail=0
say() { printf '%-42s %s\n' "$1" "$2"; }

[ -f SKILL.md ] && say "SKILL.md present" "PASS" || { say "SKILL.md present" "FAIL"; fail=1; }
[ -x detect.sh ] && say "detect.sh executable" "PASS" || { say "detect.sh executable" "FAIL"; fail=1; }

lines=$(wc -l < SKILL.md | tr -d ' ')
if [ "$lines" -lt 500 ]; then say "SKILL.md under 500 lines ($lines)" "PASS"; else say "SKILL.md under 500 lines ($lines)" "FAIL"; fail=1; fi

python3 - "$PWD" <<'PY' || fail=1
import re, sys, os
d = sys.argv[1]
s = open(os.path.join(d, 'SKILL.md')).read()
def say(k, v): print(f"{k:<42} {v}")
ok = True
m = re.match(r'^---\n(.*?)\n---\n', s, re.S)
if not m:
    say("YAML frontmatter delimited", "FAIL"); sys.exit(1)
say("YAML frontmatter delimited", "PASS")
fm = m.group(1)
name = re.search(r'^name:\s*(.+)$', fm, re.M)
desc = re.search(r'^description:\s*(.+)$', fm, re.M)
if not name or not desc:
    say("name + description present", "FAIL"); sys.exit(1)
say("name + description present", "PASS")
n = name.group(1).strip()
say(f"name matches directory ({n})", "PASS" if n == os.path.basename(d) else "FAIL")
ok &= n == os.path.basename(d)
say("name is slug-safe", "PASS" if re.fullmatch(r'[a-z0-9-]+', n) else "FAIL")
ok &= bool(re.fullmatch(r'[a-z0-9-]+', n))
dsc = desc.group(1).strip()
say(f"description single-line ({len(dsc)} chars)", "PASS" if '\n' not in dsc else "FAIL")
say("description under 1024 chars", "PASS" if len(dsc) < 1024 else "FAIL")
ok &= len(dsc) < 1024
triggers = ["manage github project", "release process", "project board",
            "prepare release", "sync project board", "triage issues into project"]
missing = [t for t in triggers if t not in dsc.lower()]
say(f"trigger phrases ({len(triggers)-len(missing)}/{len(triggers)})",
    "PASS" if not missing else "FAIL " + str(missing))
ok &= not missing
body = s[m.end():]
for h in ["## Prerequisites", "## Gotchas", "## Troubleshooting"]:
    say(f"section {h}", "PASS" if h in body else "FAIL")
    ok &= h in body
sys.exit(0 if ok else 1)
PY

echo
if [ "$fail" -eq 0 ]; then echo "VALIDATION PASSED"; else echo "VALIDATION FAILED"; fi
exit "$fail"
