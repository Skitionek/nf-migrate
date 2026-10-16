"""Template update for nf-core/tools 4.0.0.

nf-core/tools CHANGELOG, Template section of
[v4.0.0 - Bold Boa](https://github.com/nf-core/tools/releases/tag/4.0.0) - [2026-04-28]:

- Remove webhook notifications (hook_url, slackreport, adaptivecard) ([#4051](https://github.com/nf-core/tools/pull/4051)).
  - Use specific nextflow plugins instead:
    - [nf-slack](https://github.com/seqeralabs/nf-slack)
    - [nf-teams](https://github.com/nvnieuwk/nf-teams)
- Add `.lineage/` directory to the template .gitignore ([#4075](https://github.com/nf-core/tools/pull/4075)).
- Update nf-test module template to topics ([#4113](https://github.com/nf-core/tools/pull/4113))
- Fix nf-core tools version to what is specified in `.nf-core.yml` for the GitHub workflow `download_pipeline.yml` ([#4124](https://github.com/nf-core/tools/pull/4124)).
- Update all documentation URLs to point to equivalents on the new nf-core website documentation structure ([#4135](https://github.com/nf-core/tools/pull/4135))
- Trigger full nf-test run if scripts in bin/ or schema JSON files are modified ([#3897](https://github.com/nf-core/tools/pull/3897))
- Add additional fusion specific exit codes ([#4180](https://github.com/nf-core/tools/pull/4180))
- fix: rename variables in pipeline nf-test template default.nf.test for clarity ([#4189](https://github.com/nf-core/tools/pull/4189))
-
- bump nextflow to 25.10.4 ([#4190](https://github.com/nf-core/tools/pull/4190))
- fix jinja variable in template ([#4156](https://github.com/nf-core/tools/pull/4156))
- fix some nextflow lint warnings in different skipped template versions ([#4191](https://github.com/nf-core/tools/pull/4191))
- trigger full nf-test run if CI changes ([#4203](https://github.com/nf-core/tools/pull/4203))
- Include AI and LLM usage guidelines in CONTRIBUTING.md ([#4211](https://github.com/nf-core/tools/pull/4211))

#### Version updates

- Update GitHub Actions ([#4001](https://github.com/nf-core/tools/pull/4001))
- Update dependency prettier to v3.8.1 ([#4003](https://github.com/nf-core/tools/pull/4003))
- Update dawidd6/action-download-artifact action to v14 ([#4018](https://github.com/nf-core/tools/pull/4018))
- Update mcr.microsoft.com/devcontainers/miniconda Docker digest to b99720f ([#4022](https://github.com/nf-core/tools/pull/4022))
- Update apptainer setup action version ([#4036](https://github.com/nf-core/tools/pull/4036))
- Update pre-commit hook astral-sh/uv-pre-commit to v0.10.2 ([#4037](https://github.com/nf-core/tools/pull/4037))
- Update python:3.14-slim Docker digest to 486b809 ([#4039](https://github.com/nf-core/tools/pull/4039))
- Lock file maintenance ([#4044](https://github.com/nf-core/tools/pull/4044))
- Lock file maintenance ([#4045](https://github.com/nf-core/tools/pull/4045))
- Update actions/stale digest to b5d41d4 ([#4047](https://github.com/nf-core/tools/pull/4047))
- Update dawidd6/action-download-artifact action to v15 ([#4053](https://github.com/nf-core/tools/pull/4053))
- Lock file maintenance ([#4055](https://github.com/nf-core/tools/pull/4055))
- Update dawidd6/action-download-artifact action to v16 ([#4059](https://github.com/nf-core/tools/pull/4059))
- Update actions/upload-artifact action to v7 ([#4061](https://github.com/nf-core/tools/pull/4061))
- Update GitHub Actions ([#4067](https://github.com/nf-core/tools/pull/4067))
- Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.4 ([#4069](https://github.com/nf-core/tools/pull/4069))
- Update pre-commit hook astral-sh/uv-pre-commit to v0.10.7 ([#4070](https://github.com/nf-core/tools/pull/4070))
- Update python:3.14-slim Docker digest to 6a27522 ([#4072](https://github.com/nf-core/tools/pull/4072))
- Update dependency textual to v8 ([#4078](https://github.com/nf-core/tools/pull/4078))
- bump nf-test to 0.9.4 ([#4079](https://github.com/nf-core/tools/pull/4079))
- Update GitHub Actions to v4 (major) ([#4081](https://github.com/nf-core/tools/pull/4081))
- Pin dependencies ([#4090](https://github.com/nf-core/tools/pull/4090))
- Update GitHub Actions ([#4091](https://github.com/nf-core/tools/pull/4091))
- Update GitHub Actions ([#4137](https://github.com/nf-core/tools/pull/4137))
- Update codecov/codecov-action action to v6 ([#4138](https://github.com/nf-core/tools/pull/4138))
- Update astral-sh/setup-uv action to v8 ([#4148](https://github.com/nf-core/tools/pull/4148))
- Update GitHub Actions ([#4150](https://github.com/nf-core/tools/pull/4150))
- Update mcr.microsoft.com/devcontainers/base Docker tag to v2.1.7 ([#4151](https://github.com/nf-core/tools/pull/4151))
- Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.9 ([#4152](https://github.com/nf-core/tools/pull/4152))
- Update pre-commit hook astral-sh/uv-pre-commit to v0.11.2 ([#4153](https://github.com/nf-core/tools/pull/4153))
- Update mcr.microsoft.com/devcontainers/miniconda Docker digest to 26b252e ([#4158](https://github.com/nf-core/tools/pull/4158))
- chore(deps): update python:3.14-slim docker digest to 5e59aae ([#4159](https://github.com/nf-core/tools/pull/4159))
- Update dependency textual to v8.2.1 ([#4161](https://github.com/nf-core/tools/pull/4161))
- Update mshick/add-pr-comment digest to f102bb3 ([#4162](https://github.com/nf-core/tools/pull/4162))
- Update pre-commit hook pre-commit/mirrors-mypy to v1.20.0 ([#4165](https://github.com/nf-core/tools/pull/4165))
- Update nf-core/setup-nf-test action to v2 ([#4166](https://github.com/nf-core/tools/pull/4166))
- Update pre-commit hook astral-sh/uv-pre-commit to v0.11.3 ([#4169](https://github.com/nf-core/tools/pull/4169))
- Update GitHub Actions ([#4170](https://github.com/nf-core/tools/pull/4170))
- Update dawidd6/action-download-artifact action to v20 ([#4171](https://github.com/nf-core/tools/pull/4171))
- chore(deps): update pypa/gh-action-pypi-publish digest to cef2210 ([#4178](https://github.com/nf-core/tools/pull/4178))
- Update pre-commit hook astral-sh/uv-pre-commit to v0.11.4 ([#4179](https://github.com/nf-core/tools/pull/4179))
- Update actions/github-script action to v9 ([#4182](https://github.com/nf-core/tools/pull/4182))
- Update actions/upload-artifact digest to 043fb46 ([#4184](https://github.com/nf-core/tools/pull/4184))
- Update dependency prettier to v3.8.3 ([#4192](https://github.com/nf-core/tools/pull/4192))
- Update dependency textual to v8.2.3 ([#4194](https://github.com/nf-core/tools/pull/4194))
- Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.11 ([#4195](https://github.com/nf-core/tools/pull/4195))
- Lock file maintenance ([#4198](https://github.com/nf-core/tools/pull/4198))
- Update nf-core/setup-nextflow action to v3 ([#4199](https://github.com/nf-core/tools/pull/4199))
- Update python:3.14-slim Docker digest to bc389f7 ([#4200](https://github.com/nf-core/tools/pull/4200))
- Update astral-sh/setup-uv action to v8 ([#4207](https://github.com/nf-core/tools/pull/4207))
- Update conda-incubator/setup-miniconda action to v4 ([#4215](https://github.com/nf-core/tools/pull/4215))
- Update dependency textual to v8.2.4 ([#4217](https://github.com/nf-core/tools/pull/4217))
- Update mcr.microsoft.com/devcontainers/base Docker tag to v2.1.8 ([#4218](https://github.com/nf-core/tools/pull/4218))
- Update pre-commit hooks ([#4219](https://github.com/nf-core/tools/pull/4219))
- Update mcr.microsoft.com/devcontainers/miniconda Docker digest to 1a85cf3 ([#4220](https://github.com/nf-core/tools/pull/4220))
- Update python:3.14-slim Docker digest to 5b3879b ([#4221](https://github.com/nf-core/tools/pull/4221))
- Update GitHub Actions ([#4222](https://github.com/nf-core/tools/pull/4222))

Generated by nf-migrate; edit freely.
"""
# ruff: noqa: E501, F401, W291, W293

from nf_migrate.operations import (
    BumpVersion,
    CreateFile,
    DeleteFile,
    FirstOf,
    ManualStep,
    NfCoreComponent,
    RegexReplace,
    RemoveText,
    Replace,
    ReplaceFile,
)
from nf_migrate.yaml_edit import YamlListItem, YamlSet

revision = '4.0.0'
down_revision = '3.5.2'

operations = [
    Replace(
        '.devcontainer/devcontainer.json',
        old="""\
{
    "name": "nfcore",
""",
        new="""\
{
    "$schema": "https://raw.githubusercontent.com/devcontainers/spec/main/schemas/devContainer.schema.json",
    "name": "nfcore",
""",
        context_after="""\
    "image": "nfcore/devcontainer:latest",

""",
    ),
    DeleteFile(
        '.github/CONTRIBUTING.md',
        expected_content="""\
# `nf-core/{{pipeline_name}}`: Contributing Guidelines

Hi there!
Many thanks for taking an interest in improving nf-core/{{pipeline_name}}.

We try to manage the required tasks for nf-core/{{pipeline_name}} using GitHub issues, you probably came to this page when creating one.
Please use the pre-filled template to save time.

However, don't be put off by this template - other more general issues and suggestions are welcome!
Contributions to the code are even more welcome ;)

> [!NOTE]
> If you need help using or modifying nf-core/{{pipeline_name}} then the best place to ask is on the nf-core Slack [#{{pipeline_name}}](https://nfcore.slack.com/channels/{{pipeline_name}}) channel ([join our Slack here](https://nf-co.re/join/slack)).

## Contribution workflow

If you'd like to write some code for nf-core/{{pipeline_name}}, the standard workflow is as follows:

1. Check that there isn't already an issue about your idea in the [nf-core/{{pipeline_name}} issues](https://github.com/nf-core/{{pipeline_name}}/issues) to avoid duplicating work. If there isn't one already, please create one so that others know you're working on this
2. [Fork](https://help.github.com/en/github/getting-started-with-github/fork-a-repo) the [nf-core/{{pipeline_name}} repository](https://github.com/nf-core/{{pipeline_name}}) to your GitHub account
3. Make the necessary changes / additions within your forked repository following [Pipeline conventions](#pipeline-contribution-conventions)
4. Use `nf-core pipelines schema build` and add any new parameters to the pipeline JSON schema (requires [nf-core tools](https://github.com/nf-core/tools) >= 1.10).
5. Submit a Pull Request against the `dev` branch and wait for the code to be reviewed and merged

If you're not used to this workflow with git, you can start with some [docs from GitHub](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests) or even their [excellent `git` resources](https://try.github.io/).

## Tests

You have the option to test your changes locally by running the pipeline. For receiving warnings about process selectors and other `debug` information, it is recommended to use the debug profile. Execute all the tests with the following command:

```bash
nf-test test --profile debug,test,docker --verbose
```

When you create a pull request with changes, [GitHub Actions](https://github.com/features/actions) will run automatic tests.
Typically, pull-requests are only fully reviewed when these tests are passing, though of course we can help out before then.

There are typically two types of tests that run:

### Lint tests

`nf-core` has a [set of guidelines](https://nf-co.re/developers/guidelines) which all pipelines must adhere to.
To enforce these and ensure that all pipelines stay in sync, we have developed a helper tool which runs checks on the pipeline code. This is in the [nf-core/tools repository](https://github.com/nf-core/tools) and once installed can be run locally with the `nf-core pipelines lint <pipeline-directory>` command.

If any failures or warnings are encountered, please follow the listed URL for more documentation.

### Pipeline tests

Each `nf-core` pipeline should be set up with a minimal set of test-data.
`GitHub Actions` then runs the pipeline on this data to ensure that it exits successfully.
If there are any failures then the automated tests fail.
These tests are run both with the latest available version of `Nextflow` and also the minimum required version that is stated in the pipeline code.

## Patch

:warning: Only in the unlikely and regretful event of a release happening with a bug.

- On your own fork, make a new branch `patch` based on `upstream/main` or `upstream/master`.
- Fix the bug, and bump version (X.Y.Z+1).
- Open a pull-request from `patch` to `main`/`master` with the changes.

## Getting help

For further information/help, please consult the [nf-core/{{pipeline_name}} documentation](https://nf-co.re/{{pipeline_name}}/usage) and don't hesitate to get in touch on the nf-core Slack [#{{pipeline_name}}](https://nfcore.slack.com/channels/{{pipeline_name}}) channel ([join our Slack here](https://nf-co.re/join/slack)).

## Pipeline contribution conventions

To make the `nf-core/{{pipeline_name}}` code and processing logic more understandable for new contributors and to ensure quality, we semi-standardise the way the code and other contributions are written.

### Adding a new step

If you wish to contribute a new step, please use the following coding standards:

1. Define the corresponding input channel into your new process from the expected previous process channel.
2. Write the process block (see below).
3. Define the output channel if needed (see below).
4. Add any new parameters to `nextflow.config` with a default (see below).
5. Add any new parameters to `nextflow_schema.json` with help text (via the `nf-core pipelines schema build` tool).
6. Add sanity checks and validation for all relevant parameters.
7. Perform local tests to validate that the new code works as expected.
8. If applicable, add a new test in the `tests` directory.
9. Update MultiQC config `assets/multiqc_config.yml` so relevant suffixes, file name clean up and module plots are in the appropriate order. If applicable, add a [MultiQC](https://https://multiqc.info/) module.
10. Add a description of the output files and if relevant any appropriate images from the MultiQC report to `docs/output.md`.

### Default values

Parameters should be initialised / defined with default values within the `params` scope in `nextflow.config`.

Once there, use `nf-core pipelines schema build` to add to `nextflow_schema.json`.

### Default processes resource requirements

Sensible defaults for process resource requirements (CPUs / memory / time) for a process should be defined in `conf/base.config`. These should generally be specified generic with `withLabel:` selectors so they can be shared across multiple processes/steps of the pipeline. A nf-core standard set of labels that should be followed where possible can be seen in the [nf-core pipeline template](https://github.com/nf-core/tools/blob/main/nf_core/pipeline-template/conf/base.config), which has the default process as a single core-process, and then different levels of multi-core configurations for increasingly large memory requirements defined with standardised labels.

The process resources can be passed on to the tool dynamically within the process with the `${task.cpus}` and `${task.memory}` variables in the `script:` block.

### Naming schemes

Please use the following naming schemes, to make it easy to understand what is going where.

- initial process channel: `ch_output_from_<process>`
- intermediate and terminal channels: `ch_<previousprocess>_for_<nextprocess>`

### Nextflow version bumping

If you are using a new feature from core Nextflow, you may bump the minimum required version of nextflow in the pipeline with: `nf-core pipelines bump-version --nextflow . [min-nf-version]`

### Images and figures

For overview images and other documents we follow the nf-core [style guidelines and examples](https://nf-co.re/developers/design_guidelines).

## GitHub Codespaces

This repo includes a devcontainer configuration which will create a GitHub Codespaces for Nextflow development! This is an online developer environment that runs in your browser, complete with VSCode and a terminal.

To get started:

- Open the repo in [Codespaces](https://github.com/nf-core/{{pipeline_name}}/codespaces)
- Tools installed
  - nf-core
  - Nextflow

Devcontainer specs:

- [DevContainer config](.devcontainer/devcontainer.json)
""",
    ),
    Replace(
        '.github/PULL_REQUEST_TEMPLATE.md',
        old="""\
Learn more about contributing: [CONTRIBUTING.md](https://github.com/nf-core/{{pipeline_name}}/tree/master/.github/CONTRIBUTING.md)
""",
        new="""\
Learn more about contributing: [CONTRIBUTING.md](https://github.com/nf-core/{{pipeline_name}}/tree/master/docs/CONTRIBUTING.md)
""",
        context_before="""\
Remember that PRs should be made against the dev branch, unless you're preparing a pipeline release.

""",
        context_after="""\
-->

""",
        every=True,
    ),
    Replace(
        '.github/PULL_REQUEST_TEMPLATE.md',
        old="""\
- [ ] If you've added a new tool - have you followed the pipeline conventions in the [contribution docs](https://github.com/nf-core/{{pipeline_name}}/tree/master/.github/CONTRIBUTING.md)
""",
        new="""\
- [ ] If you've added a new tool - have you followed the pipeline conventions in the [contribution docs](https://github.com/nf-core/{{pipeline_name}}/tree/master/docs/CONTRIBUTING.md)
""",
        context_before="""\
- [ ] This comment contains a description of changes (with reason).
- [ ] If you've fixed a bug or added code that should be tested, add tests!
""",
        context_after="""\
- [ ] If necessary, also make a PR on the nf-core/{{pipeline_name}} _branch_ on the [nf-core/test-datasets](https://github.com/nf-core/test-datasets) repository.
- [ ] Make sure your code lints (`nf-core pipelines lint`).
""",
        every=True,
    ),
    Replace(
        '.github/actions/get-shards/action.yml',
        old="""\
      uses: nf-core/setup-nf-test@v1
""",
        new="""\
      uses: nf-core/setup-nf-test@4069fbbaabe94c08faba4ad261bfa88225ba133f # v2
""",
        context_before="""\
  steps:
    - name: Install nf-test
""",
        context_after="""\
      with:
        version: ${{ env.NFT_VER }}
""",
        every=True,
    ),
    Replace(
        '.github/actions/nf-test/action.yml',
        old="""\
      uses: nf-core/setup-nextflow@v2
""",
        new="""\
      uses: nf-core/setup-nextflow@b4ec1bc7c16a94435159de94a05253542fddf6ef # v3
""",
        context_before="""\
  steps:
    - name: Setup Nextflow
""",
        context_after="""\
      with:
        version: "${{ env.NXF_VERSION }}"
""",
        every=True,
    ),
    YamlSet(
        '.github/actions/nf-test/action.yml',
        key=['runs', 'steps', {'name': ['Set up Python'], 'uses': ['actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c', 'actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405'], '#': 1}, 'uses'],
        value='actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405',
        old='actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c',
    ),
    Replace(
        '.github/actions/nf-test/action.yml',
        old="""\
      uses: nf-core/setup-nf-test@v1
""",
        new="""\
      uses: nf-core/setup-nf-test@4069fbbaabe94c08faba4ad261bfa88225ba133f # v2
""",
        context_before="""\

    - name: Install nf-test
""",
        context_after="""\
      with:
        version: "${{ env.NFT_VER }}"
""",
        every=True,
    ),
    Replace(
        '.github/actions/nf-test/action.yml',
        old="""\
      uses: eWaterCycle/setup-apptainer@main
""",
        new="""\
      uses: eWaterCycle/setup-apptainer@3f706d898c9db585b1d741b4692e66755f3a1b40 # v2
""",
        context_before="""\
    - name: Setup apptainer
      if: contains(inputs.profile, 'singularity')
""",
        context_after="""\

    - name: Set up Singularity
""",
        every=True,
    ),
    FirstOf(
        '.github/actions/nf-test/action.yml',
        operations=(
    Replace(
        '.github/actions/nf-test/action.yml',
        old="""\
      uses: conda-incubator/setup-miniconda@505e6394dae86d6a5c7fbb6e3fb8938e3e863830 # v3
""",
        new="""\
      uses: conda-incubator/setup-miniconda@8ee1f361103df19b6f8c8655fd3967a8ecb162d5 # v4
""",
        context_before="""\
    - name: Conda setup
      if: contains(inputs.profile, 'conda')
""",
        context_after="""\
      with:
        auto-update-conda: true
""",
        every=True,
    ),
    RegexReplace(
        '.github/actions/nf-test/action.yml',
        pattern='505e6394dae86d6a5c7fbb6e3fb8938e3e863830 # v3',
        replacement='8ee1f361103df19b6f8c8655fd3967a8ecb162d5 # v4',
        applied='8ee1f361103df19b6f8c8655fd3967a8ecb162d5 # v4',
    ),
        ),
    ),
    Replace(
        '.github/workflows/awsfulltest.yml',
        old="""\
        uses: seqeralabs/action-tower-launch@v2
""",
        new="""\
        uses: seqeralabs/action-tower-launch@51565b514bff1827cf34620de25d0055759f1fc9 # v2
""",
        context_before="""\

      - name: Launch workflow via Seqera Platform
""",
        context_after="""\
        # TODO nf-core: You can customise AWS full pipeline tests as required
        # Add full size test data (but still relatively small datasets for few samples)
""",
        every=True,
    ),
    Replace(
        '.github/workflows/awsfulltest.yml',
        old="""\
          workdir: s3://${{ vars.AWS_S3_BUCKET }}/work/{{pipeline_name}}/work-${{ steps.revision.outputs.revision }}
          parameters: |
""",
        new="""\
          workdir: s3://${{ vars.AWS_S3_BUCKET }}/work/{{pipeline_name}}/work-${{ steps.revision.outputs.revision }}
          nextflow_config: |
            plugins {
              id 'nf-slack@0.5.0'
            }
            slack {
              enabled = true
              bot {
                token = '${{ secrets.NFSLACK_BOT_TOKEN }}'
                channel = '{{pipeline_name}}'
              }
              onStart {
                enabled = false
              }
              onComplete {
                message = ':white_check_mark: *{{pipeline_name}}/test_full* completed successfully! :tada:'
              }
              onError {
                message = ':x: *{{pipeline_name}}/test_full* failed :crying_cat_face:'
              }
            }
          parameters: |
""",
        context_before="""\
          compute_env: ${{ vars.TOWER_COMPUTE_ENV }}
          revision: ${{ steps.revision.outputs.revision }}
""",
        context_after="""\
            {
              "hook_url": "${{ secrets.MEGATESTS_ALERTS_SLACK_HOOK_URL }}",
""",
    ),
    RemoveText(
        '.github/workflows/awsfulltest.yml',
        text="""\
              "hook_url": "${{ secrets.MEGATESTS_ALERTS_SLACK_HOOK_URL }}",
""",
    ),
    FirstOf(
        '.github/workflows/awsfulltest.yml',
        operations=(
    Replace(
        '.github/workflows/awsfulltest.yml',
        old="""\
      - uses: actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4 # v5
""",
        new="""\
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
""",
        context_before="""\
          profiles: test_full

""",
        context_after="""\
        with:
          name: Seqera Platform debug log file
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/awsfulltest.yml',
        pattern='330a01c490aca151604b8cf639adc76d48f6c5d4 # v5',
        replacement='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
        applied='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
    ),
        ),
    ),
    Replace(
        '.github/workflows/awstest.yml',
        old="""\
        uses: seqeralabs/action-tower-launch@v2
""",
        new="""\
        uses: seqeralabs/action-tower-launch@51565b514bff1827cf34620de25d0055759f1fc9 # v2
""",
        context_before="""\
      # Launch workflow using Seqera Platform CLI tool action
      - name: Launch workflow via Seqera Platform
""",
        context_after="""\
        with:
          workspace_id: ${{ vars.TOWER_WORKSPACE_ID }}
""",
        every=True,
    ),
    FirstOf(
        '.github/workflows/awstest.yml',
        operations=(
    Replace(
        '.github/workflows/awstest.yml',
        old="""\
      - uses: actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4 # v5
""",
        new="""\
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
""",
        context_before="""\
          profiles: test

""",
        context_after="""\
        with:
          name: Seqera Platform debug log file
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/awstest.yml',
        pattern='330a01c490aca151604b8cf639adc76d48f6c5d4 # v5',
        replacement='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
        applied='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/branch.yml',
        operations=(
    Replace(
        '.github/workflows/branch.yml',
        old="""\
        uses: mshick/add-pr-comment@b8f338c590a895d50bcbfa6c5859251edc8952fc # v2
""",
        new="""\
        uses: mshick/add-pr-comment@8e4927817251f1ff60c001f04568532b38e0b4a0 # v3
""",
        context_before="""\
      - name: Post PR comment
        if: failure()
""",
        context_after="""\
        with:
          message: |
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/branch.yml',
        pattern='b8f338c590a895d50bcbfa6c5859251edc8952fc # v2',
        replacement='8e4927817251f1ff60c001f04568532b38e0b4a0 # v3',
        applied='8e4927817251f1ff60c001f04568532b38e0b4a0 # v3',
    ),
        ),
    ),
    YamlSet(
        '.github/workflows/clean-up.yml',
        key=['jobs', 'clean-up', 'steps', {'uses': ['actions/stale@5f858e3efba33a5ca4407a664cc011ad407f2008', 'actions/stale@b5d41d4e1d5dceea10e7104786b73624c18a190f'], '#': 0}, 'uses'],
        value='actions/stale@b5d41d4e1d5dceea10e7104786b73624c18a190f',
        old='actions/stale@5f858e3efba33a5ca4407a664cc011ad407f2008',
    ),
    Replace(
        '.github/workflows/download_pipeline.yml',
        old="""\
        uses: nf-core/setup-nextflow@v2
""",
        new="""\
        uses: nf-core/setup-nextflow@b4ec1bc7c16a94435159de94a05253542fddf6ef # v3
""",
        context_before="""\
    steps:
      - name: Install Nextflow
""",
        context_after="""\

      - name: Disk space cleanup
""",
        every=True,
    ),
    YamlSet(
        '.github/workflows/download_pipeline.yml',
        key=['jobs', 'download', 'steps', {'uses': ['actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c', 'actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405'], '#': 2}, 'uses'],
        value='actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405',
        old='actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c',
    ),
    YamlListItem(
        '.github/workflows/download_pipeline.yml',
        key=['jobs', 'download', 'steps'],
        item="""\
      - name: Read .nf-core.yml
        uses: pietrobolcato/action-read-yaml@9f13718d61111b69f30ab4ac683e67a56d254e1d # 1.1.0
        id: read_yml
        with:
          config: ${{ github.workspace }}/.nf-core.yml

""",
        match={'id': ['read_yml'], 'name': ['Read .nf-core.yml'], 'uses': ['pietrobolcato/action-read-yaml@9f13718d61111b69f30ab4ac683e67a56d254e1d']},
        after={'name': ['Setup Apptainer'], 'uses': ['eWaterCycle/setup-apptainer@4bb22c52d4f63406c49e94c804632975787312b3'], '#': 3},
    ),
    FirstOf(
        '.github/workflows/download_pipeline.yml',
        operations=(
    Replace(
        '.github/workflows/download_pipeline.yml',
        old="""\
          pip install git+https://github.com/nf-core/tools.git
""",
        new="""\
          pip install nf-core==${{ steps.read_yml.outputs['nf_core_version'] }}
""",
        context_before="""\
        run: |
          python -m pip install --upgrade pip
""",
        context_after="""\

      - name: Make a cache directory for the container images
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/download_pipeline.yml',
        pattern='git\\+https://github\\.com/nf-core/tools\\.git',
        replacement="nf-core==${{ steps.read_yml.outputs['nf_core_version'] }}",
        applied="nf-core==\\${{ steps\\.read_yml\\.outputs\\['nf_core_version'\\] }}",
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/download_pipeline.yml',
        operations=(
    Replace(
        '.github/workflows/download_pipeline.yml',
        old="""\
        uses: actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4 # v5
""",
        new="""\
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
""",
        context_before="""\

      - name: Upload Nextflow logfile for debugging purposes
""",
        context_after="""\
        with:
          name: nextflow_logfile.txt
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/download_pipeline.yml',
        pattern='330a01c490aca151604b8cf639adc76d48f6c5d4 # v5',
        replacement='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
        applied='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/fix_linting.yml',
        operations=(
    Replace(
        '.github/workflows/fix_linting.yml',
        old="""\
      - uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5
""",
        new="""\
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
""",
        context_before="""\
    steps:
      # Use the @nf-core-bot token to check out so we can push later
""",
        context_after="""\
        with:
          token: ${{ secrets.nf_core_bot_auth_token }}
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/fix_linting.yml',
        pattern='93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5',
        replacement='de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6',
        applied='de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6',
    ),
        ),
    ),
    Replace(
        '.github/workflows/fix_linting.yml',
        old="""\
      # Install and run pre-commit
      - uses: actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c # v6
        with:
          python-version: "3.14"
""",
        new="""\
      - name: Install Nextflow
        uses: nf-core/setup-nextflow@b4ec1bc7c16a94435159de94a05253542fddf6ef # v3
""",
        context_before="""\
          GITHUB_TOKEN: ${{ secrets.nf_core_bot_auth_token }}

""",
        context_after="""\

      - name: Install pre-commit
""",
        every=True,
    ),
    Replace(
        '.github/workflows/fix_linting.yml',
        old="""\
      - name: Install pre-commit
        run: pip install pre-commit

      - name: Run pre-commit
        id: pre-commit
        run: pre-commit run --all-files
""",
        new="""\
      # Install and run prek
      - name: Run prek
        id: prek
        uses: j178/prek-action@cbc2f23eb5539cf20d82d1aabd0d0ecbcc56f4e3 # v2
""",
        context_before="""\
          python-version: "3.14"

""",
        context_after="""\
        continue-on-error: true

""",
        every=True,
    ),
    YamlSet(
        '.github/workflows/fix_linting.yml',
        key=['jobs', 'fix-linting', 'steps', {'name': ['react if linting finished succesfully'], 'uses': ['peter-evans/create-or-update-comment@e8674b075228eee787fea43ef493e45ece1004c9'], '#': 5}, 'if'],
        value="steps.prek.outcome == 'success'",
        old="steps.pre-commit.outcome == 'success'",
    ),
    YamlSet(
        '.github/workflows/fix_linting.yml',
        key=['jobs', 'fix-linting', 'steps', {'id': ['commit-and-push'], 'name': ['Commit & push changes'], '#': 6}, 'if'],
        value="steps.prek.outcome == 'failure'",
        old="steps.pre-commit.outcome == 'failure'",
    ),
    Replace(
        '.github/workflows/linting.yml',
        old="""\
      - uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5
""",
        new="""\
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
""",
        context_before="""\
    runs-on: ubuntu-latest
    steps:
""",
        context_after="""\

      - name: Set up Python 3.14
""",
        every=True,
    ),
    Replace(
        '.github/workflows/linting.yml',
        old="""\
      - name: Set up Python 3.14
        uses: actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c # v6
        with:
          python-version: "3.14"

      - name: Install pre-commit
        run: pip install pre-commit

      - name: Run pre-commit
        run: pre-commit run --all-files
""",
        new="""\
      - name: Install Nextflow
        uses: nf-core/setup-nextflow@b4ec1bc7c16a94435159de94a05253542fddf6ef # v3

      - name: Run prek
        uses: j178/prek-action@cbc2f23eb5539cf20d82d1aabd0d0ecbcc56f4e3 # v2
""",
        context_before="""\
      - uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5

""",
        context_after="""\

  nf-core:
""",
        every=True,
    ),
    Replace(
        '.github/workflows/linting.yml',
        old="""\
        uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5
""",
        new="""\
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
""",
        context_before="""\
    steps:
      - name: Check out pipeline code
""",
        context_after="""\

      - name: Install Nextflow
""",
        every=True,
    ),
    Replace(
        '.github/workflows/linting.yml',
        old="""\
        uses: nf-core/setup-nextflow@v2

      - uses: actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c # v6
""",
        new="""\
        uses: nf-core/setup-nextflow@b4ec1bc7c16a94435159de94a05253542fddf6ef # v3

      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6
""",
        context_before="""\

      - name: Install Nextflow
""",
        context_after="""\
        with:
          python-version: "3.14"
""",
        every=True,
    ),
    YamlListItem(
        '.github/workflows/linting.yml',
        key=['jobs', 'nf-core', 'steps'],
        item="""\
      - name: Setup uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0

""",
        match={'name': ['Setup uv'], 'uses': ['astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b']},
        after={'uses': ['actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405'], '#': 2},
    ),
    Replace(
        '.github/workflows/linting.yml',
        old="""\
        run: |
          python -m pip install --upgrade pip
          pip install nf-core==${{ steps.read_yml.outputs['nf_core_version'] }}
""",
        new="""\
        run: uv tool install nf-core==${{ steps.read_yml.outputs['nf_core_version'] }}
""",
        context_before="""\

      - name: Install dependencies
""",
        context_after="""\

      - name: Run nf-core pipelines lint
""",
        every=True,
    ),
    YamlSet(
        '.github/workflows/linting.yml',
        key=['jobs', 'nf-core', 'steps', {'name': ['Run nf-core pipelines lint'], '#': 6}, 'if'],
        value="${{ github.base_ref != 'master' || github.base_ref != 'main' }}",
        old="${{ github.base_ref != 'master' }}",
    ),
    YamlSet(
        '.github/workflows/linting.yml',
        key=['jobs', 'nf-core', 'steps', {'name': ['Run nf-core pipelines lint --release'], '#': 7}, 'if'],
        value="${{ github.base_ref == 'master' || github.base_ref == 'main' }}",
        old="${{ github.base_ref == 'master' }}",
    ),
    FirstOf(
        '.github/workflows/linting.yml',
        operations=(
    Replace(
        '.github/workflows/linting.yml',
        old="""\
        uses: actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4 # v5
""",
        new="""\
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
""",
        context_before="""\
      - name: Upload linting log file artifact
        if: ${{ always() }}
""",
        context_after="""\
        with:
          name: linting-logs
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/linting.yml',
        pattern='330a01c490aca151604b8cf639adc76d48f6c5d4 # v5',
        replacement='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
        applied='043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7',
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/linting_comment.yml',
        operations=(
    Replace(
        '.github/workflows/linting_comment.yml',
        old="""\
        uses: dawidd6/action-download-artifact@ac66b43f0e6a346234dd65d4d0c8fbb31cb316e5 # v11
""",
        new="""\
        uses: dawidd6/action-download-artifact@8305c0f1062bb0d184d09ef4493ecb9288447732 # v20
""",
        context_before="""\
    steps:
      - name: Download lint results
""",
        context_after="""\
        with:
          workflow: linting.yml
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/linting_comment.yml',
        pattern='ac66b43f0e6a346234dd65d4d0c8fbb31cb316e5 # v11',
        replacement='8305c0f1062bb0d184d09ef4493ecb9288447732 # v20',
        applied='8305c0f1062bb0d184d09ef4493ecb9288447732 # v20',
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/linting_comment.yml',
        operations=(
    Replace(
        '.github/workflows/linting_comment.yml',
        old="""\
        uses: marocchino/sticky-pull-request-comment@773744901bac0e8cbb5a0dc842800d45e9b2b405 # v2
""",
        new="""\
        uses: marocchino/sticky-pull-request-comment@70d2764d1a7d5d9560b100cbea0077fc8f633987 # v3
""",
        context_before="""\

      - name: Post PR comment
""",
        context_after="""\
        with:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/linting_comment.yml',
        pattern='773744901bac0e8cbb5a0dc842800d45e9b2b405 # v2',
        replacement='70d2764d1a7d5d9560b100cbea0077fc8f633987 # v3',
        applied='70d2764d1a7d5d9560b100cbea0077fc8f633987 # v3',
    ),
        ),
    ),
    YamlSet(
        '.github/workflows/nf-test.yml',
        key=['env', 'NFT_VER'],
        value='"0.9.4"',
        old='"0.9.3"',
    ),
    Replace(
        '.github/workflows/nf-test.yml',
        old="""\
          ls -la ./
      - uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5
        with:
""",
        new="""\
          ls -la ./
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
""",
        context_before="""\
          rm -rf ./* || true
          rm -rf ./.??* || true
""",
        context_after="""\
          fetch-depth: 0

""",
    ),
    YamlSet(
        '.github/workflows/nf-test.yml',
        key=['jobs', 'nf-test', 'strategy', 'matrix', 'NXF_VER', 0],
        value='"25.10.4"',
        old='"25.04.0"',
    ),
    Replace(
        '.github/workflows/nf-test.yml',
        old="""\
    steps:
      - uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5
        with:
""",
        new="""\
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
        with:
""",
        context_before="""\
      TOTAL_SHARDS: ${{ needs.nf-test-changes.outputs.total_shards }}

""",
        context_after="""\
          fetch-depth: 0

""",
    ),
    Replace(
        '.github/workflows/release-announcements.yml',
        old="""\
      - uses: rzr/fediverse-action@master
""",
        new="""\
      - uses: rzr/fediverse-action@563159eb8d45f70ab6aaba36ed55cd037e51f441 # master
""",
        context_before="""\
        run: |
          echo "description=$(curl -s https://nf-co.re/pipelines.json | jq -r '.remote_workflows[] | select(.full_name == "${{ github.repository }}") | .description')" >> $GITHUB_OUTPUT
""",
        context_after="""\
        with:
          access-token: ${{ secrets.MASTODON_ACCESS_TOKEN }}
""",
        every=True,
    ),
    FirstOf(
        '.github/workflows/release-announcements.yml',
        operations=(
    Replace(
        '.github/workflows/release-announcements.yml',
        old="""\
      - uses: zentered/bluesky-post-action@6461056ea355ea43b977e149f7bf76aaa572e5e8 # v0.3.0
""",
        new="""\
      - uses: zentered/bluesky-post-action@5a91cc2ad10a304a4e96c16182dbe4918710bcf6 # v0.4.0
""",
        context_before="""\
    runs-on: ubuntu-latest
    steps:
""",
        context_after="""\
        with:
          post: |
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/release-announcements.yml',
        pattern='6461056ea355ea43b977e149f7bf76aaa572e5e8 # v0\\.3',
        replacement='5a91cc2ad10a304a4e96c16182dbe4918710bcf6 # v0.4',
        applied='5a91cc2ad10a304a4e96c16182dbe4918710bcf6 # v0\\.4',
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/template-version-comment.yml',
        operations=(
    Replace(
        '.github/workflows/template-version-comment.yml',
        old="""\
        uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5
""",
        new="""\
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6
""",
        context_before="""\
    steps:
      - name: Check out pipeline code
""",
        context_after="""\
        with:
          ref: ${{ github.event.pull_request.head.sha }}
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/template-version-comment.yml',
        pattern='93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5',
        replacement='de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6',
        applied='de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6',
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/template-version-comment.yml',
        operations=(
    Replace(
        '.github/workflows/template-version-comment.yml',
        old="""\
        uses: mshick/add-pr-comment@b8f338c590a895d50bcbfa6c5859251edc8952fc # v2
""",
        new="""\
        uses: mshick/add-pr-comment@8e4927817251f1ff60c001f04568532b38e0b4a0 # v3
""",
        context_before="""\

      - name: Post nf-core template version comment
""",
        context_after="""\
        if: |
          contains(env.OUTPUT, 'nf-core')
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/template-version-comment.yml',
        pattern='b8f338c590a895d50bcbfa6c5859251edc8952fc # v2',
        replacement='8e4927817251f1ff60c001f04568532b38e0b4a0 # v3',
        applied='8e4927817251f1ff60c001f04568532b38e0b4a0 # v3',
    ),
        ),
    ),
    FirstOf(
        '.github/workflows/template-version-comment.yml',
        operations=(
    Replace(
        '.github/workflows/template-version-comment.yml',
        old="""\
            > For more documentation on how to update your pipeline, please see the [nf-core documentation](https://github.com/nf-core/tools?tab=readme-ov-file#sync-a-pipeline-with-the-template) and [Synchronisation documentation](https://nf-co.re/docs/contributing/sync).
""",
        new="""\
            > For more documentation on how to update your pipeline, please see the [Synchronisation documentation](https://nf-co.re/docs/developing/template-syncs/overview).
""",
        context_before="""\
            > Please update your pipeline to the latest version.
            >
""",
        context_after="""\
          #
""",
        every=True,
    ),
    RegexReplace(
        '.github/workflows/template-version-comment.yml',
        pattern='nf-core documentation\\]\\(https://github\\.com/nf-core/tools\\?tab=readme-ov-file#sync-a-pipeline-with-the-template\\) and \\[Synchronisation documentation\\]\\(https://nf-co\\.re/docs/contributing/sync',
        replacement='Synchronisation documentation](https://nf-co.re/docs/developing/template-syncs/overview',
        applied='Synchronisation documentation\\]\\(https://nf-co\\.re/docs/developing/template-syncs/overview',
    ),
        ),
    ),
    Replace(
        '.gitignore',
        old="""\
null/
""",
        new="""\
null/
.lineage/
""",
        context_before="""\
testing*
*.pyc
""",
    ),
    YamlSet(
        '.pre-commit-config.yaml',
        key=['repos', {'#': 0}, 'hooks', {'id': ['prettier'], '#': 0}, 'additional_dependencies', 0],
        value='prettier@3.8.3',
        old='prettier@3.6.2',
    ),
    Replace(
        '.pre-commit-config.yaml',
        old='        exclude: |\n          (?x)^(\n              .*ro-crate-metadata.json$|\n              modules/nf-core/.*|\n              subworkflows/nf-core/.*|\n              .*\\.snap$\n          )$\n      - id: end-of-file-fixer\n',
        new='        exclude: |\n          (?x)^(\n              .*ro-crate-metadata.json$|\n              modules/(?!local/).*|\n              subworkflows/(?!local/).*|\n              .*\\.snap$\n          )$\n      - id: end-of-file-fixer\n',
        context_before="""\
      - id: trailing-whitespace
        args: [--markdown-linebreak-ext=md]
""",
        context_after="""\
        exclude: |
          (?x)^(
""",
    ),
    Replace(
        '.pre-commit-config.yaml',
        old='              .*ro-crate-metadata.json$|\n              modules/nf-core/.*|\n              subworkflows/nf-core/.*|\n              .*\\.snap$\n          )$\n',
        new='              .*ro-crate-metadata.json$|\n              modules/(?!local/).*|\n              subworkflows/(?!local/).*|\n              .*\\.snap$\n          )$\n  - repo: https://github.com/seqeralabs/nf-lint-pre-commit\n    rev: v0.3.0\n    hooks:\n      - id: nextflow-lint\n        files: \'\\.nf$|nextflow\\.config$\'\n        args: ["-output", "json"]\n',
        context_before="""\
        exclude: |
          (?x)^(
""",
    ),
    RemoveText(
        '.prettierignore',
        text="""\
adaptivecard.json
slackreport.json
""",
    ),
    Replace(
        'README.md',
        old="""\
[![Nextflow](https://img.shields.io/badge/version-%E2%89%A525.04.0-green?style=flat&logo=nextflow&logoColor=white&color=%230DC09D&link=https%3A%2F%2Fnextflow.io)](https://www.nextflow.io/)
[![nf-core template version](https://img.shields.io/badge/nf--core_template-3.5.2-green?style=flat&logo=nfcore&logoColor=white&color=%2324B064&link=https%3A%2F%2Fnf-co.re)](https://github.com/nf-core/tools/releases/tag/3.5.2)
""",
        new="""\
[![Nextflow](https://img.shields.io/badge/version-%E2%89%A525.10.4-green?style=flat&logo=nextflow&logoColor=white&color=%230DC09D&link=https%3A%2F%2Fnextflow.io)](https://www.nextflow.io/)
[![nf-core template version](https://img.shields.io/badge/nf--core_template-4.0.0-green?style=flat&logo=nfcore&logoColor=white&color=%2324B064&link=https%3A%2F%2Fnf-co.re)](https://github.com/nf-core/tools/releases/tag/4.0.0)
""",
        context_before="""\
[![nf-test](https://img.shields.io/badge/unit_tests-nf--test-337ab7.svg)](https://www.nf-test.com)

""",
        context_after="""\
[![run with conda](http://img.shields.io/badge/run%20with-conda-3EB049?labelColor=000000&logo=anaconda)](https://docs.conda.io/en/latest/)
[![run with docker](https://img.shields.io/badge/run%20with-docker-0db7ed?labelColor=000000&logo=docker)](https://www.docker.com/)
""",
    ),
    FirstOf(
        'README.md',
        operations=(
    Replace(
        'README.md',
        old="""\
     workflows use the "tube map" design for that. See https://nf-co.re/docs/guidelines/graphic_design/workflow_diagrams#examples for examples.   -->
""",
        new="""\
     workflows use the "tube map" design for that. See https://nf-co.re/docs/community/brand/workflow-schematics#examples for examples.   -->
""",
        context_before="""\

<!-- TODO nf-core: Include a figure that guides the user through the major workflow steps. Many nf-core
""",
        context_after="""\
<!-- TODO nf-core: Fill in short bullet-pointed list of the default steps in the pipeline -->1. Read QC ([`FastQC`](https://www.bioinformatics.babraham.ac.uk/projects/fastqc/))2. Present QC for raw reads ([`MultiQC`](http://multiqc.info/))

""",
    ),
    RegexReplace(
        'README.md',
        pattern='guidelines/graphic_design/workflow_diagrams',
        replacement='community/brand/workflow-schematics',
        applied='community/brand/workflow-schematics',
    ),
        ),
    ),
    FirstOf(
        'README.md',
        operations=(
    Replace(
        'README.md',
        old="""\
> If you are new to Nextflow and nf-core, please refer to [this page](https://nf-co.re/docs/usage/installation) on how to set-up Nextflow. Make sure to [test your setup](https://nf-co.re/docs/usage/introduction#how-to-run-a-pipeline) with `-profile test` before running the workflow on actual data.
""",
        new="""\
> If you are new to Nextflow and nf-core, please refer to [this page](https://nf-co.re/docs/get_started/environment_setup/overview) on how to set-up Nextflow. Make sure to [test your setup](https://nf-co.re/docs/get_started/run-your-first-pipeline) with `-profile test` before running the workflow on actual data.
""",
        context_before="""\

> [!NOTE]
""",
        context_after="""\

<!-- TODO nf-core: Describe the minimum required steps to execute the pipeline, e.g. how to prepare samplesheets.
""",
    ),
    RegexReplace(
        'README.md',
        pattern='usage/installation\\) on how to set-up Nextflow\\. Make sure to \\[test your setup\\]\\(https://nf-co\\.re/docs/usage/introduction#how-to-run-a',
        replacement='get_started/environment_setup/overview) on how to set-up Nextflow. Make sure to [test your setup](https://nf-co.re/docs/get_started/run-your-first',
        applied='get_started/environment_setup/overview\\) on how to set-up Nextflow\\. Make sure to \\[test your setup\\]\\(https://nf-co\\.re/docs/get_started/run-your-first',
    ),
        ),
    ),
    FirstOf(
        'README.md',
        operations=(
    Replace(
        'README.md',
        old="""\
> Please provide pipeline parameters via the CLI or Nextflow `-params-file` option. Custom config files including those provided by the `-c` Nextflow option can be used to provide any configuration _**except for parameters**_; see [docs](https://nf-co.re/docs/usage/getting_started/configuration#custom-configuration-files).
""",
        new="""\
> Please provide pipeline parameters via the CLI or Nextflow `-params-file` option. Custom config files including those provided by the `-c` Nextflow option can be used to provide any configuration _**except for parameters**_; see [docs](https://nf-co.re/docs/running/run-pipelines#using-parameter-files).
""",
        context_before="""\

> [!WARNING]
""",
        context_after="""\

For more details and further functionality, please refer to the [usage documentation](https://nf-co.re/{{pipeline_name}}/usage) and the [parameter documentation](https://nf-co.re/{{pipeline_name}}/parameters).
""",
    ),
    RegexReplace(
        'README.md',
        pattern='usage/getting_started/configuration#custom-configuration',
        replacement='running/run-pipelines#using-parameter',
        applied='running/run-pipelines#using-parameter',
    ),
        ),
    ),
    Replace(
        'README.md',
        old="""\
If you would like to contribute to this pipeline, please see the [contributing guidelines](.github/CONTRIBUTING.md).
""",
        new="""\
If you would like to contribute to this pipeline, please see the [contributing guidelines](docs/CONTRIBUTING.md).
""",
        context_before="""\
## Contributions and Support

""",
        context_after="""\

For further information or help, don't hesitate to get in touch on the [Slack `#{{pipeline_name}}` channel](https://nfcore.slack.com/channels/{{pipeline_name}}) (you can join with [this invite](https://nf-co.re/join/slack)).
""",
    ),
    DeleteFile(
        'assets/adaptivecard.json',
        expected_content='{\n    "type": "message",\n    "attachments": [\n        {\n            "contentType": "application/vnd.microsoft.card.adaptive",\n            "contentUrl": null,\n            "content": {\n                "\\$schema": "http://adaptivecards.io/schemas/adaptive-card.json",\n                "msteams": {\n                    "width": "Full"\n                },\n                "type": "AdaptiveCard",\n                "version": "1.2",\n                "body": [\n                    {\n                        "type": "TextBlock",\n                        "size": "Large",\n                        "weight": "Bolder",\n                        "color": "<% if (success) { %>Good<% } else { %>Attention<%} %>",\n                        "text": "nf-core/{{pipeline_name}} v${version} - ${runName}",\n                        "wrap": true\n                    },\n                    {\n                        "type": "TextBlock",\n                        "spacing": "None",\n                        "text": "Completed at ${dateComplete} (duration: ${duration})",\n                        "isSubtle": true,\n                        "wrap": true\n                    },\n                    {\n                        "type": "TextBlock",\n                        "text": "<% if (success) { %>Pipeline completed successfully!<% } else { %>Pipeline completed with errors. The full error message was: ${errorReport}.<% } %>",\n                        "wrap": true\n                    },\n                    {\n                        "type": "TextBlock",\n                        "text": "The command used to launch the workflow was as follows:",\n                        "wrap": true\n                    },\n                    {\n                        "type": "TextBlock",\n                        "text": "${commandLine}",\n                        "isSubtle": true,\n                        "wrap": true\n                    }\n                ],\n                "actions": [\n                    {\n                        "type": "Action.ShowCard",\n                        "title": "Pipeline Configuration",\n                        "card": {\n                            "type": "AdaptiveCard",\n                            "\\$schema": "http://adaptivecards.io/schemas/adaptive-card.json",\n                            "body": [\n                                {\n                                    "type": "FactSet",\n                                    "facts": [<% out << summary.collect{ k,v -> "{\\"title\\": \\"$k\\", \\"value\\" : \\"$v\\"}"}.join(",\\n") %>\n                                    ]\n                                }\n                            ]\n                        }\n                    }\n                ]\n            }\n        }\n    ]\n}\n',
    ),
    DeleteFile(
        'assets/slackreport.json',
        expected_content='{\n    "attachments": [\n        {\n            "fallback": "Plain-text summary of the attachment.",\n            "color": "<% if (success) { %>good<% } else { %>danger<%} %>",\n            "author_name": "nf-core/{{pipeline_name}} ${version} - ${runName}",\n            "author_icon": "https://www.nextflow.io/docs/latest/_static/favicon.ico",\n            "text": "<% if (success) { %>Pipeline completed successfully!<% } else { %>Pipeline completed with errors<% } %>",\n            "fields": [\n                {\n                    "title": "Command used to launch the workflow",\n                    "value": "```${commandLine}```",\n                    "short": false\n                }\n                <%\n                    if (!success) { %>\n                    ,\n                    {\n                        "title": "Full error message",\n                        "value": "```${errorReport}```",\n                        "short": false\n                    },\n                    {\n                        "title": "Pipeline configuration",\n                        "value": "<% out << summary.collect{ k,v -> k == "hook_url" ? "_${k}_: (_hidden_)" : ( ( v.class.toString().contains(\'Path\') || ( v.class.toString().contains(\'String\') && v.contains(\'/\') ) ) ? "_${k}_: `${v}`" : (v.class.toString().contains(\'DateTime\') ? ("_${k}_: " + v.format(java.time.format.DateTimeFormatter.ofLocalizedDateTime(java.time.format.FormatStyle.MEDIUM))) : "_${k}_: ${v}") ) }.join(",\\n") %>",\n                        "short": false\n                    }\n                    <% }\n                %>\n            ],\n            "footer": "Completed at <% out << dateComplete.format(java.time.format.DateTimeFormatter.ofLocalizedDateTime(java.time.format.FormatStyle.MEDIUM)) %> (duration: ${duration})"\n        }\n    ]\n}\n',
    ),
    Replace(
        'conf/base.config',
        old="""\
    errorStrategy = { task.exitStatus in ((130..145) + 104 + 175) ? 'retry' : 'finish' }
""",
        new="""\
    errorStrategy = { task.exitStatus in ((130..145) + 104 + (175..177)) ? 'retry' : 'finish' }
""",
        context_before="""\
    time   = { 4.h    * task.attempt }

""",
        context_after="""\
    maxRetries    = 1
    maxErrors     = '-1'
""",
    ),
    CreateFile(
        'docs/CONTRIBUTING.md',
        content='---\ntitle: Contributing\nmarkdownPlugin: checklist\n---\n\n# `nf-core/{{pipeline_name}}`: Contributing guidelines\n\nHi there!\nThanks for taking an interest in improving nf-core/{{pipeline_name}}.\n\nThis page describes the recommended nf-core way to contribute to both nf-core/{{pipeline_name}} and nf-core pipelines in general, including:\n\n- [General contribution guidelines](#general-contribution-guidelines): common procedures or guides across all nf-core pipelines.\n- [Pipeline-specific contribution guidelines](#pipeline-specific-contribution-guidelines): procedures or guides specific to the development conventions of nf-core/{{pipeline_name}}.\n\n> [!NOTE]\n> If you need help using or modifying nf-core/{{pipeline_name}}, ask on the nf-core Slack [#{{pipeline_name}}](https://nfcore.slack.com/channels/{{pipeline_name}}) channel ([join our Slack here](https://nf-co.re/join/slack)).\n\n## General contribution guidelines\n\n### Contribution quick start\n\nTo contribute code to any nf-core pipeline:\n\n- [ ] Ensure you have Nextflow, nf-core tools, and nf-test installed. See the [nf-core/tools repository](https://github.com/nf-core/tools) for instructions.\n- [ ] Check whether a GitHub [issue](https://github.com/nf-core/{{pipeline_name}}/issues) about your idea already exists. If an issue does not exist, create one so that others are aware you are working on it.\n- [ ] [Fork](https://help.github.com/en/github/getting-started-with-github/fork-a-repo) the [nf-core/{{pipeline_name}} repository](https://github.com/nf-core/{{pipeline_name}}) to your GitHub account.\n- [ ] Create a branch on your forked repository and make your changes following [pipeline conventions](#pipeline-contribution-conventions) (if applicable).\n- [ ] To fix major bugs, name your branch `patch` and follow the [patch release](#patch-release) process.\n- [ ] Update relevant documentation within the `docs/` folder, use nf-core/tools to update `nextflow_schema.json`, and update `CITATIONS.md`.\n- [ ] Run and/or update tests. See [Testing](#testing) for more information.\n- [ ] [Lint](#lint-tests) your code with nf-core/tools.\n- [ ] Submit a pull request (PR) against the `dev` branch and request a review.\n\nIf you are not used to this workflow with Git, see the [GitHub documentation](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests) or [Git resources](https://try.github.io/) for more information.\n\n## Use of AI and LLMs\n\nThe nf-core stance on the use of AI and LLMs is that humans are still ultimately responsible for their submitted code, regardless of the tools they use.\n\nIf you’re using AI tools, try to stick by these guidelines:\n\n- Keep PRs as small and focussed as possible\n- Avoid any unnecessary changes, such as moving or refactoring code (unless that is the explicit intention of the PR)\n- Review all generated code yourself before opening a PR, and ensure that you understand it\n- Engage with the community review process and expect to make revisions\n\nFor more detail, see the the [blog post](https://nf-co.re/blog/2026/statement-on-ai) for a statement from the nf-core/core team.\n\n### Getting help\n\nFor further information and help, see the [nf-core/{{pipeline_name}} documentation](https://nf-co.re/{{pipeline_name}}/usage) or ask on the nf-core [#{{pipeline_name}}](https://nfcore.slack.com/channels/{{pipeline_name}}) Slack channel ([join our Slack here](https://nf-co.re/join/slack)).\n\n### GitHub Codespaces\n\nYou can contribute to nf-core/{{pipeline_name}} without installing a local development environment on your machine by using [GitHub Codespaces](https://github.com/codespaces).\n\n[GitHub Codespaces](https://github.com/codespaces) is an online developer environment that runs in your browser, complete with VS Code and a terminal.\nMost nf-core repositories include a devcontainer configuration, which creates a GitHub Codespaces environment specifically for Nextflow development.\nThe environment includes pre-installed nf-core tools, Nextflow, and a few other helpful utilities via a Docker container.\n\nTo get started, open the repository in [Codespaces](https://github.com/nf-core/{{pipeline_name}}/codespaces).\n\n### Testing\n\nOnce you have made your changes, run the pipeline with nf-test to test them locally.\nFor additional information, use the `--verbose` flag to view the Nextflow console log output.\n\n```bash\nnf-test test --tag test --profile +docker --verbose\n```\n\nIf you have added new functionality, ensure you update the test assertions in the `.nf.test` files in the `tests/` directory.\nUpdate the snapshots with the following command:\n\n```bash\nnf-test test --tag test --profile +docker --verbose --update-snapshots\n```\n\nWhen you create a pull request with changes, GitHub Actions will run automatic tests.\nPull requests are typically reviewed when these tests are passing.\n\nTwo types of tests are typically run:\n\n#### Lint tests\n\nnf-core has a [set of guidelines](https://nf-co.re/docs/specifications/overview) which all pipelines must follow.\nTo enforce these, run linting with nf-core/tools:\n\n```bash\nnf-core pipelines lint <pipeline_directory>\n```\n\nIf you encounter failures or warnings, follow the linked documentation printed to screen.\nFor more information about linting tests, see [nf-core/tools API documentation](https://nf-co.re/docs/nf-core-tools/api_reference/latest/pipeline_lint_tests/actions_awsfulltest).\n\n#### Pipeline tests\n\nEach nf-core pipeline should be set up with a minimal set of test data.\nGitHub Actions runs the pipeline on this data to ensure it runs through and exits successfully.\nIf there are any failures then the automated tests fail.\nThese tests are run with the latest available version of Nextflow and the minimum required version specified in the pipeline code.\n\n### Patch release\n\n> [!WARNING]\n> Only in the unlikely event of a release that contains a critical bug.\n\n- [ ] Create a new branch `patch` on your fork based on `upstream/main` or `upstream/master`.\n- [ ] Fix the bug and use nf-core/tools to bump the version to the next semantic version, for example, `1.2.3` → `1.2.4`.\n- [ ] Open a Pull Request from `patch` directly to `main`/`master` with the changes.\n\n### Pipeline contribution conventions\n\nnf-core semi-standardises how you write code and other contributions to make the nf-core/{{pipeline_name}} code and processing logic more understandable for new contributors and to ensure quality.\n\n#### Add a new pipeline step\n\nTo contribute a new step to the pipeline, follow the general nf-core coding procedure.\nPlease also refer to the [pipeline-specific contribution guidelines](#pipeline-specific-contribution-guidelines):\n\n- [ ] Define the corresponding [input channel](#channel-naming-schemes) into your new process from the expected previous process channel.\n- [ ] Install a module with nf-core/tools, or write a local module (see [default processes resource requirements](#default-processes-resource-requirements)), and add it to the target `<workflow>.nf`.\n- [ ] Define the output channel if needed. Mix the version output channel into `ch_versions` and relevant files into `ch_multiqc`.\n- [ ] Add new or updated parameters to `nextflow.config` with a [default value](#default-parameter-values).\n- [ ] Add new or updated parameters and relevant help text to `nextflow_schema.json` with [nf-core/tools](#default-parameter-values).\n- [ ] Add validation for relevant parameters to the pipeline utilisation section of `utils_nfcore_\\_pipeline/main.nf` subworkflow.\n- [ ] Perform local tests to validate that the new code works as expected.\n  - [ ] If applicable, add a new test in the `tests` directory.\n- [ ] Update `usage.md`, `output.md`, and `citation.md` as appropriate.\n- [ ] [Lint](lint) the code with nf-core/tools.\n- [ ] Update any diagrams or pipeline images as necessary.\n- [ ] Update MultiQC config `assets/multiqc_config.yml` so relevant suffixes, file name cleanup, and module plots are in the appropriate order.\n- [ ] If applicable, create a [MultiQC](https://seqera.io/multiqc/) module.\n- [ ] Add a description of the output files and, if relevant, images from the MultiQC report to `docs/output.md`.\n\nTo update the minimum required Nextflow version, see the [Nextflow version bumping](#nextflow-version-bumping) section below. For more information about pipeline contributions, see [pipeline-specific contribution guidelines](#pipeline-specific-contribution-guidelines).\n\n#### Channel naming schemes\n\nUse the following naming schemes for channels to make the channel flow easier to understand:\n\n- Initial process channel: `ch_output_from_<process>`\n- Intermediate and terminal channels: `ch_<previousprocess>_for_<nextprocess>`\n\n#### Default parameter values\n\nParameters should be initialised and defined with default values within the `params` scope in `nextflow.config`.\nThey should also be documented in the pipeline JSON schema.\n\nTo update `nextflow_schema.json`, run:\n\n```bash\nnf-core pipelines schema build\n```\n\nThe schema builder interface that loads in your browser should automatically update the defaults in the parameter documentation.\n\n#### Default processes resource requirements\n\nIf you write a local module, specify a default set of resource requirements for the process.\n\nSensible defaults for process resource requirements (CPUs, memory, time) should be defined in `conf/base.config`.\nSpecify these with generic `withLabel:` selectors, so they can be shared across multiple processes and steps of the pipeline.\n\nnf-core provides a set of standard labels that you should follow where possible, as seen in the [nf-core pipeline template](https://github.com/nf-core/tools/blob/main/nf_core/pipeline-template/conf/base.config).\nThese labels define resource defaults for single-core processes, modules that require a GPU, and different levels of multi-core configurations with increasing memory requirements.\n\nValues assigned within these labels can be dynamically passed to a tool using the the `${task.cpus}` and `${task.memory}` Nextflow variables in the `script:` block of a module (see an example in the [modules repository](https://github.com/nf-core/modules/blob/bd1b6a40f55933d94b8c9ca94ec8c1ea0eaf4b82/modules/nf-core/samtools/bam2fq/main.nf#L30)).\n\n#### Nextflow version bumping\n\nIf you use a new feature from core Nextflow, bump the minimum required Nextflow version in the pipeline with:\n\n```bash\nnf-core pipelines bump-version --nextflow . <min_nf_version>\n```\n\n#### Images and figures guidelines\n\nIf you update images or graphics, follow the nf-core [style guidelines](https://nf-co.re/docs/community/brand/workflow-schematics).\n\n## Pipeline specific contribution guidelines\n\n<!-- TODO nf-core: Add any pipeline specific contribution guidelines here, such as coding styles, procedures, checklists etc. -->\n',
    ),
    Replace(
        'docs/usage.md',
        old="""\
> Do not use `-c <file>` to specify parameters as this will result in errors. Custom config files specified with `-c` must only be used for [tuning process resource specifications](https://nf-co.re/docs/usage/configuration#tuning-workflow-resources), other infrastructural tweaks (such as output directories), or module arguments (args).
""",
        new="""\
> Do not use `-c <file>` to specify parameters as this will result in errors. Custom config files specified with `-c` must only be used for [tuning process resource specifications](https://nf-co.re/docs/running/run-pipelines#configuring-pipelines), other infrastructural tweaks (such as output directories), or module arguments (args).
""",
        context_before="""\

> [!WARNING]
""",
        context_after="""\

The above pipeline run specified with a params file in yaml format:
""",
    ),
    FirstOf(
        'docs/usage.md',
        operations=(
    Replace(
        'docs/usage.md',
        old="""\
To change the resource requests, please see the [max resources](https://nf-co.re/docs/usage/configuration#max-resources) and [tuning workflow resources](https://nf-co.re/docs/usage/configuration#tuning-workflow-resources) section of the nf-core website.
""",
        new="""\
To change the resource requests, please see the [max resources](https://nf-co.re/docs/running/configuration/nextflow-for-your-system#set-max-resources) and [customise process resources](https://nf-co.re/docs/running/configuration/nextflow-for-your-system#customize-process-resources) section of the nf-core website.
""",
        context_before="""\
Whilst the default requirements set within the pipeline will hopefully work for most people and with most input data, you may find that you want to customise the compute resources that the pipeline requests. Each step in the pipeline has a default set of requirements for number of CPUs, memory and time. For most of the pipeline steps, if the job exits with any of the error codes specified [here](https://github.com/nf-core/rnaseq/blob/4c27ef5610c87db00c3c5a3eed10b1d161abf575/conf/base.config#L18) it will automatically be resubmitted with higher resources request (2 x original, then 3 x original). If it still fails after the third attempt then the pipeline execution is stopped.

""",
        context_after="""\

### Custom Containers
""",
    ),
    RegexReplace(
        'docs/usage.md',
        pattern='usage/configuration#max-resources\\) and \\[tuning workflow resources\\]\\(https://nf-co\\.re/docs/usage/configuration#tuning-workflow',
        replacement='running/configuration/nextflow-for-your-system#set-max-resources) and [customise process resources](https://nf-co.re/docs/running/configuration/nextflow-for-your-system#customize-process',
        applied='running/configuration/nextflow-for-your-system#set-max-resources\\) and \\[customise process resources\\]\\(https://nf-co\\.re/docs/running/configuration/nextflow-for-your-system#customize-process',
    ),
        ),
    ),
    FirstOf(
        'docs/usage.md',
        operations=(
    Replace(
        'docs/usage.md',
        old="""\
To use a different container from the default container or conda environment specified in a pipeline, please see the [updating tool versions](https://nf-co.re/docs/usage/configuration#updating-tool-versions) section of the nf-core website.
""",
        new="""\
To use a different container from the default container or conda environment specified in a pipeline, please see the [updating tool versions](https://nf-co.re/docs/running/configuration/nextflow-for-your-system#update-tool-versions) section of the nf-core website.
""",
        context_before="""\
In some cases, you may wish to change the container or conda environment used by a pipeline steps for a particular tool. By default, nf-core pipelines use containers and software from the [biocontainers](https://biocontainers.pro/) or [bioconda](https://bioconda.github.io/) projects. However, in some cases the pipeline specified version maybe out of date.

""",
        context_after="""\

### Custom Tool Arguments
""",
    ),
    RegexReplace(
        'docs/usage.md',
        pattern='usage/configuration#updating',
        replacement='running/configuration/nextflow-for-your-system#update',
        applied='running/configuration/nextflow-for-your-system#update',
    ),
        ),
    ),
    FirstOf(
        'docs/usage.md',
        operations=(
    Replace(
        'docs/usage.md',
        old="""\
To learn how to provide additional arguments to a particular tool of the pipeline, please see the [customising tool arguments](https://nf-co.re/docs/usage/configuration#customising-tool-arguments) section of the nf-core website.
""",
        new="""\
To learn how to provide additional arguments to a particular tool of the pipeline, please see the [customising tool arguments](https://nf-co.re/docs/running/configuration/nextflow-for-your-system#modifying-tool-arguments) section of the nf-core website.
""",
        context_before="""\
A pipeline might not always support every possible argument or option of a particular tool used in pipeline. Fortunately, nf-core pipelines provide some freedom to users to insert additional parameters that the pipeline does not include by default.

""",
        context_after="""\

### nf-core/configs
""",
    ),
    RegexReplace(
        'docs/usage.md',
        pattern='usage/configuration#customising',
        replacement='running/configuration/nextflow-for-your-system#modifying',
        applied='running/configuration/nextflow-for-your-system#modifying',
    ),
        ),
    ),
    Replace(
        'main.nf',
        old="""\
        samplesheet
""",
        new="""\
        samplesheet,
        params.multiqc_config,
        params.multiqc_logo,
        params.multiqc_methods_description,
        params.outdir,
""",
        context_before="""\
    //
    {{PIPELINE_NAME}} (
""",
        context_after="""\
    )
    emit:
""",
    ),
    RemoveText(
        'main.nf',
        text="""\
        params.hook_url,
""",
    ),
    RemoveText(
        'nextflow.config',
        text="""\
    hook_url                     = System.getenv('HOOK_URL')
""",
    ),
    Replace(
        'nextflow.config',
        old="""\
    validate_params            = true
}

// Load base.config by default for all pipelines
""",
        new="""\
    validate_params            = true
}

// Backwards compatibility for publishDir syntax
outputDir = params.outdir
workflow.output.mode = params.publish_dir_mode

// Load base.config by default for all pipelines
""",
        context_before="""\

    // Schema validation default options
""",
        context_after="""\
includeConfig 'conf/base.config'

""",
    ),
    FirstOf(
        'nextflow.config',
        operations=(
    Replace(
        'nextflow.config',
        old="""\
    nextflowVersion = '!>=25.04.0'
""",
        new="""\
    nextflowVersion = '!>=25.10.4'
""",
        context_before="""\
    mainScript      = 'main.nf'
    defaultBranch   = 'master'
""",
        context_after="""\
    version         = '{{pipeline_version}}'
    doi             = ''
""",
    ),
    BumpVersion(
        'nextflow.config',
        prefix="^[ \\t]*nextflowVersion\\s+=\\s+'!>=",
        old='25.04.0',
        new='25.10.4',
    ),
        ),
    ),
    Replace(
        'nextflow.config',
        old="""\
}

// Load modules.config for DSL2 module specific options
""",
        new="""\
}
// Load modules.config for DSL2 module specific options
""",
        context_before="""\
    defaultIgnoreParams = ["genomes"]
    monochromeLogs = params.monochrome_logs
""",
        context_after="""\
includeConfig 'conf/modules.config'
""",
    ),
    RemoveText(
        'nextflow_schema.json',
        text="""\
                "hook_url": {
                    "type": "string",
                    "description": "Incoming hook URL for messaging service",
                    "fa_icon": "fas fa-people-group",
                    "help_text": "Incoming hook URL for messaging service. Currently, MS Teams and Slack are supported.",
                    "hidden": true
                },
""",
    ),
    Replace(
        'nf-test.config',
        old="""\
    testsDir "."
""",
        new="""\
    testsDir = "."
""",
        context_before="""\
config {
    // location for all nf-test tests
""",
        context_after="""\

    // nf-test directory including temporary files for each test
""",
    ),
    Replace(
        'nf-test.config',
        old="""\
    workDir System.getenv("NFT_WORKDIR") ?: ".nf-test"
""",
        new="""\
    workDir = System.getenv("NFT_WORKDIR") ?: ".nf-test"
""",
        context_before="""\

    // nf-test directory including temporary files for each test
""",
        context_after="""\

    // location of an optional nextflow.config file specific for executing tests
""",
    ),
    Replace(
        'nf-test.config',
        old="""\
    configFile "tests/nextflow.config"
""",
        new="""\
    configFile = "tests/nextflow.config"
""",
        context_before="""\

    // location of an optional nextflow.config file specific for executing tests
""",
        context_after="""\

    // ignore tests coming from the nf-core/modules repo
""",
    ),
    Replace(
        'nf-test.config',
        old="""\
    ignore 'modules/nf-core/**/tests/*', 'subworkflows/nf-core/**/tests/*'
""",
        new="""\
    ignore = [
        'modules/nf-core/**/tests/*',
        'subworkflows/nf-core/**/tests/*',
    ]
""",
        context_before="""\

    // ignore tests coming from the nf-core/modules repo
""",
        context_after="""\

    // run all test with defined profile(s) from the main nextflow.config
""",
    ),
    Replace(
        'nf-test.config',
        old="""\
    profile "test"
""",
        new="""\
    profile = "test"
""",
        context_before="""\

    // run all test with defined profile(s) from the main nextflow.config
""",
        context_after="""\

    // list of filenames or patterns that should be trigger a full test run
""",
    ),
    Replace(
        'nf-test.config',
        old="""\
    triggers 'nextflow.config', 'nf-test.config', 'conf/test.config', 'tests/nextflow.config', 'tests/.nftignore'
""",
        new="""\
    triggers = [
        '.github/actions/nf-test/action.yml',
        '.github/workflows/nf-test.yml',
        'assets/schema_input.json',
        'bin/*',
        'conf/test.config',
        'nextflow.config',
        'nextflow_schema.json',
        'nf-test.config',
        'tests/.nftignore',
        'tests/nextflow.config',
    ]
""",
        context_before="""\

    // list of filenames or patterns that should be trigger a full test run
""",
        context_after="""\

    // load the necessary plugins
""",
    ),
    RemoveText(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        text="""\
include { imNotification            } from '../../nf-core/utils_nfcore_pipeline'
""",
    ),
    Replace(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        old='    //\n    before_text = """\n',
        new='    //\n\n    def before_text = ""\n    def after_text = ""\n    before_text = """\n',
        context_before="""\
    //
    // Validate parameters and generate parameter summary to stdout
""",
        context_after='-\\033[2m----------------------------------------------------\\033[0m-\n                                        \\033[0;32m,--.\\033[0;30m/\\033[0;32m,-.\\033[0m\n',
    ),
    Replace(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        old='"""\n    command = "nextflow run ${workflow.manifest.name} -profile <docker/singularity/.../institute> --input samplesheet.csv --outdir <OUTDIR>"\n',
        new='"""\n    if (monochrome_logs) {\n        before_text = before_text.replaceAll(/\\033\\[[0-9;]*m/, \'\')\n    }\n\n    command = "nextflow run ${workflow.manifest.name} -profile <docker/singularity/.../institute> --input samplesheet.csv --outdir <OUTDIR>"\n',
        context_before="""\
* Software dependencies
    https://github.com/nf-core/{{pipeline_name}}/blob/master/CITATIONS.md
""",
        context_after="""\

    UTILS_NFSCHEMA_PLUGIN (
""",
    ),
    Replace(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        old="""\
        .fromList(samplesheetToList(params.input, "${projectDir}/assets/schema_input.json"))
""",
        new="""\
        .fromList(samplesheetToList(input, "${projectDir}/assets/schema_input.json"))
""",
        context_before="""\

    channel
""",
        context_after="""\
        .map {
            meta, fastq_1, fastq_2 ->
""",
    ),
    RemoveText(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        text="""\
    hook_url        //  string: hook URL for notifications
""",
    ),
    Replace(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        old="""\
        completionSummary(monochrome_logs)
        if (hook_url) {
            imNotification(summary_params, hook_url)
        }
    }
""",
        new="""\
        completionSummary(monochrome_logs)

    }
""",
        context_before="""\
        }

""",
        context_after="""\

    workflow.onError {
""",
    ),
    FirstOf(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        operations=(
    Replace(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        old="""\
        log.error "Pipeline failed. Please refer to troubleshooting docs: https://nf-co.re/docs/usage/troubleshooting"
""",
        new="""\
        log.error "Pipeline failed. Please refer to troubleshooting docs for common issues: https://nf-co.re/docs/running/troubleshooting"
""",
        context_before="""\

    workflow.onError {
""",
        context_after="""\
    }
}
""",
    ),
    RegexReplace(
        'subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf',
        pattern='docs: https://nf-co\\.re/docs/usage',
        replacement='docs for common issues: https://nf-co.re/docs/running',
        applied='docs for common issues: https://nf-co\\.re/docs/running',
    ),
        ),
    ),
    Replace(
        'tests/default.nf.test',
        old="""\
            // stable_name: All files + folders in ${params.outdir}/ with a stable name
            def stable_name = getAllFilesFromDir(params.outdir, relative: true, includeDir: true, ignore: ['pipeline_info/*.{html,json,txt}'])
            // stable_path: All files in ${params.outdir}/ with stable content
            def stable_path = getAllFilesFromDir(params.outdir, ignoreFile: 'tests/.nftignore')
""",
        new="""\
            // stable_path: All files + folders in ${params.outdir}/ with a stable path (including file name)
            def stable_path = getAllFilesFromDir(params.outdir, relative: true, includeDir: true, ignore: ['pipeline_info/*.{html,json,txt}'])
            // stable_content: All files in ${params.outdir}/ with stable content
            def stable_content = getAllFilesFromDir(params.outdir, ignoreFile: 'tests/.nftignore')
            assert workflow.success
""",
        context_before="""\

        then {
""",
        context_after="""\
            assertAll(
                { assert workflow.success},
""",
    ),
    RemoveText(
        'tests/default.nf.test',
        text="""\
                { assert workflow.success},
""",
    ),
    Replace(
        'tests/default.nf.test',
        old="""\
                    stable_name,
""",
        new="""\
                    stable_path,
""",
        context_before="""\
                    removeNextflowVersion("$outputDir/pipeline_info/nf_core_{{pipeline_name}}_software_mqc_versions.yml"),
                    // All stable path name, with a relative path
""",
        context_after="""\
                    // All files with stable contents
                    stable_path
""",
    ),
    Replace(
        'tests/default.nf.test',
        old="""\
                    stable_path
""",
        new="""\
                    stable_content
""",
        context_before="""\
                    stable_name,
                    // All files with stable contents
""",
        context_after="""\
                ).match() }
            )
""",
    ),
    FirstOf(
        'tests/nextflow.config',
        operations=(
    Replace(
        'tests/nextflow.config',
        old="""\
    pipelines_testdata_base_path = 'https://raw.githubusercontent.com/nf-core/test-datasets/refs/heads/{{pipeline_name}}'
""",
        new="""\
    pipelines_testdata_base_path = 'https://raw.githubusercontent.com/nf-core/test-datasets/refs/heads/{{pipeline_name}}/'
""",
        context_before="""\
params {
    modules_testdata_base_path = 'https://raw.githubusercontent.com/nf-core/test-datasets/modules/data/'
""",
        context_after="""\
}

""",
    ),
    RegexReplace(
        'tests/nextflow.config',
        pattern='{{pipeline_name}}',
        replacement='{{pipeline_name}}/',
        applied='{{pipeline_name}}/',
    ),
        ),
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
    ch_samplesheet // channel: samplesheet read in from --input
    main:
""",
        new="""\
    ch_samplesheet // channel: samplesheet read in from --input
    multiqc_config
    multiqc_logo
    multiqc_methods_description
    outdir

    main:
""",
        context_before="""\

    take:
""",
        context_after="""\

    ch_versions = channel.empty()
""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
    ch_versions = channel.empty()
    ch_multiqc_files = channel.empty()
""",
        new="""\
    def ch_versions = channel.empty()
    def ch_multiqc_files = channel.empty()
""",
        context_before="""\
    main:

""",
        context_after="""\
    //
    // MODULE: Run FastQC
""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
    FASTQC (
        ch_samplesheet
    )
    ch_multiqc_files = ch_multiqc_files.mix(FASTQC.out.zip.collect{it[1]})
    ch_versions = ch_versions.mix(FASTQC.out.versions.first())
""",
        new="""\
    FASTQC(ch_samplesheet)
    ch_multiqc_files = ch_multiqc_files.mix(FASTQC.out.zip.map{ _meta, file -> file })
""",
        context_before="""\
    // MODULE: Run FastQC
    //
""",
        context_after="""\

    //
""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
    def topic_versions = Channel.topic("versions")
""",
        new="""\
    def topic_versions = channel.topic("versions")
""",
        context_before="""\
    // Collate and save software versions
    //
""",
        context_after="""\
        .distinct()
        .branch { entry ->
""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
    softwareVersionsToYAML(ch_versions.mix(topic_versions.versions_file))
""",
        new="""\
    def ch_collated_versions = softwareVersionsToYAML(ch_versions.mix(topic_versions.versions_file))
""",
        context_before="""\
        }

""",
        context_after="""\
        .mix(topic_versions_string)
        .collectFile(
""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
            storeDir: "${params.outdir}/pipeline_info",
""",
        new="""\
            storeDir: "${outdir}/pipeline_info",
""",
        context_before="""\
        .mix(topic_versions_string)
        .collectFile(
""",
        context_after="""\
            name: 'nf_core_'  +  '{{pipeline_name}}_software_'  + 'mqc_'  + 'versions.yml',
            sort: true,
""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
            newLine: true
        ).set { ch_collated_versions }


""",
        new="""\
            newLine: true
        )

""",
        context_before="""\
            name: 'nf_core_'  +  '{{pipeline_name}}_software_'  + 'mqc_'  + 'versions.yml',
            sort: true,
""",
        context_after="""\
    //
    // MODULE: MultiQC
""",
    ),
    RemoveText(
        'workflows/{{pipeline_name}}.nf',
        text="""\
    ch_multiqc_config        = channel.fromPath(
        "$projectDir/assets/multiqc_config.yml", checkIfExists: true)
    ch_multiqc_custom_config = params.multiqc_config ?
        channel.fromPath(params.multiqc_config, checkIfExists: true) :
        channel.empty()
    ch_multiqc_logo          = params.multiqc_logo ?
        channel.fromPath(params.multiqc_logo, checkIfExists: true) :
        channel.empty()

""",
    ),
    RemoveText(
        'workflows/{{pipeline_name}}.nf',
        text="""\
    summary_params      = paramsSummaryMap(
        workflow, parameters_schema: "nextflow_schema.json")
    ch_workflow_summary = channel.value(paramsSummaryMultiqc(summary_params))
    ch_multiqc_files = ch_multiqc_files.mix(
        ch_workflow_summary.collectFile(name: 'workflow_summary_mqc.yaml'))
    ch_multiqc_custom_methods_description = params.multiqc_methods_description ?
        file(params.multiqc_methods_description, checkIfExists: true) :
        file("$projectDir/assets/methods_description_template.yml", checkIfExists: true)
    ch_methods_description                = channel.value(
        methodsDescriptionText(ch_multiqc_custom_methods_description))

""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
    ch_multiqc_files = ch_multiqc_files.mix(
        ch_methods_description.collectFile(
            name: 'methods_description_mqc.yaml',
            sort: true
        )
""",
        new="""\
    def ch_summary_params = paramsSummaryMap(workflow, parameters_schema: "nextflow_schema.json")
    def ch_workflow_summary = channel.value(paramsSummaryMultiqc(ch_summary_params))
    ch_multiqc_files = ch_multiqc_files.mix(ch_workflow_summary.collectFile(name: 'workflow_summary_mqc.yaml'))
    def ch_multiqc_custom_methods_description = multiqc_methods_description
        ? file(multiqc_methods_description, checkIfExists: true)
        : file("${projectDir}/assets/methods_description_template.yml", checkIfExists: true)
    def ch_methods_description = channel.value(methodsDescriptionText(ch_multiqc_custom_methods_description))
    ch_multiqc_files = ch_multiqc_files.mix(ch_methods_description.collectFile(name: 'methods_description_mqc.yaml', sort: true))
    MULTIQC(
        ch_multiqc_files.flatten().collect().map { files ->
            [
                [id: '{{pipeline_name}}'],
                files,
                multiqc_config
                    ? file(multiqc_config, checkIfExists: true)
                    : file("${projectDir}/assets/multiqc_config.yml", checkIfExists: true),
                multiqc_logo ? file(multiqc_logo, checkIfExists: true) : [],
                [],
                [],
            ]
        }
""",
        context_before="""\

    ch_multiqc_files = ch_multiqc_files.mix(ch_collated_versions)
""",
        context_after="""\
    )

""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\

    MULTIQC (
        ch_multiqc_files.collect(),
        ch_multiqc_config.toList(),
        ch_multiqc_custom_config.toList(),
        ch_multiqc_logo.toList(),
        [],
        []
    )

    emit:multiqc_report = MULTIQC.out.report.toList() // channel: /path/to/multiqc_report.html
""",
        new="""\
    emit:multiqc_report = MULTIQC.out.report.map { _meta, report -> [report] }.toList() // channel: /path/to/multiqc_report.html
""",
        context_before="""\
        )
    )
""",
        context_after="""\
    versions       = ch_versions                 // channel: [ path(versions.yml) ]

""",
    ),
    Replace(
        'workflows/{{pipeline_name}}.nf',
        old="""\
    versions       = ch_versions                 // channel: [ path(versions.yml) ]

}
""",
        new="""\
    versions       = ch_versions                 // channel: [ path(versions.yml) ]
}
""",
        context_before="""\

    emit:multiqc_report = MULTIQC.out.report.toList() // channel: /path/to/multiqc_report.html
""",
        context_after="""\

/*
""",
    ),
    NfCoreComponent(
        'modules',
        'fastqc',
        git_sha='6d46786420b4d7bc88eba026eb389c0c5535d120',
    ),
    NfCoreComponent(
        'modules',
        'multiqc',
        git_sha='008f9d3e61209bf995edac3ba531f54e269e1215',
    ),
    NfCoreComponent(
        'subworkflows',
        'utils_nfcore_pipeline',
        git_sha='a3fb7351b1fdb2b1de282b765816bbea190e86a8',
    ),
    NfCoreComponent(
        'subworkflows',
        'utils_nfschema_plugin',
        git_sha='fdc08b8b1ae74f56686ce21f7ea11ad11990ce57',
    ),
    ManualStep(
        'conf/containers_*.config',
        'regenerate with `nf-core pipelines lint --fix container_configs`',
    ),
    ManualStep(
        'ro-crate-metadata.json',
        'regenerate with `nf-core pipelines rocrate`',
    ),
]
