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

## Open one draft PR

The [Action](../action.yml) needs no PR at all: it pushes the migration
commit straight onto the bot's sync branch, which is a fast-forward because
that branch is one of the commit's parents. The bot's own PR into `dev` then
carries the resolution.

The manual route cannot do that — the sync branch lives in a repo you do not
own — so it proposes the same commit as a PR *into* that branch.

```bash
migration_sha=$(nf-migrate merge-template --repo . --allow-conflicts --lint-fix origin/dev pr<n>)
```

Push that commit as it stands. `merge-template` builds it with both
`origin/dev` and `pr<n>` as parents, which is what makes a single PR work:

- `dev` is an ancestor, so GitHub resolves the PR's merge base to the `dev`
  commit the migration merged, and the diff is the migration alone rather
  than "vanilla template vs the whole pipeline";
- `dev` being an ancestor also makes the later merge into `dev` take the
  migrated tree whole instead of fighting every pipeline customisation;
- the sync branch is an ancestor, so the `@nf-core-bot` commit stays in the
  history and GitHub closes the original sync PR when this lands.

Re-parenting the tree onto a separate "merge `dev`" commit reaches the same
place by a longer road. That commit is what puts `dev` back in the ancestry,
so it is load-bearing rather than cosmetic: its own diff is empty, but
without it the migration PR would show the whole pipeline. It is needed only
because the re-parenting dropped the parents `merge-template` had already
set. Pushing `migration_sha` unchanged keeps all three properties and skips
the extra PR.

In zsh write `${sha}:refs/heads/x`: `$sha:refs` is read as a modifier. Use a
new branch name and never force-push.

```bash
git push origin "${migration_sha}:refs/heads/template-migration-<n>"
```

The PR is `template-migration-<n>` with the bot's sync branch as its base —
never `TEMPLATE`, which
[must hold only vanilla template code](https://nf-co.re/docs/guidelines/pipelines/requirements/git_branches),
and never `dev`, which would bypass the sync PR. Create it with
`gh pr create --draft`.

It has to land as a regular merge:
[nf-core's docs](https://nf-co.re/docs/tutorials/sync/merging_automated_prs)
say *"use a regular merge and do not squash template update PRs"*. Squashing
or rebasing rewrites the bot's commit hash, and the original sync PR then
never closes — `pathogenepidemiology` #60 was squash-merged, which is why its
sync branch head is not an ancestor of `dev`.

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
- On the migration PR the `download` and `Check PRs` checks fail whatever the
  migration holds, because its base is the sync branch and not `dev`.
- The PR diff is the sync branch's tree against the migrated tree, so it
  contains everything that makes the pipeline differ from the bare template,
  not just the template update. It stays small for a pipeline close to the
  template (32 files on bamtofastq) and grows with divergence (300+ on
  oncoanalyser, where the maintainer expected under 50 and closed it). Basing
  the PR on `dev` would show the template update alone, but it would bypass
  the sync PR and so never close it. Unresolved; say which it is when asking
  for a review.
- A sync PR left open while `dev` moves on goes stale fast, and a stale one
  cannot be rebased onto `dev`: its parents are template commits for an older
  release, so replaying them onto a tree already at the new version conflicts
  on the first one. Re-run `merge-template` against current `dev` instead.
- Docker nf-test failures can be pre-existing. Compare with the pipeline's
  `patch` or `dev` runs before chasing them.

## When it is done

All checks on the migration PR are green, `nf-core` lint and `pre-commit`
included, and the report has no conflicts left. What nf-migrate does not do
(pipeline-owned code and prose, module updates) is described in the
[README](../README.md) and measured in [validation.md](validation.md).
