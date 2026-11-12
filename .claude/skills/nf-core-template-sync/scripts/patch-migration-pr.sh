#!/usr/bin/env bash
# Re-run nf-migrate on an existing migration branch and push a patch commit if
# the result differs.
#
# Usage: patch-migration-pr.sh <org/repo> <sync-pr-number>
# Exit: 0=patched or already up-to-date, 1=conflicts remain, 2=error, 3=opted-out
# Stdout: "PATCHED <sha>" or "NO_CHANGE"
set -euo pipefail

REPO=${1:?Usage: patch-migration-pr.sh org/repo sync-pr-number}
SYNC_PR=${2:?Usage: patch-migration-pr.sh org/repo sync-pr-number}
MIG_BR="template-migration-${SYNC_PR}"

SCRIPTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=state-lib.sh
source "$SCRIPTS/state-lib.sh"

# This skill ships inside nf-migrate, so the checkout to run is the one holding
# this script: .claude/skills/<skill>/scripts/ is four levels below the root.
# Resolve it before the cd below, and keep it absolute.
NF_MIGRATE_REPO=$(nf_repo_root)

err() { echo "$*" >&2; }

# Some pipelines asked not to receive these PRs. Check before claiming, so an
# opted-out repo neither takes a claim nor leaves a record.
if python3 "$SCRIPTS/state.py" is-opted-out "$REPO"; then
    err "$REPO opted out of nf-migrate PRs; see opt-out.txt"
    exit 3
fi

# One agent per PR. The claim is created O_EXCL under the state directory that
# every worktree shares, so two agents cannot both patch the same branch at once.
CLAIM=$(nf_claim "$REPO#$SYNC_PR") || {
    err "another agent holds the claim for $REPO#$SYNC_PR; skipping"
    exit 2
}

WORK_DIR=$(mktemp -d)
trap 'rm -f "$CLAIM"; rm -rf "$WORK_DIR"' EXIT

# Only the bot's own same-repo sync PR may be fetched and migrated; a PR from a
# fork can copy the sync title. See nf_sync_branch.
nf_sync_branch "$REPO" "$SYNC_PR" >/dev/null || exit 2

err "=== Cloning $REPO ==="
git clone --filter=blob:none "https://github.com/$REPO.git" "$WORK_DIR/pipeline"
cd "$WORK_DIR/pipeline"

err "=== Fetching sync PR $SYNC_PR, migration branch, and dev ==="
git fetch origin dev "$MIG_BR" "pull/$SYNC_PR/head:pr${SYNC_PR}"

# Refuse if the branch has commits other than those nf-migrate produces.
# git commit-tree replaces the whole tree, so unexpected commits (e.g. a
# maintainer's manual conflict fix) would be silently reverted.
unexpected_commits=$(
    git log "origin/${MIG_BR}" --not "pr${SYNC_PR}" --not "origin/dev" \
        --format="%s" \
    | grep -vE \
        "^(Merge nf-core/tools .* template with nf-migrate\
|style: apply nf-core pipelines lint --fix\
|chore: regenerate container configs\
|fix: update migration with latest nf-migrate)$" \
    || true
)
if [ -n "$unexpected_commits" ]; then
    err "=== Branch has unexpected commits; refusing to patch ==="
    err "$unexpected_commits"
    exit 2
fi

err "=== Running nf-migrate ==="
REPORT="$WORK_DIR/report.md"
new_sha=$(
    uv run --project "$NF_MIGRATE_REPO" \
        nf-migrate merge-template \
        --repo . \
        --report-file "$REPORT" \
        --allow-conflicts \
        --lint-fix \
        origin/dev "pr${SYNC_PR}" \
    | tail -1
)
err "=== New migration SHA: $new_sha ==="

conflict_count=$(python3 - "$REPORT" <<'PYEOF'
import re, sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text()
print(len(re.findall(r"^- :x: ", text, re.MULTILINE)))
PYEOF
)

if [ "$conflict_count" -gt 0 ]; then
    err "=== $conflict_count conflicts remain ==="
    cat "$REPORT" >&2
    exit 1
fi

current_tree=$(git rev-parse "origin/${MIG_BR}^{tree}")
new_tree=$(git rev-parse "${new_sha}^{tree}")

if [ "$current_tree" = "$new_tree" ]; then
    err "=== Trees identical — nothing to patch ==="
    echo "NO_CHANGE"
    exit 0
fi

err "=== Trees differ — pushing patch commit ==="
current_tip=$(git rev-parse "origin/${MIG_BR}")
patch_sha=$(git commit-tree "$new_tree" -p "$current_tip" \
    -m "fix: update migration with latest nf-migrate")
git push origin "${patch_sha}:refs/heads/${MIG_BR}"
echo "PATCHED ${patch_sha}"
