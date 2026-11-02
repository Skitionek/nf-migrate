#!/usr/bin/env python3
"""Classify a failed fix-template-pr.sh run: too far behind, or fixable.

Reads the script's output (stdout+stderr saved to a file) and prints:
  - the first migration step that ran (where the pipeline's real version starts)
  - conflicts per step
  - the *root* conflicts, i.e. every conflict except "held back" ones, which
    only cascade from a root conflict in the same file

Verdict TOO-FAR-BEHIND means the pipeline's files are on a template older than
4.0.x: no fallback will fix it, record `failed` and leave it for a manual port.
Verdict FIXABLE lists the files whose text to compare with the migration's
expected text (see SKILL.md, "Diagnosing a fixable failure").

Usage: triage-failure.py LOGFILE
Exit code: 0 FIXABLE, 3 TOO-FAR-BEHIND, 2 unreadable log.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

STEP_LINE = re.compile(r"^(\d+\.\d+\.\d+): (\d+) applied.*?(\d+) conflict")
CONFLICT_LINE = re.compile(r"^\s+CONFLICT (\S+): (.*)$")
# Steps at or below this version rewrite most of the template; many conflicts
# there mean the pipeline never took the earlier updates.
OLD_STEP_LIMIT = (4, 0, 0)
OLD_STEP_CONFLICTS = 5


def version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    try:
        lines = Path(sys.argv[1]).read_text().splitlines()
    except OSError as error:
        print(f"cannot read log: {error}", file=sys.stderr)
        return 2

    steps: list[str] = []
    conflicts_per_step: Counter = Counter()
    roots: dict[str, list[tuple[str, str]]] = defaultdict(list)
    current = ""
    for line in lines:
        step_match = STEP_LINE.match(line)
        if step_match:
            current = step_match.group(1)
            steps.append(current)
            conflicts_per_step[current] = int(step_match.group(3))
            continue
        conflict_match = CONFLICT_LINE.match(line)
        if conflict_match and current:
            path, reason = conflict_match.groups()
            if not reason.startswith("held back"):
                roots[current].append((path, reason))

    if not steps:
        print("no migration steps found in the log (infrastructure error?)")
        return 2

    print(f"first step run: {steps[0]}")
    for step in steps:
        print(f"  {step}: {conflicts_per_step[step]} conflicts, "
              f"{len(roots[step])} root")

    old_conflicts = sum(
        count for step, count in conflicts_per_step.items()
        if version(step) <= OLD_STEP_LIMIT
    )
    if version(steps[0]) < (4, 0, 3) and old_conflicts >= OLD_STEP_CONFLICTS:
        print(f"\nVERDICT: TOO-FAR-BEHIND ({old_conflicts} conflicts in steps "
              f"<= 4.0.0, starting at {steps[0]}); record failed, manual port.")
        return 3

    print("\nVERDICT: FIXABLE. Root conflicts to compare against "
          "the pipeline's dev:")
    for step in steps:
        for path, reason in roots[step]:
            print(f"  {step}  {path}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
