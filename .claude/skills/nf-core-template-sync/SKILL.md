---
name: nf-core-template-sync
description: Find open nf-core pipeline template upgrade PRs, track which have been attempted, and fix unattempted ones in parallel agents. Use when asked to process, fix, or iterate over nf-core template sync PRs.
---

# nf-core template sync

Open nf-core template PRs (title: `Important! Template update for nf-core/tools vX.Y.Z`)
need a manual nf-migrate resolution when the GitHub Action cannot resolve them
automatically. This skill finds those PRs, skips ones already attempted, and
fixes the rest.

## Shared state

Attempts live in the **common git directory**, not in the working tree:

```bash
python3 .claude/skills/nf-core-template-sync/scripts/state.py dir
# <repo>/.git/nf-core-template-sync
```

`git rev-parse --git-common-dir` resolves to the same `.git` from every
worktree, so parallel agents in different worktrees share one view with no
commit, merge or pull in the loop. It is not committed, and should not be: this
is run bookkeeping. The durable conclusion of a failure is a migration fallback
and its test, not a note in a JSON file.

Set `NF_TEMPLATE_SYNC_STATE_DIR` to put it somewhere else, such as a directory
that syncs between machines.

One file per attempt, so concurrent agents never write the same file:

```
claims/nf-core_rnaseq_1980.claim    held only while an attempt runs
attempts/nf-core_rnaseq_1980.json   the record
```

```json
{
  "key": "nf-core/rnaseq#1980",
  "status": "success|failed|skipped",
  "pr": "https://github.com/nf-core/rnaseq/pull/1981",
  "merge_pr": "",
  "attempted_at": "2026-10-27",
  "notes": "optional free text"
}
```

`pr` is the migration PR. `merge_pr` is only set on records from before the
single-PR change, which also opened a no-op merge PR. Records migrated from the
oldest schema carry `legacy_status` so the rewrite stays auditable.

`status` values:
- `success` — migration PR opened, no conflicts remain
- `failed` — conflicts remain after nf-migrate; manual work needed
- `skipped` — not attempted (has_conflicts=false already, or other reason)

```bash
python3 .claude/skills/nf-core-template-sync/scripts/state.py list
python3 .claude/skills/nf-core-template-sync/scripts/state.py get nf-core/rnaseq#1980
```

### Claims

`fix-template-pr.sh` claims a PR before cloning, by creating its claim file
`O_EXCL`. Exactly one of several concurrent agents wins, so two agents in two
worktrees cannot both push branches for the same PR. The claim is released from
a trap on exit.

A claim left behind by a crashed agent keeps that PR skipped.
`audit-attempts.py` reports those; delete the file to allow a retry.

Claims serialise one machine. The remote checks in `fix-template-pr.sh`
(`git ls-remote`, `gh pr list`) remain the authority across machines.

## Finding open PRs

```bash
bash .claude/skills/nf-core-template-sync/scripts/list-open-prs.sh
```

Outputs JSON: `[{"repo": "nf-core/rnaseq", "pr": 1980, "key": "nf-core/rnaseq#1980"}, ...]`

### Filter rules
- **Skip pipelines that opted out** — listed in
  [`opt-out.txt`](opt-out.txt), with who asked and why. `list-open-prs.sh`
  hides them and `fix-template-pr.sh` refuses them with exit 3, before taking a
  claim. Currently `nf-core/oncoanalyser`.
- **Only the bot's own sync PRs** — opened by `nf-core-bot` from an
  `nf-core-template-merge-*` branch of the pipeline itself, never from a fork,
  as `action.yml` checks. Anyone can give a PR the sync title, so
  `list-open-prs.sh` drops any other PR, and `fix-template-pr.sh` and
  `patch-migration-pr.sh` refuse it with exit 2 before they clone anything.
- **Only the latest template version** — currently v4.2.1. Older sync PRs are skipped.
- **Skip if TEMPLATE branch has fallen behind** — check `gh api repos/<owner>/<repo>/branches/TEMPLATE --jq '.commit.commit.message'` before attempting. If the message does not contain `4.2.1`, skip with `status: skipped`.

```bash
msg=$(gh api repos/nf-core/<pipeline>/branches/TEMPLATE --jq '.commit.commit.message | split("\n")[0]')
[[ "$msg" != *"4.2.1"* ]] && echo "SKIP: TEMPLATE not at 4.2.1 ($msg)" && exit 0
```

## Checking which are unattempted

```bash
python3 .claude/skills/nf-core-template-sync/scripts/state.py list
```

Filter out keys already present. A `failed` key is worth retrying once its root
conflict has a fallback; `fix-template-pr.sh` re-claims it, and its remote
checks still refuse to open a second PR if one exists.

## Fixing one PR

Follow [`docs/resolving-template-prs.md`](../../../docs/resolving-template-prs.md),
in this repo. In brief:

```bash
bash .claude/skills/nf-core-template-sync/scripts/fix-template-pr.sh nf-core/rnaseq 1980
```

The script clones the pipeline (blob-less), reproduces the PR, runs
`nf-migrate merge-template --allow-conflicts --lint-fix`, checks for conflicts
in the report, and if clean, opens one draft PR against the bot's sync branch.

The migration commit already has both `dev` and the sync branch as parents, so
it is pushed as it stands — no separate "merge `dev`" PR. See
`docs/resolving-template-prs.md` for why that keeps the diff small and lets
GitHub close the sync PR.

It exits 0 on success, 1 on remaining conflicts, 2 on infrastructure errors
or a PR that is not the bot's own sync PR, 3 when the pipeline opted out,
and 4 when another agent already holds the claim for this PR (treat as
"skip, not a failure"). stdout: the new PR URL. stderr: progress.
Any unresolved change in the report (`- :x:` line, whatever the reason) counts
as a conflict and exits 1.

## Running in parallel agents

When iterating over unattempted PRs, spawn one agent per PR with:

- Prompt: see `scripts/agent-prompt.md` (fill `$REPO` and `$PR`)
- Each agent records its own result file when done.

Spawn at most 5 agents concurrently to avoid hammering GitHub.

Agents may run in separate worktrees; the state directory is shared, so a claim
taken in one is seen in all of them. Overlapping batches are safe for that
reason — there is no need to wait for a whole batch before starting the next.

Tell each agent to save the full script output to a file and to run the script
**once**: a failed run creates nothing, but a rerun after a transient 502 can
duplicate PRs.

## Trusting agent reports

An agent's report can be empty (`placeholder`) or wrong. Before counting a result,
check the facts yourself:

```bash
python3 .claude/skills/nf-core-template-sync/scripts/audit-attempts.py [KEY...]
```

It checks the shared state against GitHub: no branch with more than one PR, and
it reports stale claims left by a crashed agent. Every
`success` has a PR. Run it at the end of a session too.

## After a batch: diagnosing failures

For each `failed` run, triage its saved output:

```bash
python3 .claude/skills/nf-core-template-sync/scripts/triage-failure.py LOGFILE
```

- **TOO-FAR-BEHIND** (steps start at 3.x, many 4.0.0 conflicts, `nf_core_version`
  disagrees with the files): nothing to fix in nf-migrate. Leave it `failed`.
- **FIXABLE**: for each root conflict, fetch the pipeline's `dev` file
  (`gh api "repos/<repo>/contents/<path>?ref=dev" --jq .content | base64 -d`) and
  compare it with the text the migration expects in
  `nf_migrate/nf_core_migrations/v4_X_Y.py`. Usual causes: a different pin, spacing,
  a trailing comma, a file the pipeline lacks, a renamed pipeline. Add a
  `FirstOf` fallback (a no-op `RegexReplace` whose pattern equals its `applied`
  for "pipeline differs, leave alone"), a Given/When/Then test in
  `tests/test_template_fallbacks.py`, run `uv run pytest -n auto -q`, then retry
  that PR in the next batch.
- Never fix what is only a cascade: "held back" conflicts clear when their root does.

## Reporting a batch

Report:
- How many PRs were attempted
- How many succeeded / failed / skipped
- Links to opened PRs

## Maintenance

- Updated: 2026-10-28 (skip merge PR when dev already merged; triage and audit scripts)
