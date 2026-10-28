from pathlib import Path

from nf_migrate.operations import (
    BumpVersion,
    CreateFile,
    DeleteFile,
    FirstOf,
    Outcome,
    RegexReplace,
    RemoveText,
    Replace,
    ReplaceFile,
    SnapNormalize,
    Workspace,
)


def make_workspace(tmp_path: Path, files: dict[str, str]) -> Workspace:
    for relative_path, content in files.items():
        file_path = tmp_path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    return Workspace(tmp_path)


# Replace
def test_replace_applies_when_old_text_occurs_once(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "x = 1\ny = 2\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("a.config") == "x = 1\ny = 3\n"


def test_replace_is_already_applied_when_only_new_text_is_present(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y = 3\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_replace_is_already_applied_when_old_text_only_occurs_inside_new(
    tmp_path: Path,
) -> None:
    # Given a template change that appended a line at the end of the file
    workspace = make_workspace(tmp_path, {".gitattributes": "a\nb\n"})
    operation = Replace(".gitattributes", old="a\n", new="a\nb\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.read(".gitattributes") == "a\nb\n"


def test_replace_conflicts_when_neither_text_is_present(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y = 42\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("a.config") == "y = 42\n"


def test_replace_conflicts_when_old_text_is_ambiguous(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y = 2\ny = 2\n"})
    operation = Replace("a.config", old="y = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "2 times" in result.message


def test_replace_only_matches_whole_lines(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "line 13\nline 3\n"})
    operation = Replace("a.txt", old="line 3\n", new="line three\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("a.txt") == "line 13\nline three\n"


def test_replace_matches_old_text_realigned_by_the_pipeline(
    tmp_path: Path,
) -> None:
    # Given a pipeline that aligned and trimmed differently
    workspace = make_workspace(
        tmp_path,
        {"test.config": "    max_cpus = 2\n    max_time = 6.h  \n"},
    )
    operation = Replace(
        "test.config",
        old="    max_time   = 6.h\n",
        new="    max_time   = '6.h'\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("test.config") == (
        "    max_cpus = 2\n    max_time   = '6.h'\n"
    )


def test_replace_is_already_applied_when_new_text_is_realigned(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(
        tmp_path, {"test.config": "    max_time = '6.h'\n"}
    )
    operation = Replace(
        "test.config",
        old="    max_time   = 6.h\n",
        new="    max_time   = '6.h'\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_replace_still_requires_the_same_indentation(tmp_path: Path) -> None:
    # Given YAML, where indentation changes the meaning
    workspace = make_workspace(tmp_path, {"a.yml": "a:\n  key: 1\n"})
    operation = Replace("a.yml", old="    key: 1\n", new="    key: 2\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("a.yml") == "a:\n  key: 1\n"


def test_replace_conflicts_when_realigned_old_text_is_ambiguous(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y  = 2\ny = 2\n"})
    operation = Replace("a.config", old="y   = 2\n", new="y = 3\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "2 times" in result.message


def test_replace_picks_the_occurrence_whose_context_matches(
    tmp_path: Path,
) -> None:
    # Given a line the template has once but this pipeline twice
    workspace = make_workspace(
        tmp_path,
        {
            "usage.md": (
                "### `--genome`\n\nNB: Single hyphen\n\n"
                "### `-name`\n\nNB: Single hyphen\n\n### `-resume`\n"
            )
        },
    )
    operation = Replace(
        "usage.md",
        old="NB: Single hyphen\n",
        new="#### Custom resource requests\n",
        context_before="### `-name`\n\n",
        context_after="\n### `-resume`\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("usage.md") == (
        "### `--genome`\n\nNB: Single hyphen\n\n"
        "### `-name`\n\n#### Custom resource requests\n\n### `-resume`\n"
    )


def test_replace_conflicts_when_context_does_not_tell_occurrences_apart(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.config": "y = 2\ny = 2\n"})
    operation = Replace(
        "a.config", old="y = 2\n", new="y = 3\n", context_before="x = 1\n"
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "2 times" in result.message


def test_replace_follows_markdown_lists_reindented_by_the_pipeline(
    tmp_path: Path,
) -> None:
    # Given nested lists the pipeline indents by 4 where the template uses 2
    workspace = make_workspace(
        tmp_path,
        {"usage.md": "* `docker`\n    * Pulls from Docker Hub\n* `conda`\n"},
    )
    operation = Replace(
        "usage.md",
        old="* `docker`\n  * Pulls from Docker Hub\n",
        new="* `docker`\n  * Pulls from Docker Hub\n* `podman`\n  * Podman\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("usage.md") == (
        "* `docker`\n    * Pulls from Docker Hub\n"
        "* `podman`\n    * Podman\n* `conda`\n"
    )


def test_replace_ignores_markdown_emphasis_and_bullet_styles(
    tmp_path: Path,
) -> None:
    # Given a formatter that rewrote __bold__ and * bullets
    workspace = make_workspace(
        tmp_path,
        {"usage.md": "Do not **cap** resources.\n- Docker\n- Conda\n"},
    )
    operation = Replace(
        "usage.md",
        old="Do not __cap__ resources.\n* Docker\n",
        new="Do not __cap__ resources.\n* Docker\n* Podman\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("usage.md") == (
        "Do not __cap__ resources.\n* Docker\n* Podman\n- Conda\n"
    )


def test_replace_does_not_reindent_yaml(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.yml": "a:\n    key: 1\n"})
    operation = Replace("a.yml", old="a:\n  key: 1\n", new="a:\n  key: 2\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT


def test_replace_every_occurrence_bumps_each_copied_ci_job(
    tmp_path: Path,
) -> None:
    # Given a pipeline that copied a CI job using the template's action
    workspace = make_workspace(
        tmp_path,
        {"ci.yml": "  - uses: get-diff@v1\n  run: a\n  - uses: get-diff@v1\n"},
    )
    operation = Replace(
        "ci.yml",
        old="  - uses: get-diff@v1\n",
        new="  - uses: get-diff@v4\n",
        every=True,
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("ci.yml") == (
        "  - uses: get-diff@v4\n  run: a\n  - uses: get-diff@v4\n"
    )


def test_replace_with_requires_skips_files_that_dropped_that_text(
    tmp_path: Path,
) -> None:
    # Given a README whose template TODO notes the pipeline filled in
    workspace = make_workspace(
        tmp_path, {"README.md": "## Credits\n\nWritten by us.\n"}
    )
    operation = Replace(
        "README.md",
        old="## Credits\n",
        new="## Credits\n\n<!-- TODO nf-core: list contributors -->\n",
        requires="TODO nf-core",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert "TODO nf-core" in result.message
    assert workspace.changed_paths() == []


def test_replace_with_requires_applies_while_the_text_is_there(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(
        tmp_path,
        {"README.md": "<!-- TODO nf-core: summary -->\n## Credits\n"},
    )
    operation = Replace(
        "README.md",
        old="## Credits\n",
        new="## Credits\n<!-- TODO nf-core: list contributors -->\n",
        requires="TODO nf-core",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED


def test_replace_matches_when_the_pipeline_resolved_a_todo_note(
    tmp_path: Path,
) -> None:
    # Given a pipeline that deleted the template's TODO note
    workspace = make_workspace(
        tmp_path,
        {"base.config": "process {\n  cpus = 1\n  memory = 7.GB\n}\n"},
    )
    operation = Replace(
        "base.config",
        old=(
            "  // TODO nf-core: Check the defaults for all processes\n"
            "  cpus = 1\n  memory = 7.GB\n"
        ),
        new=(
            "    // TODO nf-core: Check the defaults for all processes\n"
            "    cpus   = 1\n    memory = 6.GB\n"
        ),
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("base.config") == (
        "process {\n    cpus   = 1\n    memory = 6.GB\n}\n"
    )


def test_replace_of_a_resolved_todo_note_goes_where_the_note_was(
    tmp_path: Path,
) -> None:
    # Given a README whose maintainers deleted the TODO note
    workspace = make_workspace(
        tmp_path,
        {"README.md": "## Usage\n\n```bash\nnextflow run x\n```\n"},
    )
    operation = Replace(
        "README.md",
        old="<!-- TODO nf-core: Update the typical command -->\n",
        new="Now, you can run the pipeline using:\n",
        context_before="## Usage\n\n",
        context_after="```bash\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("README.md") == (
        "## Usage\n\nNow, you can run the pipeline using:\n"
        "```bash\nnextflow run x\n```\n"
    )


def test_remove_text_removes_a_paragraph_kept_verbatim(tmp_path: Path) -> None:
    # Given a usage doc with a template section and the pipeline's own
    workspace = make_workspace(
        tmp_path,
        {"usage.md": "## Job resources\n\nGeneric.\n\n## Mine\n\nOwn.\n"},
    )
    operation = RemoveText("usage.md", text="## Job resources\n\nGeneric.\n\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("usage.md") == "## Mine\n\nOwn.\n"


def test_remove_text_is_already_applied_when_the_text_is_gone(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"usage.md": "## Mine\n"})
    operation = RemoveText("usage.md", text="## Job resources\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_remove_text_conflicts_when_the_text_is_ambiguous(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"usage.md": "NB: x\nNB: x\n"})
    operation = RemoveText("usage.md", text="NB: x\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "2 times" in result.message


def test_remove_text_is_already_applied_when_the_file_is_gone(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = RemoveText("usage.md", text="## Job resources\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


# RegexReplace
MAX_CPUS = RegexReplace(
    "nextflow.config",
    pattern=r"^    max_cpus += (?P<cpus>\d+)\n",
    replacement="    resourceLimits = [cpus: \\g<cpus>]\n",
    applied=r"^    resourceLimits = \[cpus: \d+\]\n",
)


def test_regex_replace_keeps_the_captured_pipeline_values(
    tmp_path: Path,
) -> None:
    # Given a pipeline that raised the template's max_cpus
    workspace = make_workspace(
        tmp_path, {"nextflow.config": "params {\n    max_cpus   = 64\n}\n"}
    )

    # When
    result = MAX_CPUS.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("nextflow.config") == (
        "params {\n    resourceLimits = [cpus: 64]\n}\n"
    )


def test_regex_replace_is_already_applied_when_only_applied_matches(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(
        tmp_path, {"nextflow.config": "    resourceLimits = [cpus: 64]\n"}
    )

    # When
    result = MAX_CPUS.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.changed_paths() == []


def test_regex_replace_conflicts_when_neither_pattern_matches(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"nextflow.config": "params {}\n"})

    # When
    result = MAX_CPUS.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert result.message == "pattern not found"
    assert "max_cpus" in result.suggestion


def test_regex_replace_conflicts_when_the_pattern_matches_twice(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(
        tmp_path,
        {"nextflow.config": "    max_cpus = 16\n    max_cpus = 64\n"},
    )

    # When
    result = MAX_CPUS.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "2 times" in result.message
    assert workspace.changed_paths() == []


def test_regex_replace_ignores_matches_inside_the_applied_text(
    tmp_path: Path,
) -> None:
    # Given a template change that appended a line after the matched one
    operation = RegexReplace(
        ".gitignore",
        pattern=r"^results/?\n",
        replacement="\\g<0>null/\n",
        applied=r"^results/?\nnull/\n",
    )
    workspace = make_workspace(tmp_path, {".gitignore": "results\nnull/\n"})

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


def test_regex_replace_every_changes_each_match(tmp_path: Path) -> None:
    # Given two samplesheet examples with the pipeline's own columns
    workspace = make_workspace(
        tmp_path,
        {
            "usage.md": "```console\nsample,bam\n```\n"
            "```console\nsample,fastq_1\n```\n```console\nls\n```\n"
        },
    )
    operation = RegexReplace(
        "usage.md",
        pattern=r"^```console\n(?=sample,)",
        replacement='```csv title="samplesheet.csv"\n',
        applied=r'^```csv title="samplesheet\.csv"\n',
        every=True,
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("usage.md") == (
        '```csv title="samplesheet.csv"\nsample,bam\n```\n'
        '```csv title="samplesheet.csv"\nsample,fastq_1\n```\n'
        "```console\nls\n```\n"
    )


def test_regex_replace_fills_placeholders_as_literal_text(
    tmp_path: Path,
) -> None:
    # Given a value with characters that are special in a pattern
    make_workspace(tmp_path, {"README.md": "# nf-core/c++tools\n"})
    workspace = Workspace(tmp_path, variables={"pipeline_name": "c++tools"})
    operation = RegexReplace(
        "README.md",
        pattern=r"^# nf-core/{{pipeline_name}}\n",
        replacement="# {{pipeline_name}}\n",
        applied=r"^# {{pipeline_name}}\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("README.md") == "# c++tools\n"


def test_regex_replace_is_skipped_when_file_is_missing(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})

    # When
    result = MAX_CPUS.apply(workspace)

    # Then
    assert result.outcome is Outcome.SKIPPED
    assert result.message == "the pipeline has no such file"


# BumpVersion
NF_SCHEMA = BumpVersion(
    "nextflow.config", prefix=r"id 'nf-schema@", old="2.1.1", new="2.3.0"
)


def test_bump_version_raises_an_older_version_whatever_follows(
    tmp_path: Path,
) -> None:
    # Given the pipeline's own comment after the plugin
    workspace = make_workspace(
        tmp_path,
        {"nextflow.config": "plugins {\n    id 'nf-schema@2.1.1' // ours\n}\n"},
    )

    # When
    result = NF_SCHEMA.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("nextflow.config") == (
        "plugins {\n    id 'nf-schema@2.3.0' // ours\n}\n"
    )


def test_bump_version_keeps_a_newer_version(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(
        tmp_path, {"nextflow.config": "    id 'nf-schema@2.4.2'\n"}
    )

    # When
    result = NF_SCHEMA.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert "newer" in result.message


def test_bump_version_conflicts_without_the_versioned_text(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"nextflow.config": "plugins {}\n"})

    # When
    result = NF_SCHEMA.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT


# FirstOf
TEMPLATE_CPUS = "    cpus   = { check_max( 1    * task.attempt, 'cpus'   ) }\n"
CHECK_MAX = FirstOf(
    "base.config",
    operations=(
        Replace(
            "base.config",
            old=TEMPLATE_CPUS,
            new="    cpus   = { 1      * task.attempt }\n",
        ),
        RegexReplace(
            "base.config",
            pattern=r"check_max\(\s*([^,]+?)\s*,\s*'\w+'\s*\)",
            replacement=r"\1",
            applied=r"\A(?![\s\S]*check_max\()[\s\S]*",
            every=True,
        ),
    ),
)


def test_first_of_uses_the_template_change_where_it_fits(
    tmp_path: Path,
) -> None:
    # Given an untouched template line
    workspace = make_workspace(
        tmp_path,
        {"base.config": TEMPLATE_CPUS},
    )

    # When
    result = CHECK_MAX.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert (
        workspace.read("base.config")
        == "    cpus   = { 1      * task.attempt }\n"
    )


def test_first_of_falls_back_to_the_next_operation(tmp_path: Path) -> None:
    # Given a pipeline with its own resource values
    workspace = make_workspace(
        tmp_path,
        {"base.config": "cpus = { check_max( 4 * task.attempt, 'cpus' ) }\n"},
    )

    # When
    result = CHECK_MAX.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("base.config") == "cpus = { 4 * task.attempt }\n"


def test_first_of_reports_the_first_conflict_when_nothing_fits(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"base.config": "cpus = 4\n"})
    operation = FirstOf(
        "base.config",
        operations=(
            Replace("base.config", old="cpus = 1\n", new="cpus = 2\n"),
            Replace("base.config", old="cpus = 3\n", new="cpus = 2\n"),
        ),
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert "cpus = 1" in result.suggestion


# ReplaceFile
DSL2_MAIN = ReplaceFile(
    "main.nf",
    content="nextflow.enable.dsl = 2\ninclude { PIPE } from './pipe'\n",
    already="nextflow.enable.dsl = 2",
)


def test_replace_file_swaps_a_file_the_release_rewrote(tmp_path: Path) -> None:
    # Given a DSL1 main.nf with the pipeline's own processes
    workspace = make_workspace(tmp_path, {"main.nf": "process FOO {\n}\n"})

    # When
    result = DSL2_MAIN.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert "replaced as a whole" in result.message
    assert workspace.read("main.nf") == DSL2_MAIN.content


def test_replace_file_keeps_a_file_already_on_the_new_structure(
    tmp_path: Path,
) -> None:
    # Given a pipeline that moved to DSL2 on its own
    content = (
        "nextflow.enable.dsl = 2\ninclude { MINE } from './workflows/mine'\n"
    )
    workspace = make_workspace(tmp_path, {"main.nf": content})

    # When
    result = DSL2_MAIN.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED
    assert workspace.read("main.nf") == content


# CreateFile
def test_create_file_writes_a_missing_file(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = CreateFile("tests/nextflow.config", content="params {}\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("tests/nextflow.config") == "params {}\n"


def test_create_file_is_already_applied_for_identical_file(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "same\n"})
    operation = CreateFile("a.txt", content="same\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


def test_create_file_conflicts_with_a_different_existing_file(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "local\n"})
    operation = CreateFile("a.txt", content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("a.txt") == "local\n"


# DeleteFile
def test_delete_file_removes_an_unmodified_file(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"old.yml": "template\n"})
    operation = DeleteFile("old.yml", expected_content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("old.yml") is None


def test_delete_file_conflicts_when_file_was_customised(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"old.yml": "customised\n"})
    operation = DeleteFile("old.yml", expected_content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.CONFLICT
    assert workspace.read("old.yml") == "customised\n"


def test_delete_file_is_already_applied_when_file_is_gone(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = DeleteFile("old.yml", expected_content="template\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.ALREADY_APPLIED


# Workspace
def test_workspace_only_touches_disk_on_commit(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {"a.txt": "before\n", "b.txt": "x"})
    workspace.write("a.txt", "after\n")
    workspace.delete("b.txt")
    workspace.write("new/c.txt", "c\n")

    # When
    content_before_commit = (tmp_path / "a.txt").read_text()
    workspace.commit()

    # Then
    assert content_before_commit == "before\n"
    assert (tmp_path / "a.txt").read_text() == "after\n"
    assert not (tmp_path / "b.txt").exists()
    assert (tmp_path / "new/c.txt").read_text() == "c\n"


# Template variables
def test_operations_expand_template_variables_from_the_workspace(
    tmp_path: Path,
) -> None:
    # Given
    make_workspace(tmp_path, {"workflows/rnaseq.nf": "workflow RNASEQ {\n"})
    workspace = Workspace(
        tmp_path,
        variables={"pipeline_name": "rnaseq", "PIPELINE_NAME": "RNASEQ"},
    )
    operation = Replace(
        "workflows/{{pipeline_name}}.nf",
        old="workflow {{PIPELINE_NAME}} {\n",
        new="workflow {{PIPELINE_NAME}} {\n    main:\n",
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert result.path == "workflows/rnaseq.nf"
    assert workspace.read("workflows/rnaseq.nf") == (
        "workflow RNASEQ {\n    main:\n"
    )


# Files the pipeline no longer has
def test_replace_is_skipped_when_the_pipeline_has_no_such_file(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = Replace("conf/igenomes.config", old="a\n", new="b\n")

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.SKIPPED
    assert result.path == "conf/igenomes.config"
    assert workspace.read("conf/igenomes.config") is None


def test_bump_version_is_skipped_when_the_pipeline_has_no_such_file(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})

    # When
    result = NF_SCHEMA.apply(workspace)

    # Then
    assert result.outcome is Outcome.SKIPPED


def test_first_of_is_skipped_when_the_pipeline_has_no_such_file(
    tmp_path: Path,
) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})
    operation = FirstOf(
        "a.config",
        (
            Replace("a.config", old="a\n", new="b\n"),
            Replace("a.config", old="c\n", new="d\n"),
        ),
    )

    # When
    result = operation.apply(workspace)

    # Then
    assert result.outcome is Outcome.SKIPPED


def test_edit_applies_to_a_file_an_earlier_operation_created(
    tmp_path: Path,
) -> None:
    # Given a file that only exists because this migration creates it
    workspace = make_workspace(tmp_path, {})
    CreateFile("new.config", content="a\n").apply(workspace)

    # When
    result = Replace("new.config", old="a\n", new="b\n").apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED
    assert workspace.read("new.config") == "b\n"


def test_create_file_still_creates_a_missing_file(tmp_path: Path) -> None:
    # Given
    workspace = make_workspace(tmp_path, {})

    # When
    result = CreateFile("new.config", content="a\n").apply(workspace)

    # Then
    assert result.outcome is Outcome.APPLIED


# SnapNormalize
SNAP_UNSORTED = """\
{
    "-profile test": {
        "content": [
            {
                "SUMMARIZER": {
                    "python": "3.11.0",
                    "pandas": "1.5.2",
                    "numpy": "1.24.2"
                },
                "SUMMARY_CLASSIFICATION": {
                    "python": "3.11.0",
                    "pandas": "1.5.2"
                },
                "Workflow": {
                    "nf-core/mypipeline": "v1.0.0"
                }
            }
        ]
    }
}
"""

SNAP_SORTED = """\
{
    "-profile test": {
        "content": [
            {
                "SUMMARIZER": {
                    "numpy": "1.24.2",
                    "pandas": "1.5.2",
                    "python": "3.11.0"
                },
                "SUMMARY_CLASSIFICATION": {
                    "pandas": "1.5.2",
                    "python": "3.11.0"
                },
                "Workflow": {
                    "nf-core/mypipeline": "v1.0.0"
                }
            }
        ]
    }
}
"""


def test_snap_normalize_sorts_leaf_dict_keys(tmp_path: Path) -> None:
    # Given a snapshot with unsorted version keys
    workspace = make_workspace(
        tmp_path, {"tests/default.nf.test.snap": SNAP_UNSORTED}
    )

    # When
    results = SnapNormalize().apply(workspace)

    # Then
    assert len(results) == 1
    assert results[0].outcome is Outcome.APPLIED
    assert workspace.read("tests/default.nf.test.snap") == SNAP_SORTED


def test_snap_normalize_is_already_applied_when_keys_are_sorted(
    tmp_path: Path,
) -> None:
    # Given a snapshot already in alphabetical order
    workspace = make_workspace(
        tmp_path, {"tests/default.nf.test.snap": SNAP_SORTED}
    )

    # When
    results = SnapNormalize().apply(workspace)

    # Then
    assert len(results) == 1
    assert results[0].outcome is Outcome.ALREADY_APPLIED
    assert workspace.read("tests/default.nf.test.snap") == SNAP_SORTED


def test_snap_normalize_skips_when_no_files_match(tmp_path: Path) -> None:
    # Given a workspace with no snap files
    workspace = make_workspace(tmp_path, {"main.nf": "workflow {}\n"})

    # When
    results = SnapNormalize().apply(workspace)

    # Then
    assert len(results) == 1
    assert results[0].outcome is Outcome.SKIPPED


def test_snap_normalize_processes_all_matching_files(tmp_path: Path) -> None:
    # Given two snap files with unsorted keys
    workspace = make_workspace(tmp_path, {
        "tests/a.nf.test.snap": SNAP_UNSORTED,
        "tests/b.nf.test.snap": SNAP_UNSORTED,
    })

    # When
    results = SnapNormalize().apply(workspace)

    # Then
    assert len(results) == 2
    assert all(r.outcome is Outcome.APPLIED for r in results)
    assert workspace.read("tests/a.nf.test.snap") == SNAP_SORTED
    assert workspace.read("tests/b.nf.test.snap") == SNAP_SORTED


def test_snap_normalize_does_not_sort_enclosing_tool_group_dicts(
    tmp_path: Path,
) -> None:
    # Given tool-group dicts have dict values — they must not be reordered
    snap = """\
{
    "-profile test": {
        "content": [
            {
                "ZTOOL": {
                    "ztool": "1.0"
                },
                "ATOOL": {
                    "atool": "2.0"
                }
            }
        ]
    }
}
"""
    workspace = make_workspace(tmp_path, {"tests/default.nf.test.snap": snap})

    # When
    results = SnapNormalize().apply(workspace)

    # Then — outer dict unchanged, inner single-key dicts unchanged
    assert results[0].outcome is Outcome.ALREADY_APPLIED
