# nf-migrate

Alembic-style, upgrade-only migrations for nf-core template updates.

`nf-core pipelines sync` applies a template release as one big git merge.
nf-migrate splits it into one migration per nf-core/tools release, made of
small idempotent operations, and applies them without an LLM:

- `Replace(path, old, new)` — a template diff hunk. Applied when `old`
  occurs exactly once (line-aligned), skipped as already applied when only
  `new` is present, otherwise a conflict.
- `CreateFile(path, content)` / `DeleteFile(path, expected_content)` —
  delete only removes files the pipeline left untouched.
- `NfCoreComponent(kind, name, git_sha)` — an nf-core module or subworkflow
  the template pins. Already applied when `modules.json` has that `git_sha`,
  otherwise reported with the `nf-core modules|subworkflows` command to run.
- `ManualStep(path, instruction)` — files nf-core generates (RO-Crate,
  container configs) or binary files; reported, never blocking.

Each migration is all-or-nothing: a conflict leaves every file and the
`nf_core_version` in `.nf-core.yml` unchanged, and the report names the
conflicting hunks.

Migrations are pipeline-independent. Values the template bakes in are stored
as placeholders and filled from the target's `.nf-core.yml` `template:`
section: `{{pipeline_name}}`, `{{PIPELINE_NAME}}`, `{{pipeline_author}}`,
`{{pipeline_description}}`, `{{pipeline_version}}`.

## Upgrading a pipeline

The chain for nf-core/tools 3.3.1 → 4.1.0 ships with the package
(`src/nf_migrate/nf_core_migrations`):

```bash
nf-migrate --project path/to/pipeline upgrade --dry-run
nf-migrate --project path/to/pipeline upgrade
```

## GitHub Action

Add this workflow to a pipeline repository. When nf-core-bot opens a
template sync PR, or when you run the workflow by hand, the action upgrades
the PR's base branch with the migrations, and if no step conflicts, pushes
the result to the PR branch as a merge of the base and the template commit.
It always comments the report on the PR, with manual steps
(`nf-core modules update ...`) as a checklist.

```yaml
# .github/workflows/nf-migrate.yml
name: nf-migrate
on:
  pull_request:
    types: [opened, reopened]
  workflow_dispatch:
    inputs:
      pr-number:
        description: Template sync PR to resolve (empty = newest open one)
        required: false

permissions:
  contents: write
  pull-requests: write

jobs:
  resolve-template-sync:
    if: >-
      github.event_name == 'workflow_dispatch'
      || github.event.pull_request.user.login == 'nf-core-bot'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          # A conflicting PR has no merge ref, so check out its branch.
          # Empty on workflow_dispatch, which checks out the default branch.
          ref: ${{ github.event.pull_request.head.ref }}
          fetch-depth: 0
      - uses: Skitionek/nf-migrate@main
        with:
          pr-number: ${{ inputs.pr-number }}
```

Run it by hand from the Actions tab or with
`gh workflow run nf-migrate.yml -f pr-number=123`. A manual run handles a
sync PR from any author, for example one a maintainer opened after running
`nf-core pipelines sync` locally; PRs from forks are skipped because their
branch cannot be pushed. Either way, a PR whose branch already contains its
base is left alone, so work a maintainer already merged in is never
overwritten.

Inputs: `github-token` (default `github.token`), `bot-login` (default
`nf-core-bot`, checked on PR events only), `pr-number` (manual runs),
`detect-version` (default `false`, see below), `push` and `comment` (both
default `true`). Outputs: `status` (`resolved`,
`conflicts` or `skipped`), `commit` and `pr-number`.

The push uses the credentials `actions/checkout` stored. Pushes made with
the default `GITHUB_TOKEN` do not start other workflows, so to run CI on
the resolved PR, give checkout a PAT or GitHub App token instead.

## When nf_core_version is wrong

`nf_core_version` can disagree with the files, for example after a template
update was reverted without resetting it. `nf-migrate detect` checks every
migration against the files: operations that still apply say the pipeline
is before that release, operations already applied say it is past it, and
the version most evidence agrees with wins (ties keep the stamp).

`upgrade --detect` and `merge-template --detect` (the action's
`detect-version` input) start from the detected version, but only when it
is older than the stamp: migrations already applied are no-ops, while
starting past the stamp could skip changes a partly updated pipeline still
lacks. The PR comment warns about a mismatch even without the flag.

## Adding a migration for a new tools release

```bash
# 1. Render the template per release with placeholder values into a tagged
#    history repo. Releases before 3.4 need NXF_SYNTAX_PARSER=v1 on
#    Nextflow >= 26.
scripts/build_template_history.sh scripts/sentinel.nf-core.yml history 4.1.0 4.2.0

# 2. Generate the migration, then review it.
nf-migrate --migrations src/nf_migrate/nf_core_migrations \
    revision --repo history v4.1.0 v4.2.0
```

Other commands: `current`, `history`, `upgrade <revision>`, and
`stamp <revision>` to record a version after resolving a step by hand.

Migrations may also define their own operation classes: anything with a
`path` and an `apply(workspace) -> OperationResult` method works.

## Validation

Replaying 43 real template merges from 11 nf-core pipelines, 80% of the
template changes applied automatically, and 80% of the files nf-migrate
changed matched what the maintainers merged by hand. Nearly every merge
still had a few conflicts, mostly in code the pipeline owns
(`workflows/<name>.nf`, the local utils subworkflow, README.md,
nextflow.config): 5 of 40 merges would have gone through untouched. See
[docs/validation.md](docs/validation.md) for the method, per-pipeline
results, version detection and how to reproduce it.

## Development

```bash
uv sync
uv run pytest -n auto
uv run ruff check . && uv run ruff format --check .
```
