#!/usr/bin/env bash
# Shared state helpers for the nf-core template sync skill. Source, don't run.
#
# The state lives in the common git directory so that every worktree of this
# checkout shares one view. See state.py for the layout and the reasoning.

# The checkout holding this script: .claude/skills/<skill>/scripts/ is four
# levels below the root. Callers cd into temporary clones, so keep it absolute.
nf_repo_root() {
    cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd
}

# `git rev-parse --git-common-dir` is relative from the main checkout and
# absolute from a worktree, so resolve it from inside the repo either way.
# NF_TEMPLATE_SYNC_STATE_DIR overrides it, for tests and for pointing the
# state at a directory that syncs between machines.
nf_state_dir() {
    local root common
    if [ -n "${NF_TEMPLATE_SYNC_STATE_DIR:-}" ]; then
        printf '%s' "$NF_TEMPLATE_SYNC_STATE_DIR"
        return 0
    fi
    root=$(nf_repo_root) || return 1
    common=$(cd "$root" && cd "$(git rev-parse --git-common-dir)" && pwd) \
        || return 1
    printf '%s/nf-core-template-sync' "$common"
}

# `nf-core/rnaseq#1980` -> `nf-core_rnaseq_1980`. Matches key_slug in state.py.
nf_key_slug() {
    printf '%s' "$1" | sed 's/[^A-Za-z0-9._-][^A-Za-z0-9._-]*/_/g'
}

# Claim a PR for this process, or fail if another agent already holds it.
# The create is O_EXCL, so exactly one of several concurrent agents wins.
# Prints the claim path on success; the caller is responsible for removing it
# (do it from a trap, so a crash does not strand the claim).
nf_claim() {
    local key claim_dir claim
    key=$1
    claim_dir=$(nf_state_dir)/claims || return 1
    mkdir -p "$claim_dir" || return 1
    claim="$claim_dir/$(nf_key_slug "$key").claim"
    if ( set -o noclobber; : > "$claim" ) 2>/dev/null; then
        printf '%s' "$claim"
        return 0
    fi
    return 1
}
