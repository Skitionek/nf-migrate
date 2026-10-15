# Validation across 11 pipelines

How well does the bundled migration chain (nf-core/tools 3.3.1 → 4.1.0) do
on real pipelines, compared with the template merges their maintainers
resolved by hand?

## Method

Every nf-core pipeline keeps a `TEMPLATE` branch with one commit per tools
release, and merges each of those commits into `dev` through a sync PR.
That history is ground truth: for each merge we know the pipeline before
the template update and the result a maintainer settled on.

[`scripts/evaluate_pipeline.py`](../scripts/evaluate_pipeline.py) replays
it. For every `TEMPLATE` commit whose version the chain covers, it:

1. finds the first commit on `dev`'s first-parent history that contains
   it — the merge of the sync PR;
2. exports that merge's first parent (`dev` just before the update) and
   the merge itself (the maintainers' resolution);
3. applies the pending migrations to the first, starting from the
   `nf_core_version` in its `.nf-core.yml`;
4. compares every file nf-migrate changed with the same file in the
   maintainers' merge, and records the version `nf-migrate detect` reports
   for the starting snapshot.

Two deliberate differences from a real `nf-migrate upgrade`:

- Every operation is applied, even after a conflict, so all outcomes are
  counted. The real upgrade stops a release at its first conflict.
- When one sync PR merged several `TEMPLATE` commits, the merge is counted
  once, against the newest of them.

**Outcomes.** *Applied*: the template change was made. *Already applied*:
the pipeline already had it. *Conflict*: the text the change expects is
missing or ambiguous, so a human has to decide. *Manual step*: work handed
to nf-core's own tooling (module and subworkflow updates, regenerating the
RO-Crate and container configs), reported but never blocking.

**"Identical to the human merge"** counts, among the files nf-migrate
changed, those that end up byte-identical to the maintainers' merge. It
measures whether what nf-migrate did is what the maintainers did; it does
not measure completeness, since a merge PR often holds further edits (a
CHANGELOG entry, module updates, fixes).

## Pipelines

rnaseq, sarek, mag, taxprofiler, ampliseq, methylseq, fetchngs, scrnaseq,
differentialabundance, atacseq and chipseq: widely used pipelines with
template merges in the 3.3.1–4.1.0 range, evaluated on 2026-10-15.

## Results

| Pipeline | Merges | Applied | Already applied | Conflict | Manual step | Changed files identical to the human merge |
|---|---|---|---|---|---|---|
| ampliseq | 5 | 212 | 13 | 40 | 25 | 78/92 |
| atacseq | 4 | 163 | 4 | 35 | 19 | 61/73 |
| chipseq | 3 | 173 | 5 | 23 | 18 | 55/65 |
| differentialabundance | 2 | 157 | 9 | 51 | 19 | 41/52 |
| fetchngs | 2 | 96 | 2 | 19 | 8 | 33/38 |
| mag | 4 | 131 | 16 | 56 | 16 | 39/62 |
| methylseq | 5 | 161 | 13 | 56 | 21 | 50/66 |
| rnaseq | 6 | 185 | 19 | 61 | 25 | 68/89 |
| sarek | 1 | 0 | 0 | 0 | 0 | 0/0 |
| scrnaseq | 5 | 209 | 6 | 25 | 22 | 84/94 |
| taxprofiler | 6 | 178 | 18 | 70 | 24 | 69/90 |
| **Total** | **43** | **1665** | **105** | **436** | **197** | **578/721** |

- **80% of template changes apply automatically** (1770 of 2206 text
  operations applied or already present).
- **80% of the files nf-migrate changes match the human merge** (578 of
  721).
- **5 of 40 merges would have gone through with no conflict**, all of them
  the small 4.0.2 → 4.0.3 release. Three more merges re-synced a version
  the pipeline was already on (sarek and mag at 4.1.0, methylseq at
  3.5.1); they have nothing to apply and are left out of that count.

So nf-migrate does most of a template update by itself, but nearly every
real merge still has a few conflicts for a maintainer. Because a release is
applied all-or-nothing, those few conflicts currently block the whole
release; see [Limits](#limits).

## Where the conflicts are

| Conflicts | File |
|---|---|
| 110 | `workflows/<name>.nf` |
| 54 | `subworkflows/local/utils_nfcore_<name>_pipeline/main.nf` |
| 53 | `README.md` |
| 41 | `nextflow.config` |
| 35 | `.github/workflows/nf-test.yml` |
| 21 | `tests/default.nf.test` |
| 19 | `main.nf` |
| 18 | `.github/workflows/awsfulltest.yml` |
| 14 | `tests/.nftignore` |
| 10 | `tests/nextflow.config` |
| 7 | `.github/workflows/release-announcements.yml` |
| 7 | `.github/actions/nf-test/action.yml` |
| 6 | `nf-test.config` |
| 6 | `nextflow_schema.json` |
| 6 | `assets/schema_input.json` |

Most conflicts are in code the pipeline owns, where the maintainers had to
decide too:

- **`workflows/<name>.nf`** (110). The template edits its example workflow
  body — the FastQC block, the MultiQC wiring — which real pipelines
  replace entirely. 28 of these are pipelines whose main workflow has a
  different file name.
- **The local utils subworkflow, README, `nextflow.config`, `main.nf` and
  tests** hold pipeline-specific code and text next to template code.
- **CI workflows** (`nf-test.yml`, `awsfulltest.yml`) are often customised
  with extra profiles, shards or test data.

Before nf-core modules, subworkflows and generated files became manual
steps, they caused a further 36 of rnaseq's 97 conflicts: pipelines update
modules with `nf-core modules update`, often past the template's pinned
version, so patching their files as text could not match.

## Version detection

`nf-migrate detect` works out the template version from the files instead
of trusting `nf_core_version`. On the 43 pre-merge snapshots it agreed with
the stamp 41 times:

| Pipeline | Snapshot | Stamped | Detected | Why |
|---|---|---|---|---|
| chipseq | `2270251` | 3.5.2 | 3.5.1 | 3.5.2 changes one line, so there is almost no evidence either way. |
| rnaseq | `38979633` | 4.0.2 | 4.0.3 | rnaseq had taken 7 of the 4.0.3 changes early; 6 were still missing. |

The rnaseq case is why `--detect` only ever starts an upgrade *earlier*
than the stamp: starting at 4.0.3 would have skipped the 6 missing changes,
while re-running a release that is already applied is harmless.

Outside this set, nf-core/spatialaxe shows what detection is for. Its
`dev` (`origin/dev` on 2026-10-15) is stamped 4.0.3, but it reverted the
4.0.2 template update without resetting the stamp, and detection reports
3.5.2. Upgrading to 4.1.0:

| Start from | Applied | Already applied | Conflict | Manual step |
|---|---|---|---|---|
| the stamp, 4.0.3 | 15 | 2 | 20 | 4 |
| the detected version, 3.5.2 | 83 | 30 | 40 | 13 |

From the stamp, the 4.0.x template changes spatialaxe lacks would be
skipped for good; from the detected version 68 more of them are applied,
at the cost of more conflicts. That trade-off is why detection is opt-in
(`--detect`, or the action's `detect-version`), while the report warns
about a mismatch either way.

## Skipped merges

Six merges fall outside the chain and were not evaluated:

- atacseq, chipseq, mag, scrnaseq: started from 3.2.1, before the chain's
  first version, 3.3.1.
- fetchngs: started from 3.2.0.
- fetchngs: `dev` was already stamped 3.5.2 when a 3.5.1 `TEMPLATE` commit
  was merged, and nf-migrate only upgrades.

## Limits

- **All-or-nothing releases.** One conflict blocks a whole release, so
  the 80% that applies cleanly is not written until the conflicts are
  resolved. Applying what fits and leaving conflict markers would turn
  most of these merges into partial, reviewable progress.
- **Renamed main workflow.** Operations on `workflows/<name>.nf` fail
  outright when a pipeline names its main workflow differently.
- **Skipped template features.** The chain is rendered with every template
  feature on; a pipeline that sets `skip_features` still gets operations
  for the files it left out.
- **Merge commits as ground truth.** A sync PR's merge can include
  unrelated work done in the same PR, which lowers the
  "identical to the human merge" figure without nf-migrate being wrong.

## Reproducing

```bash
# Blob-less clones keep every branch and the history without downloading
# all file contents up front.
for pipeline in rnaseq sarek mag taxprofiler ampliseq methylseq fetchngs \
    scrnaseq differentialabundance atacseq chipseq; do
  git clone --filter=blob:none --no-single-branch \
    "https://github.com/nf-core/$pipeline.git" "pipelines/$pipeline"
done

for pipeline in pipelines/*; do
  name=$(basename "$pipeline")
  uv run python scripts/evaluate_pipeline.py "$pipeline" "work/$name" \
    > "results/$name.json"
done

uv run python scripts/summarize_evaluation.py results/*.json
```

`dev` keeps moving, so later runs may pick up newer template merges. The
commits evaluated here:

| Pipeline | `origin/dev` at evaluation |
|---|---|
| ampliseq | `72003332a5` |
| atacseq | `73155d2b59` |
| chipseq | `1b3078d71c` |
| differentialabundance | `b54dae450a` |
| fetchngs | `44cdd49763` |
| mag | `264a7fe216` |
| methylseq | `998bc1fbc6` |
| rnaseq | `d810fa8d19` |
| sarek | `fd5d26bf0a` |
| scrnaseq | `0831d40e52` |
| taxprofiler | `3b8595987e` |
