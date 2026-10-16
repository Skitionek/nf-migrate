"""Operations to learn from: single-step PRs where the maintainers applied
a change that the migration could not place.

usage: worklist.py EVAL.jsonl [--min N] [--rev VERSION]
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

MIGRATIONS = Path("src/nf_migrate/nf_core_migrations")


def down_revisions() -> dict[str, str]:
    result = {}
    for path in MIGRATIONS.glob("v*.py"):
        source = path.read_text()
        revision = re.search(r"^revision = '(.+)'", source, re.M).group(1)
        down = re.search(r"^down_revision = '(.+)'", source, re.M).group(1)
        result[revision] = down
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("eval", type=Path)
    parser.add_argument("--min", type=int, default=4)
    parser.add_argument("--rev")
    arguments = parser.parse_args()

    down = down_revisions()
    counts: dict[tuple, Counter] = defaultdict(Counter)
    paths = {}
    for line in arguments.eval.read_text().splitlines():
        sample = json.loads(line)
        for entry in sample.get("operations", []):
            if not entry.get("survives") or entry.get("agree") is not False:
                continue
            if arguments.rev and entry["rev"] != arguments.rev:
                continue
            # In longer PRs an earlier conflict cascades into later ones.
            if sample["from"] != down.get(entry["rev"]):
                continue
            key = (entry["rev"], entry["index"])
            paths[key] = f"{entry['kind']} {entry['path']}"
            counts[key][(entry["outcome"], entry.get("hc"))] += 1

    def version(text: str) -> list[int]:
        return [int(part) for part in text.split(".")]

    rows = [
        (key, kinds[("CONFLICT", "applied")], sum(kinds.values()))
        for key, kinds in counts.items()
        if kinds[("CONFLICT", "applied")] >= arguments.min
    ]
    rows.sort(key=lambda row: (version(row[0][0]), -row[1]))
    for (revision, index), learnable, total in rows:
        print(revision, index, paths[(revision, index)][:60], learnable, total)


if __name__ == "__main__":
    main()
