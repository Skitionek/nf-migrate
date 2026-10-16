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

# Releases before 3.0 do not install against today's dependencies or
# Python. Resolve them as of the day after their PyPI upload instead, but
# build sdists with today's wheel and setuptools: older ones reject the
# platform tags of current macOS on arm64. Some import pkg_resources at
# runtime, which uvx environments lack and setuptools 81 dropped.
legacy_uvx_options() {
    local version=$1
    local major=${version%%.*}
    local minor=${version#*.}
    minor=${minor%%.*}
    if [ "$major" -ge 3 ]; then
        return
    fi

    local python=3.10
    if [ "$major" -eq 1 ] || [ "$minor" -lt 7 ]; then
        python=3.8
    fi
    local release_day
    release_day=$(curl -fsS "https://pypi.org/pypi/nf-core/$version/json" \
        | python3 -c 'import json, sys
print(json.load(sys.stdin)["urls"][0]["upload_time"][:10])')
    local exclude_newer
    exclude_newer=$(python3 -c 'import datetime, sys
day = datetime.date.fromisoformat(sys.argv[1])
print(day + datetime.timedelta(days=1))' "$release_day")
    local today
    today=$(date +%F)
    echo "--python $python --exclude-newer $exclude_newer" \
        "--exclude-newer-package wheel=$today" \
        "--exclude-newer-package setuptools=$today" \
        "--with setuptools<81"
}

for version in "$@"; do
    if git -C "$history_repo" rev-parse -q --verify "refs/tags/v$version" >/dev/null; then
        echo "v$version already rendered"
        continue
    fi
    # shellcheck disable=SC2046 # the options are meant to split into words
    uvx -q $(legacy_uvx_options "$version") --from "nf-core==$version" \
        python "$script_dir/render_template.py" \
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
