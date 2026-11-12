#!/usr/bin/env bash
# Reproduce and fix one nf-core template sync PR with nf-migrate.
#
# Usage: fix-template-pr.sh <org/repo> <pr-number>
# Exit: 0=success (no conflicts, PR opened), 1=conflicts remain, 2=error, 4=held-claim
# Stdout: the new PR URL on success
# Stderr: progress messages
set -euo pipefail

REPO=${1:?Usage: fix-template-pr.sh org/repo pr-number}
PR=${2:?Usage: fix-template-pr.sh org/repo pr-number}

SCRIPTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=state-lib.sh
source "$SCRIPTS/state-lib.sh"

# This skill ships inside nf-migrate, so the checkout to run is the one holding
# this script. Resolve it before the cd below, and keep it absolute.
NF_MIGRATE_REPO=$(nf_repo_root)

err() { echo "$*" >&2; }

# Some pipelines asked not to receive these PRs. Check before claiming, so an
# opted-out repo neither takes a claim nor leaves a record.
if python3 "$SCRIPTS/state.py" is-opted-out "$REPO"; then
    err "$REPO opted out of nf-migrate PRs; see opt-out.txt"
    exit 3
fi

# One agent per PR. The claim is created O_EXCL under the state directory that
# every worktree shares, so two agents in two worktrees cannot both get past
# here and push duplicate branches. The remote checks further down stay as the
# authority across machines; this only serialises the local batch.
CLAIM=$(nf_claim "$REPO#$PR") || {
    err "another agent holds the claim for $REPO#$PR; skipping"
    exit 4
}

# Install the trap immediately so a failure between here and mktemp does not
# strand the claim file. WORK_DIR starts empty; the trap only removes it once
# mktemp has assigned it.
WORK_DIR=""
trap 'rm -f "$CLAIM"; [ -n "$WORK_DIR" ] && rm -rf "$WORK_DIR"' EXIT

WORK_DIR=$(mktemp -d)

# The search that finds sync PRs matches on title, which a PR from a fork can
# copy. Refuse anything but the bot's own same-repo sync PR before fetching its
# tree. See nf_sync_branch.
nf_sync_branch "$REPO" "$PR" >/dev/null || exit 2

err "=== Cloning $REPO ==="
git clone --filter=blob:none "https://github.com/$REPO.git" "$WORK_DIR/pipeline"
cd "$WORK_DIR/pipeline"

err "=== Fetching PR $PR and dev ==="
git fetch origin "dev" "pull/$PR/head:pr$PR"

err "=== Running nf-migrate ==="
REPORT="$WORK_DIR/report.md"
migration_sha=$(
    uv run --project "$NF_MIGRATE_REPO" \
        nf-migrate merge-template \
        --repo . \
        --report-file "$REPORT" \
        --allow-conflicts \
        --lint-fix \
        origin/dev "pr$PR" \
    | tail -1
)

err "=== Migration commit: $migration_sha ==="

# Check for remaining conflicts
conflict_count=$(python3 - "$REPORT" <<'EOF'
import re, sys, pathlib

text = pathlib.Path(sys.argv[1]).read_text()
# Every unresolved change is listed as "- :x: `file`: <reason>", whatever the
# reason (old text not found, held back, file exists with different content,
# file was modified locally, ...).
conflicts = re.findall(r"^- :x: ", text, re.MULTILINE)
print(len(conflicts))
EOF
)

if [ "$conflict_count" -gt 0 ]; then
    err "=== $conflict_count conflicts remain — writing report to stderr ==="
    cat "$REPORT" >&2
    exit 1
fi

err "=== No conflicts — opening the draft PR ==="

# The PR targets the sync PR's own branch, never TEMPLATE itself. The Action
# fast-forwards that branch instead; here it belongs to someone else's repo.
sync_branch=$(gh pr view "$PR" --repo "$REPO" --json headRefName --jq .headRefName)
if [ "$sync_branch" = "TEMPLATE" ]; then
    err "refusing to target TEMPLATE"
    exit 2
fi

# Never push the same work twice: a branch or PR from an earlier attempt
# (including merged ones, whose branch may be deleted) means this PR is done.
branch="template-migration-${PR}"
if git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
    err "branch $branch already exists on $REPO; refusing to duplicate"
    exit 2
fi
existing=$(gh pr list --repo "$REPO" --state all --head "$branch" \
    --json number --jq 'length')
if [ "$existing" != "0" ]; then
    err "a PR from $branch already exists on $REPO; refusing to duplicate"
    exit 2
fi

# nf-migrate builds the migration commit with both origin/dev and the sync
# branch as parents, so pushing it needs no extra merge commit: the sync
# branch is an ancestor, which keeps the PR diff down to the migration and
# leaves the bot's commit in the history that closes the sync PR. Assert it
# rather than trust it — a lost parent would silently turn the PR into
# "vanilla template vs whole pipeline".
template_head=$(git rev-parse "pr$PR")
for ancestor in "$template_head" origin/dev; do
    if ! git merge-base --is-ancestor "$ancestor" "$migration_sha"; then
        err "$ancestor is not an ancestor of $migration_sha; aborting"
        exit 2
    fi
done

git push origin "${migration_sha}:refs/heads/${branch}"

pr_url=$(gh pr create \
    --repo "$REPO" \
    --title "feat: apply template sync PR $PR with nf-migrate" \
    --body "Migration of template sync PR #${PR} applied with [nf-migrate](https://github.com/Skitionek/nf-migrate). No conflicts remain.

Merges \`dev\` and applies the template as migrations in one commit, so this PR shows only the migration. Merge it into \`${sync_branch}\` with a regular merge — no squash, no rebase — to keep the \`@nf-core-bot\` commit that closes PR #${PR}." \
    --base "$sync_branch" \
    --head "$branch" \
    --draft)

echo "$pr_url"
