#!/usr/bin/env bash
# List open nf-core template upgrade PRs as JSON.
# Output: [{"repo":"nf-core/rnaseq","pr":1980,"key":"nf-core/rnaseq#1980"}, ...]
set -euo pipefail

SCRIPTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

gh search prs \
    --state open \
    --owner nf-core \
    --limit 200 \
    --json repository,number \
    --match title \
    'Important! Template update for nf-core/tools' \
  | python3 -c '
import json, sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import state

prs = json.load(sys.stdin)
# Keep only the highest-numbered PR per repo (most recent sync PR)
top = {}
for p in prs:
    repo = "nf-core/" + p["repository"]["name"]
    pr = p["number"]
    if repo not in top or pr > top[repo]:
        top[repo] = pr

# Pipelines that asked not to receive these PRs never reach an agent.
opted_out = state.opt_outs()
for repo in sorted(opted_out & top.keys()):
    print(f"skipping {repo}: opted out", file=sys.stderr)

result = [
    {"repo": repo, "pr": pr, "key": f"{repo}#{pr}"}
    for repo, pr in top.items()
    if repo not in opted_out
]
print(json.dumps(result))
' "$SCRIPTS"
