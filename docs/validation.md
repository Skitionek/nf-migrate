# Validation

## Every merged template update (October 2026)

The bundled chain (nf-core/tools 1.9 → 4.1.0) was tuned release by release
against the template updates nf-core maintainers actually merged, and
scored the same way before and after.

### Samples

All 159 repositories of the nf-core pipelines list were cloned on
2026-10-16 (157 still exist). A template update is a first-parent commit
on `dev` (or the default branch) that brings in new `TEMPLATE` commits:
the merge of a sync PR. Its versions come from the `TEMPLATE` history
itself, not from `nf_core_version`, which older pipelines lack: the
newest `TEMPLATE` commit the branch had before, and the newest it brings
in. That gives 1,213 merged updates from 129 pipelines; 1,127 start at
1.9 or later and are replayed. Each is replayed straight from git objects
([`scripts/learn/evaluate.py`](../scripts/learn/evaluate.py)): the
migrations from its from-version to its to-version are applied to the
commit before the merge, every operation even after a conflict, and the
result is compared with the merge.

### Scoring "conceptually the same"

A sync PR is more than the template change: maintainers fix things,
update modules, write CHANGELOG entries. So nothing is compared byte for
byte. For each operation, only the lines it adds or removes count,
whitespace-insensitive, and the score asks whether nf-migrate's result
and the maintainers' merge agree on each of those lines being there. A
change the maintainers adapted (applied around their own edits) counts as
applied; one they left out counts as kept. Two kinds of samples are not
scored:

- files whose merge was committed with conflict markers (several 1.x and
  2.x merges did), which hold both sides;
- operations whose change a later release in the same PR overwrites.

When looking for what to fix, only single-release PRs count
([`scripts/learn/worklist.py`](../scripts/learn/worklist.py)): in a PR
spanning several releases, one conflict early on leaves the file in its
old state and every later change to it fails as well.

### Results

| | Before | After |
|---|---|---|
| Operations agreeing with the maintainers | 89.8% (83,542 / 93,047) | 91.2% (89,059 / 97,699) |
| Conflicts | 22,785 | 17,350 |
| Template-changed lines handled as the maintainers did | 86.4% | 88.2% |
| PRs replayed without any conflict | 116 / 1,127 | 150 / 1,127 |

Before is commit `06f8033` (nf-migrate 0.2.0 and the fixes after it);
after is this version. The operation count grows
because large deletions are now removed paragraph by paragraph.

Most of the gain came from changes to how operations match, which help
every release at once:

- **Placeholders.** 2.x renders name the workflow class
  `lib/Workflow<Name>.groovy` with a capitalised name, which no
  placeholder covered; 29 operations pointed at a file no pipeline has.
  `{{Pipeline_name}}` fixes them.
- **Layout.** Re-aligned or trimmed spaces, Markdown lists re-indented by
  a formatter, `__bold__` written as `**bold**`, and template blocks a
  pipeline nested one level deeper in its own Nextflow code no longer
  stop a change.
- **Resolved notes.** Maintainers delete `TODO nf-core` notes once they
  act on them; a hunk holding one now also matches without it, and
  template boilerplate (a new TODO, a placeholder sentence) is not added
  to files that have none left.
- **Deletions.** A template deletion is removed paragraph by paragraph
  (`RemoveText`), so the generic sections a pipeline kept go and the ones
  it rewrote stay, as the maintainers did in 1.10 and 2.0. In code, only
  paragraphs that close every bracket and string they open are removed on
  their own; a block like 3.4.0's `validation { help { ... } }` goes as a
  whole or not at all, so a file is never left half removed.
- **Repeated text.** Template lines around a hunk pick the occurrence when
  a pipeline has the text twice; a one-line CI change applies to every
  copy of a step.
- **YAML by key path.** GitHub workflow changes are made on the value,
  key or step they concern (`YamlSet`, `YamlListItem`); steps are found
  by `id`, `name` or action, wherever the pipeline put them.
- **Versions.** A version bump in a line the pipeline also edited (a
  plugin id with its own comment) raises the version alone
  (`BumpVersion`), and never lowers a newer one.

Hand edits, kept as scripts in
[`scripts/learn/edits/`](../scripts/learn/edits), cover what the template
diff cannot express: `main.nf` in 2.0 and 2.13 and
`bin/scrape_software_versions.py` in 2.0 replaced as a whole
(`ReplaceFile`), since in every converting PR the maintainers took the
template's file and moved their own code; blocks re-anchored where
pipelines extend the neighbouring text (container profiles, igenomes
entries, `modules.config`, the help arguments of 3.4.0); and patterns
for the parts pipelines customise (the `helpMessage()` body, the table of
contents in `usage.md`, `check_max` around a pipeline's own resources).
Each edit is a `FirstOf` that tries the exact template change first, so
the chain still turns each release's render into the next one byte for
byte.

### Score per release

Share of the release's operations that agree with the maintainers, over
every PR whose range includes the release.

| Release | PRs | Before | After |
|---|---|---|---|
| 1.10 | 16 | 88.0% | 88.9% |
| 1.10.1 | 1 | 100.0% | 100.0% |
| 1.10.2 | 16 | 90.0% | 92.7% |
| 1.11 | 20 | 87.6% | 89.8% |
| 1.12 | 21 | 86.2% | 91.9% |
| 1.12.1 | 25 | 80.6% | 88.4% |
| 1.13 | 31 | 82.2% | 86.5% |
| 1.13.1 | 30 | 100.0% | 100.0% |
| 1.13.2 | 20 | 92.6% | 91.4% |
| 1.13.3 | 11 | 100.0% | 100.0% |
| 1.14 | 31 | 94.1% | 94.4% |
| 2.0 | 29 | 77.4% | 81.5% |
| 2.0.1 | 27 | 96.3% | 100.0% |
| 2.1 | 31 | 87.0% | 87.0% |
| 2.2 | 32 | 84.8% | 88.9% |
| 2.3 | 36 | 84.6% | 84.9% |
| 2.3.1 | 38 | 90.5% | 88.4% |
| 2.3.2 | 38 | 96.6% | 94.2% |
| 2.4 | 43 | 91.8% | 91.0% |
| 2.5 | 45 | 84.0% | 85.5% |
| 2.5.1 | 40 | 85.4% | 85.4% |
| 2.6 | 47 | 85.4% | 86.8% |
| 2.7 | 52 | 93.2% | 94.8% |
| 2.7.2 | 52 | 92.1% | 94.8% |
| 2.8 | 57 | 88.2% | 88.6% |
| 2.9 | 61 | 88.9% | 90.3% |
| 2.10 | 68 | 93.8% | 93.2% |
| 2.11 | 71 | 90.6% | 92.8% |
| 2.11.1 | 71 | 95.5% | 95.0% |
| 2.12 | 73 | 94.4% | 95.2% |
| 2.13 | 74 | 83.9% | 85.0% |
| 2.13.1 | 76 | 91.2% | 92.2% |
| 2.14.0 | 75 | 94.6% | 95.4% |
| 2.14.1 | 67 | 100.0% | 97.3% |
| 3.0.0 | 85 | 90.7% | 92.8% |
| 3.0.1 | 85 | 94.7% | 93.7% |
| 3.0.2 | 85 | 89.6% | 91.0% |
| 3.1.0 | 87 | 91.5% | 92.5% |
| 3.1.1 | 87 | 93.8% | 94.7% |
| 3.1.2 | 87 | 92.2% | 92.0% |
| 3.2.0 | 88 | 92.0% | 93.6% |
| 3.2.1 | 90 | 90.1% | 94.0% |
| 3.3.0 | 88 | 90.1% | 92.1% |
| 3.3.1 | 45 | 83.9% | 84.4% |
| 3.3.2 | 83 | 91.3% | 93.2% |
| 3.4.0 | 84 | 92.7% | 94.3% |
| 3.4.1 | 84 | 92.4% | 92.4% |
| 3.5.0 | 85 | 89.2% | 91.1% |
| 3.5.1 | 63 | 93.7% | 95.2% |
| 3.5.2 | 2 | 100.0% | 100.0% |
| 4.0.0 | 80 | 90.3% | 91.3% |
| 4.0.1 | 70 | 98.5% | 98.5% |
| 4.0.2 | 80 | 93.5% | 94.2% |
| 4.0.3 | 70 | 98.9% | 98.9% |
| 4.1.0 | 48 | 92.9% | 94.1% |

The few that went down did so by under three points, from the generic
changes: applying a CI change to every copy of a step, or skipping
boilerplate, is what most maintainers did, but not all.

### Where it still disagrees

What is left is mostly code and prose the pipeline owns:
`workflows/<name>.nf`, README.md, `docs/usage.md` and `docs/output.md`,
`nextflow.config` and the local utils subworkflow. Maintainers rewrote
the template's example workflow body and documentation, and decided case
by case which template text to take. Two other limits:

- **Multi-release PRs cascade.** A conflict in one release leaves a file
  behind, and later releases' changes to it no longer find their text.
- **Moved blocks.** When a release moves a block (2.0 moved `profiles`),
  finding the moved-to text reads as applied even if the pipeline still
  has an edited copy at the old place.

### Reproducing

```bash
# Clone every pipeline (full clones: blobs are read for each commit).
# names.txt: one name per line, from https://nf-co.re/pipelines.json.
mkdir -p pipelines
while read -r name; do
  git clone --quiet --no-single-branch "https://github.com/nf-core/$name.git" \
    "pipelines/$name"
done < names.txt

# Renders of every release (see the README), and the nf-core/tools CHANGELOG.
uv run python scripts/learn/collect.py pipelines > merges.jsonl
NF_MIGRATE_PIPELINES=pipelines uv run python scripts/learn/evaluate.py \
  merges.jsonl history src/nf_migrate/nf_core_migrations eval.jsonl
uv run python scripts/learn/scores.py eval.jsonl src/nf_migrate/nf_core_migrations
uv run python scripts/learn/worklist.py eval.jsonl --min 4
uv run python scripts/learn/report.py summary eval.jsonl --rev 3.0.0
NF_MIGRATE_PIPELINES=pipelines uv run python scripts/learn/triage.py \
  eval.jsonl merges.jsonl src/nf_migrate/nf_core_migrations 3.0.0 --min 4

# After editing an operation or a migration: the chain still has to turn
# each render into the next, and compare.py shows what got better or worse.
uv run python scripts/learn/check_renders.py history src/nf_migrate/nf_core_migrations
uv run python scripts/learn/compare.py eval-before.jsonl eval.jsonl
```

## Earlier evaluation: 11 pipelines, nf-migrate 0.2.0

How well does the bundled migration chain (nf-core/tools 3.3.1 → 4.1.0) do
on real pipelines, compared with the template merges their maintainers
resolved by hand? Figures are for nf-migrate 0.2.0.

### Method

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

### Pipelines

rnaseq, sarek, mag, taxprofiler, ampliseq, methylseq, fetchngs, scrnaseq,
differentialabundance, atacseq and chipseq: widely used pipelines with
template merges in the 3.3.1–4.1.0 range, evaluated on 2026-10-15.

### Results

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

### Where the conflicts are

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

### Version detection

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

### Pipelines older than nf-core/tools 3.0

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

### Skipped merges

Six merges fall outside the chain as it stood for this evaluation and were
not evaluated. The chain now starts at 1.9, but they have not been re-run:

- atacseq, chipseq, mag, scrnaseq: started from 3.2.1, before the chain's
  first version then, 3.3.1.
- fetchngs: started from 3.2.0.
- fetchngs: `dev` was already stamped 3.5.2 when a 3.5.1 `TEMPLATE` commit
  was merged, and nf-migrate only upgrades.

### Limits

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

### Reproducing

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
