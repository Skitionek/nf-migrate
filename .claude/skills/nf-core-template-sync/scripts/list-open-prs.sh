#!/usr/bin/env bash
# List open nf-core template upgrade PRs as JSON.
# Output: [{"repo":"nf-core/rnaseq","pr":1980,"key":"nf-core/rnaseq#1980"}, ...]
set -euo pipefail

SCRIPTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# The title can be copied by anyone, so only the bot's PRs are searched for
# (state.py BOT_LOGIN), and each one is checked again below before it is listed.
gh search prs \
    --state open \
    --owner nf-core \
    --author nf-core-bot \
    --limit 200 \
    --json repository,number \
    --match title \
    'Important! Template update for nf-core/tools' \
  | python3 -c '
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import state


def is_sync_pr(repo, pr):
    """Whether the bot opened this PR from a branch of the repo itself.

    The title matched, but a PR from a fork can copy it.
    """
    completed = subprocess.run(
        ["gh", "pr", "view", str(pr), "--repo", repo,
         "--json", "author,isCrossRepository,headRefName"],
        capture_output=True, text=True,
    )
    if completed.returncode != 0:
        reason = "cannot read it from GitHub"
    else:
        try:
            info = json.loads(completed.stdout)
        except json.JSONDecodeError:
            info = None
        reason = state.sync_pr_refusal(info)
    if reason:
        print(f"skipping {repo}#{pr}: {reason}", file=sys.stderr)
    return reason is None


prs = json.load(sys.stdin)
numbers = {}
for p in prs:
    repo = "nf-core/" + p["repository"]["name"]
    numbers.setdefault(repo, []).append(p["number"])

# Pipelines that asked not to receive these PRs never reach an agent.
opted_out = state.opt_outs()
for repo in sorted(opted_out & numbers.keys()):
    print(f"skipping {repo}: opted out", file=sys.stderr)

# Keep only the highest-numbered sync PR per repo (most recent sync PR). A
# newer PR that is not the bot-opened one must not hide the real one.
top = {}
for repo, candidates in numbers.items():
    if repo in opted_out:
        continue
    for pr in sorted(candidates, reverse=True):
        if is_sync_pr(repo, pr):
            top[repo] = pr
            break

result = [
    {"repo": repo, "pr": pr, "key": f"{repo}#{pr}"}
    for repo, pr in top.items()
]
print(json.dumps(result))
' "$SCRIPTS"
