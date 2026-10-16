"""Per-release score: share of that release's operations agreeing with the
maintainers, over every merged template PR whose range includes it.

usage: scores.py EVAL.jsonl MIGRATIONS_DIR [SCORES.tsv to append a column]
"""

import json
import sys
from collections import Counter
from pathlib import Path

from nf_migrate.migrations import load_migrations

agree, total, prs = Counter(), Counter(), {}
for line in Path(sys.argv[1]).read_text().splitlines():
    sample = json.loads(line)
    seen = set()
    for entry in sample.get("operations", []):
        if not entry.get("survives"):
            continue
        value = entry.get("agree")
        if value is None:
            value = entry.get("human") == "applied" or (
                entry["outcome"] == "CONFLICT"
                and entry.get("human") != "applied"
            )
        total[entry["rev"]] += 1
        agree[entry["rev"]] += bool(value)
        seen.add(entry["rev"])
    for rev in seen:
        prs[rev] = prs.get(rev, 0) + 1
for migration in load_migrations(Path(sys.argv[2])):
    rev = migration.revision
    score = agree[rev] / total[rev] if total[rev] else float("nan")
    print(f"{rev}\t{prs.get(rev, 0)}\t{agree[rev]}/{total[rev]}\t{score:.1%}")
