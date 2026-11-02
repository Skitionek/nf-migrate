#!/usr/bin/env bash
# Re-run nf-migrate on an existing migration branch and push a patch commit if
# the result differs.
#
# Usage: patch-migration-pr.sh <org/repo> <sync-pr-number>
# Exit: 0=patched or already up-to-date, 1=conflicts remain, 2=error
# Stdout: "PATCHED <sha>" or "NO_CHANGE"
set -euo pipefail

REPO=${1:?Usage: patch-migration-pr.sh org/repo sync-pr-number}
SYNC_PR=${2:?Usage: patch-migration-pr.sh org/repo sync-pr-number}
MIG_BR="template-migration-${SYNC_PR}"

# This skill ships inside nf-migrate, so the checkout to run is the one holding
# this script: .claude/skills/<skill>/scripts/ is four levels below the root.
# Resolve it before the cd below, and keep it absolute.
NF_MIGRATE_REPO=$(
    cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd
)

err() { echo "$*" >&2; }

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

err "=== Cloning $REPO ==="
git clone --filter=blob:none "https://github.com/$REPO.git" "$WORK_DIR/pipeline"
cd "$WORK_DIR/pipeline"

err "=== Fetching sync PR $SYNC_PR, migration branch, and dev ==="
git fetch origin dev "$MIG_BR" "pull/$SYNC_PR/head:pr${SYNC_PR}"

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
