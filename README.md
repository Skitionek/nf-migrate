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

`scripts/evaluate_pipeline.py REPO WORK_DIR` replays a pipeline's real
template merges: for each TEMPLATE commit the chain covers, it applies the
chain to `dev` just before the merge and compares the result with the merge
the maintainers resolved by hand.

Across 11 nf-core pipelines (rnaseq, sarek, mag, taxprofiler, ampliseq,
methylseq, fetchngs, scrnaseq, differentialabundance, atacseq, chipseq; 43
merges), 80% of text operations applied automatically and 578 of 721 changed
files matched the human merge. Conflicts concentrate in pipeline-owned code:
`workflows/<name>.nf`, the local utils subworkflow, README.md and
nextflow.config.

## Development

```bash
uv sync
uv run pytest -n auto
uv run ruff check . && uv run ruff format --check .
```
