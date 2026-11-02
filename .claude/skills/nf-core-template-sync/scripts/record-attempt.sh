#!/usr/bin/env bash
# Record one attempt in the state shared by every worktree (see state.py).
#
# Usage: record-attempt.sh <key> <status> [pr-url] [notes]
#   key:    e.g. nf-core/rnaseq#1980
#   status: success | failed | skipped
set -euo pipefail

KEY=${1:?key required}
STATUS=${2:?status required}
PR=${3:-}
NOTES=${4:-}

SCRIPTS=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Values travel as argv, never interpolated into a script: notes carry
# conflict prose with quotes and backslashes, which corrupted the old
# single-file writer.
exec python3 "$SCRIPTS/state.py" record \
    "$KEY" "$STATUS" --pr "$PR" --notes "$NOTES"
