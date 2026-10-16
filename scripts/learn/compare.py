"""Operations whose agreement with the maintainers changed between runs.

Run evaluate.py before and after editing migrations or operations, then
compare: every (release, operation) that got better or worse, with how
often and its outcome before and after.

usage: compare.py BEFORE.jsonl AFTER.jsonl [RELEASE]
"""

import json
import sys
from collections import Counter
from pathlib import Path


def agreements(path: Path) -> dict[tuple, tuple]:
    """(merge, release, index) -> (agrees, outcome, file) per operation."""
    result = {}
    for line in path.read_text().splitlines():
        sample = json.loads(line)
        for entry in sample.get("operations", []):
            if not entry.get("survives") or entry.get("agree") is None:
                continue
            key = (sample["merge"], entry["rev"], entry["index"])
            result[key] = (entry["agree"], entry["outcome"], entry.get("path"))
    return result


def main() -> None:
    before = agreements(Path(sys.argv[1]))
    after = agreements(Path(sys.argv[2]))
    release = sys.argv[3] if len(sys.argv) > 3 else None

    changes: Counter = Counter()
    for key in before.keys() & after.keys():
        _, revision, index = key
        if release and revision != release:
            continue
        agreed_before, outcome_before, _ = before[key]
        agreed_after, outcome_after, path = after[key]
        if agreed_before == agreed_after:
            continue
        direction = "better" if agreed_after else "worse"
        outcomes = f"{outcome_before}->{outcome_after}"
        changes[(revision, index, path, outcomes, direction)] += 1

    for change, count in changes.most_common(40):
        print(count, change)
    totals = Counter(change[-1] for change in changes.elements())
    print(f"better {totals['better']}, worse {totals['worse']}")


if __name__ == "__main__":
    main()
