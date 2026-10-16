# Validation across 11 pipelines

How well does the bundled migration chain (nf-core/tools 3.3.1 → 4.1.0) do
on real pipelines, compared with the template merges their maintainers
resolved by hand? Figures are for nf-migrate 0.2.0.

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

- Every release is applied, even after a conflict, so all outcomes are
  counted: migrations run as `upgrade --allow-conflicts` does, or with
  `--partial-files` as `upgrade --partial-files` does. The 0.2.0 figures
  below applied every operation without holding files back, which
  `--partial-files` matches.
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
| ampliseq | 5 | 244 | 17 | 36 | 25 | 81/94 |
| atacseq | 4 | 189 | 5 | 37 | 19 | 63/74 |
| chipseq | 3 | 201 | 5 | 24 | 18 | 56/66 |
| differentialabundance | 2 | 181 | 9 | 49 | 19 | 41/54 |
| fetchngs | 2 | 110 | 3 | 19 | 8 | 33/39 |
| mag | 4 | 157 | 25 | 50 | 16 | 40/65 |
| methylseq | 5 | 186 | 19 | 54 | 21 | 51/69 |
| rnaseq | 6 | 209 | 28 | 60 | 25 | 69/91 |
| sarek | 1 | 0 | 0 | 0 | 0 | 0/0 |
| scrnaseq | 5 | 237 | 6 | 29 | 22 | 82/95 |
| taxprofiler | 6 | 208 | 29 | 61 | 24 | 71/95 |
| **Total** | **43** | **1922** | **146** | **419** | **197** | **587/742** |

- **83% of template changes apply automatically** (2068 of 2487 text
  operations applied or already present).
- **79% of the files nf-migrate changes match the human merge** (587 of
  742).
- **8 of 40 merges would have gone through with no conflict.** Three more
  merges re-synced a version the pipeline was already on (sarek and mag at
  4.1.0, methylseq at 3.5.1); they have nothing to apply and are left out
  of that count.

So nf-migrate does most of a template update by itself, but nearly every
real merge still has a few conflicts for a maintainer. By default a release
is applied all-or-nothing, so those few conflicts block the whole release;
`--allow-conflicts` applies everything that fits and lists the rest.

**Changes since 0.1.0.** 0.1.0 kept at least one line of context around
every template change, so a one-line change such as the README's template
version badge conflicted whenever a pipeline had edited a neighbouring
line. 0.2.0 drops the context for replacements whose changed lines are
unique. That raised automatic changes from 80% to 83% and clean merges
from 5 to 8 of 40. Some conflicts now count more than once: a change that
was one operation can become several smaller ones, which is why
`workflows/<name>.nf` went from 110 to 129 conflicts.

## Where the conflicts are

| Conflicts | File |
|---|---|
| 129 | `workflows/<name>.nf` |
| 54 | `subworkflows/local/utils_nfcore_<name>_pipeline/main.nf` |
| 37 | `nextflow.config` |
| 37 | `README.md` |
| 32 | `.github/workflows/nf-test.yml` |
| 27 | `tests/default.nf.test` |
| 19 | `main.nf` |
| 12 | `tests/.nftignore` |
| 9 | `.github/actions/nf-test/action.yml` |
| 8 | `.github/workflows/awsfulltest.yml` |
| 7 | `tests/nextflow.config` |
| 6 | `nf-test.config` |
| 6 | `nextflow_schema.json` |
| 6 | `conf/igenomes.config` |
| 6 | `assets/schema_input.json` |

Most conflicts are in code the pipeline owns, where the maintainers had to
decide too:

- **`workflows/<name>.nf`** (129). The template edits its example workflow
  body — the FastQC block, the MultiQC wiring — which real pipelines
  replace entirely. 36 of these are pipelines whose main workflow has a
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
the stamp 39 times:

| Pipeline | Snapshot | Stamped | Detected | Why |
|---|---|---|---|---|
| chipseq | `2270251` | 3.5.2 | 3.5.1 | 3.5.2 changes little more than the README's template version badge, and the badge still says 3.5.1. |
| mag | `1e050746` | 3.5.2 | 3.5.1 | Same as chipseq: the badge still says 3.5.1. |
| rnaseq | `38979633` | 4.0.2 | 4.0.3 | rnaseq had taken most of the 4.0.3 changes early; some were still missing. |
| taxprofiler | `9a8cef2` | 4.0.2 | 4.0.3 | 14 of the 4.0.3 changes were already there; 7 were still missing. |

The rnaseq and taxprofiler cases are why `--detect` only ever starts an
upgrade *earlier* than the stamp: starting at 4.0.3 would have skipped the
changes still missing, while re-running a release that is already applied
is harmless. In the chipseq and mag cases the files and the stamp disagree
only about the badge.

Outside this set, nf-core/spatialaxe shows what detection is for. Its
`dev` (`origin/dev` on 2026-10-15) is stamped 4.0.3, but it reverted the
4.0.2 template update without resetting the stamp, and detection reports
3.5.2. Upgrading to 4.1.0:

| Start from | Applied | Already applied | Conflict | Manual step |
|---|---|---|---|---|
| the stamp, 4.0.3 | 17 | 2 | 21 | 4 |
| the detected version, 3.5.2 | 90 | 40 | 41 | 13 |

From the stamp, the 4.0.x template changes spatialaxe lacks would be
skipped for good; from the detected version 73 more of them are applied,
at the cost of more conflicts. That trade-off is why detection is opt-in
(`--detect`, or the action's `detect-version`), while the report warns
about a mismatch either way.

## Pipelines older than nf-core/tools 3.0

The chain was extended from 3.3.1 down to 1.9 because slamseq, imcyto and
mnaseseq never merged a template newer than 1.9. Their migrations were
generated from renders of every release from 1.9 to 3.3.1, and checked
against those renders:

- Upgrading the 1.9 render, without a `.nf-core.yml`, through the whole
  chain to 4.1.0 applies every release without a conflict; at 3.3.1 every
  text file, `.nf-core.yml` included, is identical to the 3.3.1 render.
  Binary files, nf-core components and the RO-Crate are left as manual
  steps.
- Each migration finds all of its changes already applied on its own
  release's render, so running a release twice changes nothing.
- With `.nf-core.yml` removed, `detect` names the right release for 45 of
  the 48 renders. The other three, 2.4, 2.7 and 2.12, render exactly like
  their .1 patch releases, which changed only the version stamp.

None of the three pipelines has a `.nf-core.yml`. On their `master`
branches (2026-10-15), `detect` finds 1.9 for each, and a dry run to 4.1.0
with `--allow-conflicts` gives:

| Pipeline | Commit | Applied | Already applied | Conflict | Manual step |
|---|---|---|---|---|---|
| slamseq | `081d363` | 1338 | 23 | 743 | 101 |
| imcyto | `33eeade` | 1309 | 28 | 767 | 101 |
| mnaseseq | `eaaeaeb` | 1374 | 19 | 711 | 101 |

As in the 3.x merges above, the conflicts are in files the pipeline owns:
for slamseq, `nextflow.config`, README.md, `docs/usage.md` and `main.nf`
account for 534 of the 743. Most of them follow from an earlier conflict:
once a file is held back, later releases' changes to it no longer find
their text.

The migrations follow what each release meant to change, not every slip
it shipped. 2.3.1 put an nf-core/tools release note ("Clarified conda
usage ...") into the pipeline CHANGELOG and 2.3.2 removed it, so
`nf-migrate revision` leaves the note out of `v2_3_1.py` (listed in
`UNINTENDED_CHANGES` in `autogenerate.py`), while `v2_3_2.py` still removes
it from pipelines that merged it.

## Since 0.2.0: more changes applied automatically

Five changes raise the share of template changes nf-migrate makes by
itself: template changes that no longer fit README.md, CHANGELOG.md,
CITATIONS.md or `docs/*.md` are suggestions rather than conflicts; a
`Replace` matches lines ignoring whitespace, or on the intact side of its
context; JSON files are edited by key, falling back to the text hunk
where a pipeline renamed the key; `--partial-files` keeps the changes that
fit in a file with a conflict; and a file's manual step is reported only
from the last release that touches it. The whole chain is regenerated
with the generator fixes made for the 1.9 support.

On the same 43 merges as the 0.2.0 results above:

| | 0.2.0 | Now, `--allow-conflicts` | Now, `--partial-files` |
|---|---|---|---|
| Applied | 1922 | 1721 | 1992 |
| Already applied | 146 | 162 | 161 |
| Conflict | 419 | 592 | 322 |
| Suggested | — | 40 | 40 |
| Manual step | 197 | 144 | 144 |
| Applied automatically | 83% | 75% | 86% |
| Changed files identical to the human merge | 587/742 | 603/693 | 617/780 |
| Merges with no conflict | 8/40 | 8/40 | 8/40 |

Suggestions count as not automatic. 0.2.0 applied every operation, so its
column compares with `--partial-files`; `--allow-conflicts` holds files
with a conflict back and so applies less, but 87% of the files it changes
match the human merge. 53 manual steps are left out because a later
release in the same upgrade covers the same file. `nextflow_schema.json`
and `assets/schema_input.json`, 12 conflicts in 0.2.0, have none left.

With the chain back to 1.9 the evaluation also replays these pipelines'
older template merges: 251 merges, 238 of them updates. There
`--partial-files` applies 82% of changes automatically (14032 of 17076),
31 merges have no conflict, and 3000 of the 4258 files it changes match
the human merge.

On the three 1.9 pipelines, upgrading to 4.1.0:

| Pipeline | Before | `--allow-conflicts` | `--partial-files` | Manual steps |
|---|---|---|---|---|
| slamseq | 65% | 75% | 89% | 101 → 12 |
| imcyto | 64% | 71% | 81% | 101 → 12 |
| mnaseseq | 66% | 76% | 90% | 101 → 12 |

## Skipped merges

Six merges fall outside the chain as it stood for this evaluation and were
not evaluated. The chain now starts at 1.9, but they have not been re-run:

- atacseq, chipseq, mag, scrnaseq: started from 3.2.1, before the chain's
  first version then, 3.3.1.
- fetchngs: started from 3.2.0.
- fetchngs: `dev` was already stamped 3.5.2 when a 3.5.1 `TEMPLATE` commit
  was merged, and nf-migrate only upgrades.

## Limits

- **All-or-nothing releases by default.** One conflict blocks a whole
  release. `--allow-conflicts` writes everything that fits instead, but
  leaves any file with a conflict untouched as a whole, so the report, not
  conflict markers, shows what is left.
- **Dependencies between changes.** A text change can rely on a module or
  subworkflow update that nf-migrate only reports as a manual step: in
  4.1.0 the local utils subworkflow passes a new argument that only the
  updated `utils_nfschema_plugin` accepts.
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
  # Add --partial-files to evaluate that mode. Run one evaluation per
  # clone at a time: blob-less clones fetch file contents on demand.
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
