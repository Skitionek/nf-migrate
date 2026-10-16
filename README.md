# nf-migrate

Alembic-style, upgrade-only migrations for nf-core template updates.

`nf-core pipelines sync` applies a template release as one big git merge.
nf-migrate splits it into one migration per nf-core/tools release, made of
small idempotent operations, and applies them without an LLM:

- `Replace(path, old, new)` — a template diff hunk. Applied when `old`
  occurs exactly once (line-aligned), skipped as already applied when only
  `new` is present, otherwise a conflict. It looks past what pipelines
  routinely change around template text: re-aligned or trimmed spaces,
  re-indented Markdown lists and nested Nextflow blocks, Markdown
  emphasis and bullet styles, and `TODO nf-core` notes the maintainers
  resolved. Template lines next to `old` (`context_before`/`after`) pick
  one occurrence where a pipeline has several; `every=True` changes all
  of them (a CI step the pipeline copied); `requires` skips boilerplate
  for files that no longer hold any (`TODO nf-core`).
- `RemoveText(path, text)` — one paragraph of a template deletion; gone
  already counts as applied, so a pipeline keeps the sections it rewrote.
- `RegexReplace(path, pattern, replacement, applied)` — for template text
  pipelines customise in known places: groups capture the pipeline's
  parts and the replacement puts them back.
- `BumpVersion(path, prefix, old, new)` — raises a version after `prefix`
  on whatever line holds it, and leaves a newer one alone.
- `YamlSet(path, key, value)` / `YamlListItem(path, key, item, match)` —
  a YAML value, key or list item (a CI step) by its key path. Steps are
  found by `id`, `name` or action, so a pipeline's own steps around them
  do not matter.
- `ReplaceFile(path, content, already)` — for a release that rewrote a
  file (2.0 and 2.13 `main.nf`), the template's file unless the pipeline
  is on the new structure already.
- `FirstOf(path, operations)` — the exact template change first, then a
  more tolerant one, so untouched pipelines still get the template's text
  byte for byte.
- `CreateFile(path, content)` / `DeleteFile(path, expected_content)` —
  delete only removes files the pipeline left untouched.
- `NfCoreComponent(kind, name, git_sha)` — an nf-core module or subworkflow
  the template pins. Already applied when `modules.json` has that `git_sha`,
  otherwise reported with the `nf-core modules|subworkflows` command to run.
- `ManualStep(path, instruction)` — files nf-core generates (RO-Crate,
  container configs) or binary files; reported, never blocking.

An edit to a file the pipeline no longer has (`Replace`, `RegexReplace`,
`BumpVersion`, `YamlSet`, `YamlListItem`, `FirstOf`) is skipped, not a
conflict: the pipeline deleted or moved it. A file an earlier operation
creates counts as present. The report names each skipped file, so a
reviewer can check where its content went; skips never block an upgrade.

Each migration is all-or-nothing: a conflict leaves every file and the
`nf_core_version` in `.nf-core.yml` unchanged, and the report names the
conflicting hunks. With `--allow-conflicts` (on `upgrade` and
`merge-template`), every change that fits is applied and the upgrade
carries on to the target; a file with any conflicting change is left
untouched as a whole, so it is never half converted, and the report shows
each conflicting template change as a diff to apply by hand.

Migrations are pipeline-independent. Values the template bakes in are stored
as placeholders and filled from the target's `.nf-core.yml` `template:`
section: `{{pipeline_name}}`, `{{PIPELINE_NAME}}`, `{{pipeline_author}}`,
`{{pipeline_description}}`, `{{pipeline_version}}`. Pipelines from before
nf-core/tools 3.0 have no such section; as sync did then, the values come
from the `manifest` in `nextflow.config` instead.

## Upgrading a pipeline

The chain for nf-core/tools 1.9 → 4.1.0 ships with the package
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

`merge-template --lint-fix` follows the merge commit with two commits from
`nf-core pipelines lint --fix`: one for the files nf-core can restore
(action pins, RO-Crate), one for the regenerated container configs. It runs
the nf-core release of the template through `uvx`, because CI lints with that
release, and puts back the logos of the template branch, which nf-core would
redraw. It prints the last commit.

## Pipelines older than nf-core/tools 3.0

The chain starts at 1.9 because some nf-core pipelines never merged a
newer template: slamseq, imcyto and mnaseseq are still on 1.9, and
dualrnaseq and cageseq on 1.12.1 (October 2026). Their TEMPLATE branches
hold syncs up to 4.1.0, so their next sync PR has to bridge every
release in between in one git merge.

Those pipelines have no `nf_core_version`, often no `.nf-core.yml` at all.
`upgrade` and `merge-template` then start from the version `detect` finds,
and the first migration writes the stamp. Record a known version with
`stamp` first to skip detection.

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
#    Nextflow >= 26. Releases before 3.0 install with the Python and
#    dependencies of their release date.
scripts/build_template_history.sh scripts/sentinel.nf-core.yml history 4.1.0 4.2.0

# 2. Generate the migration, with the release's CHANGELOG notes as its
#    docstring, then review it.
nf-migrate --migrations src/nf_migrate/nf_core_migrations \
    revision --repo history --changelog nf-core-tools/CHANGELOG.md \
    v4.1.0 v4.2.0
```

Migrations are edited by hand where real pipelines need more than the
template diff. Those edits live as scripts in `scripts/learn/edits/`, so
regenerating the chain keeps them:

```bash
scripts/learn/rebuild.sh history nf-core-tools/CHANGELOG.md
```

`scripts/learn/` also replays every merged template update of the nf-core
pipelines against the chain, to find what to edit; see
[docs/validation.md](docs/validation.md).

Other commands: `current`, `history`, `upgrade <revision>`, and
`stamp <revision>` to record a version after resolving a step by hand.

Migrations may also define their own operation classes: anything with a
`path` and an `apply(workspace) -> OperationResult` method works.

## Validation

The chain was tuned against every merged template update of the nf-core
pipelines: 1,213 sync PRs from 129 pipelines, 1,127 of them from 1.9 or
later. On the lines a template update changes, 91.2% of nf-migrate's
operations end up where the maintainers put them, up from 89.8%;
conflicts dropped by a quarter, from 22,785 to 17,269. Most of what is
left is code and prose the pipeline owns (`workflows/<name>.nf`, README,
docs), where the maintainers decided case by case. See
[docs/validation.md](docs/validation.md) for the method, the score per
release, and the earlier 11-pipeline evaluation.

## Development

```bash
uv sync
uv run pytest -n auto
uv run ruff check . && uv run ruff format --check .
```

## License

Copyright (C) 2026 Dominik Mariusz Maszczyk

nf-migrate is free software, licensed under the GNU General Public License,
version 3 or later. See [LICENSE](LICENSE). The bundled migrations include
text from nf-core/tools, which is MIT-licensed; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
