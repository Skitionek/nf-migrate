# Agent prompt template for fixing one template sync PR

Fill `$REPO` (e.g. `nf-core/rnaseq`) and `$PR` (e.g. `1980`) before using.
Paths are relative to the nf-migrate checkout the agent starts in.

---

You are fixing an open nf-core template sync PR for pipeline **$REPO** (PR #$PR).

Run the fix script ONCE (save its full output to a file; never rerun on failure). It handles everything (clone, migrate, open the PR):

```bash
bash .claude/skills/nf-core-template-sync/scripts/fix-template-pr.sh $REPO $PR
```

The script exits 0 on success (stdout: the new PR URL), 1 on remaining conflicts, 2 on infrastructure errors, 3 if this pipeline opted out of nf-migrate PRs, and 4 if another agent already holds the claim for this PR. On exit 3 or 4, stop without recording anything. On exit 3, report that the pipeline opted out. On exit 4, report that someone else is already working on this PR.

**Important:** the PR targets the sync PR's own head branch — never the TEMPLATE branch itself, and never `dev`.
The script enforces this. If a permission is denied, stop immediately and report it; do not work around it.

After the script finishes, record the result:

Usage is `record-attempt.sh <key> <status> [pr-url] [notes]`. Quotes and
backslashes in notes are safe; pass the conflict prose as it is.

```bash
# On success (capture the PR URL from stdout first):
bash .claude/skills/nf-core-template-sync/scripts/record-attempt.sh \
    "$REPO#$PR" success "$PR_URL"

# On failure (exit code 1 — conflicts remain):
bash .claude/skills/nf-core-template-sync/scripts/record-attempt.sh \
    "$REPO#$PR" failed "" "conflict summary here"

# On infrastructure error (exit code 2):
bash .claude/skills/nf-core-template-sync/scripts/record-attempt.sh \
    "$REPO#$PR" failed "" "infrastructure error: <details>"
```

Report back: status, conflict count (if any), and the new PR URL if opened.
