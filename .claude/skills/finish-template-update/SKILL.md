---
name: finish-template-update
description: Finish an nf-core template update in a pipeline after nf-migrate has applied what it can - resolve the conflicts it reports, the files it held back and its manual steps, the way the pipeline's maintainers would. Use on a template sync PR or after `nf-migrate upgrade --allow-conflicts`, when the report lists conflicts or manual steps.
---

# Finishing a template update

nf-migrate applies a template release as small text operations. What it
cannot place, it leaves: **conflicts** (a change whose text the pipeline no
longer has), **held-back files** (a file with any conflict is left
untouched as a whole, so its other changes are pending too) and **manual
steps** (module updates, generated files). This skill does the rest by
reading and editing code, so the result is what the maintainers would have
merged.

The target is a pipeline that ends up **conceptually identical to the new
template where the template has a say, and unchanged everywhere else**.
Byte-identical to the template is not the goal; the pipeline's own code,
names and wording stay.

## Inputs

1. The pipeline checkout, with nf-migrate's changes applied (uncommitted,
   or as the latest commit). If it has not run yet:

   ```bash
   nf-migrate upgrade --allow-conflicts --report-file report.md
   ```

   `report.md` lists per release every conflict with the template change
   as a diff, every held-back change, and the manual steps as a checklist.
2. The template at both versions, rendered with this pipeline's values.
   On a sync PR these are the pipeline's `TEMPLATE` branch commits: the
   one already merged into the base branch (from) and the PR's (to).
   Otherwise render them with `nf-core pipelines create` from the
   pipeline's `.nf-core.yml` at each tools version. Call them `FROM/` and
   `TO/`.
3. The release notes: each migration in `src/nf_migrate/nf_core_migrations/`
   starts with its release's CHANGELOG Template notes. Read them for the
   releases in range; they say what each change is *for*.

## Procedure

Work file by file, not hunk by hunk.

1. **List the files to finish**: every path with a conflict or held-back
   change in `report.md`, plus every file `diff -r FROM TO` changes that
   the pipeline has and nf-migrate did not change (check `git diff`).
   Skip `modules/nf-core/`, `subworkflows/nf-core/`, `modules.json` and
   generated files: those are manual steps (step 5).
2. **For each file, read three versions**: `FROM/<file>`, `TO/<file>` and
   the pipeline's. `diff FROM/<file> TO/<file>` is the template's intent;
   `diff FROM/<file> <file>` is what the pipeline made its own.
3. **Apply the template's intent to the pipeline's version.** Keep every
   pipeline change that the template change does not touch. Where both
   changed the same lines, make the template's change *in the pipeline's
   terms*: its channel names, parameters, indentation, quoting and order.
   **Change only the tokens the template changes.** Leave the rest of each
   line as it is: no reflowing of ternaries or argument lists, no new
   spacing inside brackets, no trailing commas the line did not have, no
   dropped end-of-line comments. Reformatting is the most common way to
   drift from what maintainers merged.
4. **Decide per change, using the rules below.** When in doubt, apply.
   Maintainers declined fewer than one in ten of these changes; mostly
   they adapted them.
5. **Manual steps**: run each `nf-core modules|subworkflows install/update`
   command the report lists, if `nf-core` is available; never downgrade a
   component the pipeline has at a newer version. Copy changed binary files
   (logos) from `TO/`. Regenerate the RO-Crate and container configs with
   the commands given. If a tool is missing, leave the checklist item open
   and say so.
6. **Check** (below), then summarise every change you declined and why.

## Rules: what maintainers did

From 1,127 merged nf-core template updates, file by file:

**Apply fully** (infrastructure the template owns):
- `.github/workflows/*`, `.github/actions/*`: action versions, new steps,
  removed steps, matrix values. Apply to *each* copy of a step the
  pipeline duplicated. A pipeline's extra jobs, profiles or shards stay;
  never lower a version the pipeline set newer.
- `.pre-commit-config.yaml`, `.editorconfig`, `.prettierrc.yml`,
  `.prettierignore`, `.gitignore`, `.gitattributes`, `.nf-core.yml` lint
  settings, `CODE_OF_CONDUCT.md`, `.github/` issue and PR templates.
- `nextflow.config` plumbing: plugins and their versions, `validation {}`,
  profiles the template adds (`arm`, `gpu`, `mamba`...), container
  registries, `manifest` keys, `nextflowVersion`, env/shell settings,
  include lines, resource limits. The pipeline's own params and profiles
  stay.
- `conf/base.config` structure (labels, `resourceLimits`, removed
  `check_max`) — keep the pipeline's own resource values and `withName`
  blocks.
- `subworkflows/local/utils_nfcore_<name>_pipeline/main.nf`: plugin calls,
  new arguments, samplesheet parsing calls. Keep the pipeline's own
  validation, channel shaping and extra arguments; add new arguments
  after the pipeline's last one, in the call and in `take:` alike.
- `main.nf` entry-point plumbing (initialisation/completion calls, help
  arguments, genome attribute helpers). Keep the pipeline's own includes,
  genome parameters and arguments.
- Test infrastructure: `nf-test.config`, `tests/nextflow.config`,
  `tests/.nftignore` entries for files the pipeline's tests produce,
  `tests/default.nf.test` structure.
- `nextflow_schema.json`, `assets/schema_input.json`: new or changed
  generic parameters and schema keywords. The pipeline's own parameters
  and columns stay.

**Adapt** (the template's example code meets the pipeline's own):
- `workflows/<name>.nf`: apply plumbing changes — version collection,
  MultiQC inputs, method descriptions, `softwareVersionsToYAML` — to the
  pipeline's equivalent lines. A rename the template makes for the linter
  (`Channel` → `channel`) goes through the *whole* file, the pipeline's
  own lines included: that is what maintainers did. Do not add the template's example
  processes (FASTQC) or channels the pipeline does not use.
- `README.md`, `docs/usage.md`, `docs/output.md`, `CITATIONS.md`: apply
  generic changes (badges, links, Nextflow/nf-core instructions, wording
  of shared sections, `:::note` admonitions) where the pipeline still has
  that text. Rename links and versions in place.
- `conf/test.config`, `conf/test_full.config`: apply the structural change
  (resource limits format, profile names) around the pipeline's own test
  data and parameters.

**Leave out**:
- Template boilerplate for new pipelines: new `TODO nf-core` notes, and
  placeholder text (`... is a bioinformatics pipeline that ...`, the
  example FastQC/MultiQC steps and outputs, example samplesheets) in files
  where the pipeline has replaced the template's.
- Changes to files the pipeline deleted on purpose (no `lib/` after it
  moved to subworkflows, no `conf/igenomes.config` when igenomes is
  skipped, no AWS tests), unless the release re-creates them.
- Whatever a later release in the same update overwrites: aim at `TO/`.

**When a release rewrote a file** (DSL2 `main.nf` in 2.0, the utils
subworkflows in 2.13): take `TO/`'s file and port the pipeline's own code
into the new structure.

## Check before you finish

- No conflict markers: `git grep -n -E '^(<<<<<<<|>>>>>>>|=======$)'`.
- Every file nf-migrate or you changed still closes its blocks and
  strings (count `{`/`}` and `"""` in Nextflow and Groovy files). An
  operation that removes part of a block the pipeline edited can leave one
  open; finish the removal as the template's `TO/` file has it.
- Every YAML and JSON file still parses; `nextflow_schema.json` is valid
  JSON Schema.
- `nf-core pipelines lint` (if available) shows no new failures compared
  with before the update; fix those the update introduced.
- `nextflow config .` (or `nextflow run . -profile test,docker -preview`
  where possible) still parses.
- `nf_core_version` in `.nf-core.yml` is the target version (nf-migrate
  stamps it).
- `git diff` holds only template-driven changes — no reformatting of
  untouched code, no fixes the template did not ask for.

## Report

End with a short summary: per file, what you applied, what you adapted and
how, what you left out and why, and which manual steps remain open.

## Measuring it

In the nf-migrate repo, `scripts/learn/evaluate.py --merge <sha> --resolved
<pipeline dir>` scores a finished tree against the maintainers' real merge
of the same PR, on the lines the template update changes: the same scoring
as the chain's validation. The maintainers' merge itself scores 100%.
