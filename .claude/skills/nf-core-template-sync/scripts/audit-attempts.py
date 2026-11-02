#!/usr/bin/env python3
"""Audit the shared attempt state: status counts, and no duplicated PRs.

An agent's report can be empty or wrong, so check the facts against GitHub.
For every `success`, asks how many PRs exist for the branches this skill
pushes. More than one per branch means duplicated work; none at all means the
success was not real.

Only `template-migration-N` is expected now, since one PR carries the merge and
the migration together. `template-merge-N` is still checked for records that
predate that change, which carry the merge PR in `merge_pr`.

Also reports stale claims: a claim with no record means an agent died
mid-attempt, and that PR stays skipped until the claim is removed.

Usage: audit-attempts.py            # all successes
       audit-attempts.py KEY...     # only these keys, e.g. nf-core/rnaseq#1980
Exit code: 0 clean, 1 duplicates, a success with no PR, or a stale claim.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import state  # noqa: E402


def pr_count(repo: str, branch: str) -> int:
    completed = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--state", "all",
         "--head", branch, "--json", "number"],
        capture_output=True, text=True,
    )
    return len(json.loads(completed.stdout or "[]"))


def stale_claims(records: dict[str, dict]) -> list[str]:
    """Claims left behind by an agent that died before recording a result."""
    claims = state.claims_dir()
    if not claims.is_dir():
        return []
    recorded = {state.key_slug(key) for key in records}
    return sorted(
        path.stem for path in claims.glob("*.claim")
        if path.stem not in recorded
    )


def main() -> int:
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print(__doc__)
        return 0

    records = state.load_all()
    print(f"state: {state.state_dir()}")
    print(dict(Counter(item["status"] for item in records.values())))

    wanted = set(sys.argv[1:])
    problems: list[tuple] = []

    for key, item in records.items():
        if item["status"] != "success" or (wanted and key not in wanted):
            continue
        repo, pr = key.split("#")
        branches = [f"template-migration-{pr}"]
        # Records from the two-PR era also have a merge branch to account for.
        if item.get("merge_pr"):
            branches.append(f"template-merge-{pr}")
        counts = {branch: pr_count(repo, branch) for branch in branches}
        if any(count > 1 for count in counts.values()):
            problems.append((key, "duplicate", counts))
        elif not any(counts.values()):
            problems.append((key, "no PR found", counts))

    for claim in stale_claims(records):
        problems.append((claim, "stale claim — remove it to allow a retry", {}))

    for problem in problems:
        print("PROBLEM", *problem)
    print("clean" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
