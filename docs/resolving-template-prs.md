# Resolving a template sync PR by hand

The [GitHub Action](../README.md#github-action) does this on its own when no
step conflicts. This is the manual route for a PR it cannot resolve, written
from resolving about 15 real nf-core sync PRs in October 2026.

## Reproduce a PR

Use a partial clone, then fetch the PR next to `dev`:

```bash
git clone --filter=blob:none https://github.com/nf-core/<pipeline> && cd <pipeline>
```

```bash
git fetch origin dev pull/<n>/head:pr<n>
```

```bash
nf-migrate merge-template --repo . --report-file report.md --allow-conflicts --lint-fix origin/dev pr<n>
```

The last line printed on stdout is the commit with the migration result.
`report.md` lists, per release, the conflicts and the manual steps:

- `old text not found`: the pipeline changed the template text, or a file
  the template edits is gone from where it expected it. The report shows
  the template change as a diff to apply by hand.
- `held back: another change to this file conflicts`: this change fit, but
  another change to the same file did not, so the file is left as it was
  rather than half converted. Resolve the file as a whole.
- `file does not exist`: the pipeline removed or never had the file.

A conflict in one release leaves its file in the old state, so later
releases that touch it conflict too. A PR for release X therefore
contains the conflicts of every release between the version on `dev` and X.
Read the report from the oldest release down.

## What counts as clean

Clean means 0 conflicts. Manual steps (`nf-core modules update`,
`nf-core subworkflows update`, RO-Crate, container configs) do not block.
`--lint-fix` handles RO-Crate and the container configs.

## What `--lint-fix` does

After the merge commit it adds up to two commits, each from
`nf-core pipelines lint --fix`:

- `files_unchanged`: restores files that must match the template.
- `container_configs`: regenerates them. It is a second run because nf-core
  needs a clean tree and builds them from the files the first fix leaves.

It runs the nf-core release of the template through `uvx nf-core@<version>`,
because CI lints with that release, and so needs `uv`. It also puts back the
logo PNGs of the template branch, because `lint --fix` redraws them and CI
then reports a mismatch.

## Open two stacked draft PRs

Do not push to the bot's template branch. PR 1 only records the merge of
`dev` into the template branch, with the template's tree unchanged. PR 2
holds the migration and is reviewed on top of PR 1.

```bash
template_head=$(git rev-parse pr<n>)
```

```bash
merge_sha=$(git commit-tree "${template_head}^{tree}" -p "$template_head" -p origin/dev -m "Merge dev into TEMPLATE")
```

```bash
migration_sha=$(nf-migrate merge-template --repo . --allow-conflicts --lint-fix origin/dev pr<n>)
```

The migration commit descends from `dev` and the template branch, not from
`merge_sha`. Record its tree on top of PR 1, so PR 2 shows only the
migration:

```bash
stacked_sha=$(git commit-tree "${migration_sha}^{tree}" -p "$merge_sha" -m "feat: apply template with nf-migrate")
```

In zsh write `${sha}:refs/heads/x`: `$sha:refs` is read as a modifier. Use
new branch names and never force-push.

```bash
git push origin "${merge_sha}:refs/heads/template-merge-<n>"
```

```bash
git push origin "${stacked_sha}:refs/heads/template-migration-<n>"
```

PR 1 is `template-merge-<n>` with the template branch as its base. PR 2 is
`template-migration-<n>` with `template-merge-<n>` as its base. Create both
with `gh pr create --draft`.

## Gotchas

- Plain `nf-core pipelines lint` discards uncommitted changes. Commit first.
- nf-core 4.x can fail with `KeyError: 'manifest.name'` from a stale cached
  config in `~/.nextflow/nf-core`. Use a fresh `NXF_HOME`.
- Updating a shared nf-core subworkflow such as `utils_nfcore_pipeline`
  while the pipeline's local utils file still imports a function the update
  removed (`imNotification`) breaks Nextflow compilation. Update both
  together.
- A pipeline whose files lag its `nf_core_version` stamp migrates cleanly
  and may still need hand work. The report warns when the stamp and the
  files disagree; see
  [When nf_core_version is wrong](../README.md#when-nf_core_version-is-wrong).
- A rename in the template (`fix_linting.yml` to `fix-linting.yml`) conflicts
  on the old file when `dev` already took the new content under the old name:
  nf-migrate only deletes a file that is still the template's. `git mv` it
  and keep `dev`'s content.
- `nf-core pipelines lint --fix` run by hand formats files with prettier when
  it is installed, and CI's lint has none. `--lint-fix` undoes this; after a
  manual fix, restore the files the template branch holds.
- A newer nf-schema can reject params `dev` set before, such as `""` for a
  `file-path`. `--compile-check` previews the test profile to find it; set the
  default to `null`.
- On the stacked PRs the `download` and `Check PRs` checks fail whatever the
  migration holds, because their base is not `dev`. They also fail on PR 1.
- Docker nf-test failures can be pre-existing. Compare with the pipeline's
  `patch` or `dev` runs before chasing them.

## When it is done

All checks on the migration PR are green, `nf-core` lint and `pre-commit`
included, and the report has no conflicts left. What nf-migrate does not do
(pipeline-owned code and prose, module updates) is described in the
[README](../README.md) and measured in [validation.md](validation.md).
