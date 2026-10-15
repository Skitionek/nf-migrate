#!/usr/bin/env bash
# Render the nf-core template once per tools release and commit each render
# to a history repo, tagged by version. Consecutive tags then work as the
# old/new refs for `nf-migrate revision`.
#
# usage: build_template_history.sh NF_CORE_YML HISTORY_REPO VERSION...
set -euo pipefail

nf_core_yml=$(realpath "$1")
history_repo=$2
shift 2

script_dir=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$history_repo"
history_repo=$(realpath "$history_repo")
if [ ! -d "$history_repo/.git" ]; then
    git init -q "$history_repo"
fi

render_dir=$(mktemp -d)
trap 'rm -rf "$render_dir"' EXIT

for version in "$@"; do
    if git -C "$history_repo" rev-parse -q --verify "refs/tags/v$version" >/dev/null; then
        echo "v$version already rendered"
        continue
    fi
    uvx -q --from "nf-core==$version" python "$script_dir/render_template.py" \
        "$nf_core_yml" "$render_dir/$version"

    # Replace the tracked tree with this render, keeping only template files.
    git -C "$history_repo" rm -rq --ignore-unmatch .
    rsync -a --exclude .git --exclude .nextflow \
        "$render_dir/$version/" "$history_repo/"
    git -C "$history_repo" add -A
    git -C "$history_repo" \
        -c user.name=nf-migrate -c user.email=nf-migrate@localhost \
        commit -q --allow-empty -m "Template for nf-core/tools $version"
    git -C "$history_repo" tag "v$version"
    echo "v$version rendered"
done
