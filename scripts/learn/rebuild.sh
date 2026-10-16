#!/usr/bin/env bash
# Regenerate every bundled migration from the template renders, then apply
# the hand edits in edits/ on top, and check the chain against the renders.
#
# usage: rebuild.sh HISTORY_REPO NF_CORE_TOOLS_CHANGELOG
set -euo pipefail

history=$(realpath "$1")
changelog=$(realpath "$2")
learn_dir=$(cd "$(dirname "$0")" && pwd)
migrations=src/nf_migrate/nf_core_migrations

for migration in "$migrations"/v*.py; do
    revision=$(grep "^revision" "$migration" | cut -d"'" -f2)
    down_revision=$(grep "^down_revision" "$migration" | cut -d"'" -f2)
    uv run -q nf-migrate --migrations "$migrations" revision \
        --repo "$history" --changelog "$changelog" \
        "v$down_revision" "v$revision" >/dev/null
done

export NF_MIGRATE_HISTORY="$history"
for edit in $(ls "$learn_dir"/edits/v*.py | sort -V); do
    PYTHONPATH="$learn_dir" uv run -q python "$edit"
done

uv run -q python "$learn_dir/check_renders.py" "$history" "$migrations"
