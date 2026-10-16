import json
import subprocess
from pathlib import Path

from nf_migrate.autogenerate import diff_hunks, generate_migration
from nf_migrate.migrations import load_migrations
from nf_migrate.operations import Outcome, Replace, Workspace
from nf_migrate.runner import upgrade


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def commit_files(repo: Path, files: dict[str, str | None]) -> str:
    for relative_path, content in files.items():
        file_path = repo / relative_path
        if content is None:
            file_path.unlink()
            continue
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "template")
    return git(repo, "rev-parse", "HEAD")


BASE_CONFIG_OLD = "".join(f"line {number}\n" for number in range(1, 21))
BASE_CONFIG_NEW = BASE_CONFIG_OLD.replace("line 3\n", "line three\n").replace(
    "line 18\n", "line eighteen\n"
)


def test_generated_migration_applies_template_diff_to_customised_pipeline(
    tmp_path: Path,
) -> None:
    # Given a template repo with two template versions
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 3.2.1\n",
            "base.config": BASE_CONFIG_OLD,
            "removed.yml": "gone\n",
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 3.3.1\n",
            "base.config": BASE_CONFIG_NEW,
            "removed.yml": None,
            "added.yml": "new\n",
        },
    )

    # And a pipeline that customised the middle of base.config
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / ".nf-core.yml").write_text("nf_core_version: 3.2.1\n")
    (pipeline / "removed.yml").write_text("gone\n")
    customised_config = BASE_CONFIG_OLD.replace("line 10\n", "my line\n")
    (pipeline / "base.config").write_text(customised_config)

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "v3_3_1.py").write_text(generated.source)
    report = upgrade(pipeline, load_migrations(migrations_dir), target="head")

    # Then
    assert report.succeeded, report.render()
    expected_config = BASE_CONFIG_NEW.replace("line 10\n", "my line\n")
    assert (pipeline / "base.config").read_text() == expected_config
    assert (pipeline / "added.yml").read_text() == "new\n"
    assert not (pipeline / "removed.yml").exists()
    assert (pipeline / ".nf-core.yml").read_text() == (
        "nf_core_version: 3.3.1\n"
    )


def test_generated_files_are_noted_instead_of_diffed(tmp_path: Path) -> None:
    # Given a template update that only regenerates the RO-Crate
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 4.0.3\n",
            "ro-crate-metadata.json": '{"@id": "#random-1"}\n',
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 4.1.0\n",
            "ro-crate-metadata.json": '{"@id": "#random-2"}\n',
        },
    )

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)

    # Then
    assert "#random" not in generated.source
    assert "ManualStep(" in generated.source
    assert "nf-core pipelines rocrate" in generated.source


def test_nf_core_components_become_component_operations(
    tmp_path: Path,
) -> None:
    # Given a template update that bumps multiqc and its container configs
    def modules_json(sha: str) -> str:
        content = {
            "repos": {
                "https://github.com/nf-core/modules.git": {
                    "modules": {"nf-core": {"multiqc": {"git_sha": sha}}}
                }
            }
        }
        return json.dumps(content) + "\n"

    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 4.0.3\n",
            "modules.json": modules_json("old000"),
            "modules/nf-core/multiqc/main.nf": "process MULTIQC { v1 }\n",
            "conf/containers_docker_amd64.config": "v1\n",
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 4.1.0\n",
            "modules.json": modules_json("new111"),
            "modules/nf-core/multiqc/main.nf": "process MULTIQC { v2 }\n",
            "conf/containers_docker_amd64.config": "v2\n",
        },
    )

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)

    # Then
    assert "Replace(" not in generated.source
    assert "NfCoreComponent(" in generated.source
    assert "'multiqc'" in generated.source
    assert "'new111'" in generated.source
    assert "lint --fix container_configs" in generated.source


def test_migration_generated_from_one_pipeline_applies_to_another(
    tmp_path: Path,
) -> None:
    # Given a template rendered for a placeholder pipeline
    sentinel_yml = (
        "nf_core_version: {version}\n"
        "template:\n"
        "  author: Sentinel Author\n"
        "  description: Sentinel pipeline description\n"
        "  name: sentinelpipe\n"
        "  version: 7.7.7dev\n"
    )
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": sentinel_yml.format(version="4.0.3"),
            "workflows/sentinelpipe.nf": "workflow SENTINELPIPE {\n}\n",
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": sentinel_yml.format(version="4.1.0"),
            "workflows/sentinelpipe.nf": (
                "workflow SENTINELPIPE {\n    main:\n}\n"
            ),
        },
    )

    # And a different pipeline at the old version
    pipeline = tmp_path / "rnaseq"
    (pipeline / "workflows").mkdir(parents=True)
    (pipeline / ".nf-core.yml").write_text(
        "nf_core_version: 4.0.3\n"
        "template:\n"
        "  author: Harshil Patel\n"
        "  description: RNA sequencing analysis pipeline\n"
        "  name: rnaseq\n"
        "  version: 3.28.0dev\n"
    )
    (pipeline / "workflows/rnaseq.nf").write_text("workflow RNASEQ {\n}\n")

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "v4_1_0.py").write_text(generated.source)
    report = upgrade(pipeline, load_migrations(migrations_dir), target="head")

    # Then
    assert "sentinelpipe" not in generated.source.lower()
    assert report.succeeded, report.render()
    assert (pipeline / "workflows/rnaseq.nf").read_text() == (
        "workflow RNASEQ {\n    main:\n}\n"
    )


# Context around template changes
def test_unique_replacement_needs_no_context() -> None:
    # Given a one-line change whose new text is unique in both versions
    old_text = "header\nbadge 4.0.2\nfooter\n"
    new_text = "header\nbadge 4.0.3\nfooter\n"

    # When
    hunks = diff_hunks(old_text, new_text)

    # Then
    assert hunks == [("badge 4.0.2\n", "badge 4.0.3\n")]


def test_insertion_keeps_context_to_detect_reapplication() -> None:
    # Given
    old_text = "first\nlast\n"
    new_text = "first\nadded\nlast\n"

    # When
    hunks = diff_hunks(old_text, new_text)

    # Then
    assert hunks == [("first\nlast\n", "first\nadded\nlast\n")]


def test_hunks_stay_unique_while_earlier_hunks_are_applied(
    tmp_path: Path,
) -> None:
    # Given a change that moves "Pull" up and replaces the old "Pull", so
    # once the first hunk is in, "Pull" alone occurs twice (nf-core/tools
    # 1.10 did this to ci.yml)
    old_text = "A\nX1\nX2\nX3\nPull\nC\n"
    new_text = "A\nPull\nX1\nX2\nX3\nRun\nC\n"
    (tmp_path / "ci.yml").write_text(old_text)
    workspace = Workspace(tmp_path)

    # When
    hunks = diff_hunks(old_text, new_text)
    outcomes = [
        Replace("ci.yml", old, new).apply(workspace).outcome
        for old, new in hunks
    ]

    # Then
    assert outcomes == [Outcome.APPLIED] * len(hunks)
    assert workspace.read("ci.yml") == new_text


def test_a_hunk_reads_as_already_applied_on_the_new_template(
    tmp_path: Path,
) -> None:
    # Given an insertion whose context before it is also how the new text
    # starts (nf-core/tools 1.11 did this to docs/output.md)
    old_text = "# Output\n\nThis document\n\n* `multiqc/`\n"
    new_text = "# Output\n\n## warning\n\nThis document\n\n* `multiqc/`\n"
    (tmp_path / "output.md").write_text(new_text)
    workspace = Workspace(tmp_path)

    # When the hunks run again on the updated file
    hunks = diff_hunks(old_text, new_text)
    outcomes = [
        Replace("output.md", old, new).apply(workspace).outcome
        for old, new in hunks
    ]

    # Then
    assert outcomes == [Outcome.ALREADY_APPLIED] * len(hunks)
    assert workspace.read("output.md") == new_text


def test_an_insertion_ending_like_its_context_keeps_small_context(
    tmp_path: Path,
) -> None:
    # Given a step inserted before a job, ending in the blank line that also
    # precedes it (nf-core/tools 4.0.3 did this to nf-test.yml)
    old_text = (
        "jobs:\n  test:\n    steps:\n      - run: a\n\n"
        "  confirm:\n    needs: [test]\n"
    )
    new_text = (
        "jobs:\n  test:\n    steps:\n      - run: a\n\n"
        "      - name: upload\n        run: c\n\n"
        "  confirm:\n    needs: [test]\n"
    )
    (tmp_path / "nf-test.yml").write_text(new_text)

    # When
    hunks = diff_hunks(old_text, new_text)
    rerun = [
        Replace("nf-test.yml", old, new).apply(Workspace(tmp_path)).outcome
        for old, new in hunks
    ]

    # Then the hunk does not grow into lines a pipeline may have changed
    assert hunks == [
        (
            "\n  confirm:\n",
            "\n      - name: upload\n        run: c\n\n  confirm:\n",
        )
    ]
    assert rerun == [Outcome.ALREADY_APPLIED]


# Renders of releases before nf-core/tools 3.0
RENDER_METADATA_2_2 = """\
nf_core_version: '2.2'
template:
  name: sentinelpipe
  description: Sentinel pipeline description
"""
RENDER_METADATA_2_3 = RENDER_METADATA_2_2.replace("'2.2'", "'2.3'")


def test_legacy_render_metadata_stays_out_of_the_migration(
    tmp_path: Path,
) -> None:
    # Given 2.2 rendered no .nf-core.yml and 2.3 a bare one, with the
    # render's version and values kept beside them
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo,
        {
            ".nf-migrate-render.yml": RENDER_METADATA_2_2,
            "README.md": "# nf-core/sentinelpipe\n",
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-migrate-render.yml": RENDER_METADATA_2_3,
            ".nf-core.yml": "repository_type: pipeline\n",
            "README.md": "# nf-core/sentinelpipe\n\nSentinel pipeline\n",
        },
    )

    # And a pipeline from before nf-core/tools wrote .nf-core.yml
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / "README.md").write_text("# nf-core/slamseq\n")
    (pipeline / "nextflow.config").write_text(
        "manifest {\n  name = 'nf-core/slamseq'\n}\n"
    )

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "v2_3.py").write_text(generated.source)
    report = upgrade(
        pipeline, load_migrations(migrations_dir), target="head", current="2.2"
    )

    # Then
    assert generated.revision == "2.3"
    assert generated.down_revision == "2.2"
    assert ".nf-migrate-render.yml" not in generated.source
    assert report.succeeded, report.render()
    assert (pipeline / ".nf-core.yml").read_text() == (
        "nf_core_version: '2.3'\nrepository_type: pipeline\n"
    )
    assert (pipeline / "README.md").read_text() == (
        "# nf-core/slamseq\n\nSentinel pipeline\n"
    )


# Changes a release made by mistake
def test_a_release_note_leaked_into_the_changelog_is_left_out(
    tmp_path: Path,
) -> None:
    # Given 2.3.1, which put an nf-core/tools release note into CHANGELOG.md
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    changelog = "## v1.0dev\n\n### `Fixed`\n\n{}### `Dependencies`\n"
    old_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: '2.3'\n",
            "CHANGELOG.md": changelog.format(""),
            "main.nf": "workflow {}\n",
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 2.3.1\n",
            "CHANGELOG.md": changelog.format(
                "- Clarified conda usage and added a tutorial\n\n"
            ),
            "main.nf": "workflow { main: }\n",
        },
    )

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)

    # Then
    assert "'CHANGELOG.md'," not in generated.source
    assert "# Left out: 2.3.1 added 'Clarified conda usage'" in generated.source
    assert "workflow { main: }" in generated.source


def test_release_notes_go_into_the_migration_docstring(
    tmp_path: Path,
) -> None:
    # Given two renders and the nf-core/tools CHANGELOG
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo,
        {".nf-core.yml": "nf_core_version: 4.0.3\n", "a.txt": "old\n"},
    )
    new_ref = commit_files(
        template_repo,
        {".nf-core.yml": "nf_core_version: 4.1.0\n", "a.txt": "new\n"},
    )
    changelog = (
        "## [v4.1.0 - Marshalled Mamba](https://example.org) - [2026-07-29]\n"
        "\n"
        "### Template\n"
        "\n"
        '- Use `\\d` in a regex, not a """docstring"""\n'
    )

    # When
    generated = generate_migration(
        template_repo, old_ref, new_ref, changelog=changelog
    )
    namespace: dict = {}
    exec(compile(generated.source, "v4_1_0.py", "exec"), namespace)

    # Then
    assert namespace["__doc__"] == (
        "Template update for nf-core/tools 4.1.0.\n"
        "\n"
        "nf-core/tools CHANGELOG, Template section of\n"
        "[v4.1.0 - Marshalled Mamba](https://example.org) - [2026-07-29]:\n"
        "\n"
        '- Use `\\d` in a regex, not a """docstring"""\n'
        "\n"
        "Generated by nf-migrate; edit freely.\n"
    )


def test_a_large_deletion_removes_the_paragraphs_a_pipeline_kept(
    tmp_path: Path,
) -> None:
    # Given a template release that drops three sections of usage.md
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    sections = (
        "## Job resources\n\nEach step has defaults.\n\n"
        "## AWS Batch\n\nUse the awsbatch profile.\n\n"
        "## Other parameters\n\nSet --outdir.\n\n"
    )
    old_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 1.9\n",
            "usage.md": f"# Usage\n\n{sections}## -resume\n",
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 1.10\n",
            "usage.md": "# Usage\n\n## -resume\n",
        },
    )

    # And a pipeline that rewrote the AWS section but kept the others
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / ".nf-core.yml").write_text("nf_core_version: 1.9\n")
    customised = sections.replace(
        "Use the awsbatch profile.", "We run on our own cluster."
    )
    (pipeline / "usage.md").write_text(f"# Usage\n\n{customised}## -resume\n")

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "v1_10.py").write_text(generated.source)
    report = upgrade(pipeline, load_migrations(migrations_dir), target="head")

    # Then
    assert report.succeeded, report.render()
    assert (pipeline / "usage.md").read_text() == (
        "# Usage\n\n## AWS Batch\n\nWe run on our own cluster.\n\n## -resume\n"
    )


def _two_renders(tmp_path: Path, path: str, old: str, new: str) -> tuple:
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo, {".nf-core.yml": "nf_core_version: 4.0.3\n", path: old}
    )
    new_ref = commit_files(
        template_repo, {".nf-core.yml": "nf_core_version: 4.1.0\n", path: new}
    )
    return template_repo, old_ref, new_ref


def _upgrade_with(tmp_path: Path, source: str, files: dict[str, str]):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "v4_1_0.py").write_text(source)
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / ".nf-core.yml").write_text("nf_core_version: 4.0.3\n")
    for relative_path, content in files.items():
        file_path = pipeline / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    report = upgrade(pipeline, load_migrations(migrations_dir), target="head")
    return pipeline, report


def test_a_workflow_step_change_follows_the_step_not_its_lines(
    tmp_path: Path,
) -> None:
    # Given a template release bumping an action in one CI step
    workflow = (
        "jobs:\n  lint:\n    steps:\n"
        "      - name: Check out\n        uses: actions/checkout@v4\n"
        "      - name: Lint\n        run: nf-core lint\n"
    )
    repo, old_ref, new_ref = _two_renders(
        tmp_path,
        ".github/workflows/linting.yml",
        workflow,
        workflow.replace("checkout@v4", "checkout@v5"),
    )

    # And a pipeline with its own step before the template's
    customised = workflow.replace(
        "    steps:\n",
        "    steps:\n      - name: Our setup\n        run: make\n",
    )

    # When
    generated = generate_migration(repo, old_ref, new_ref)
    pipeline, report = _upgrade_with(
        tmp_path,
        generated.source,
        {".github/workflows/linting.yml": customised},
    )

    # Then
    assert "YamlSet(" in generated.source
    assert report.succeeded, report.render()
    assert (pipeline / ".github/workflows/linting.yml").read_text() == (
        customised.replace("checkout@v4", "checkout@v5")
    )


def test_a_version_bump_survives_edits_to_the_rest_of_its_line(
    tmp_path: Path,
) -> None:
    # Given a template release bumping a plugin
    repo, old_ref, new_ref = _two_renders(
        tmp_path,
        "nextflow.config",
        "plugins {\n    id 'nf-schema@2.1.1' // Validation\n}\n",
        "plugins {\n    id 'nf-schema@2.3.0' // Validation\n}\n",
    )

    # When the pipeline wrote its own comment
    generated = generate_migration(repo, old_ref, new_ref)
    pipeline, report = _upgrade_with(
        tmp_path,
        generated.source,
        {"nextflow.config": "plugins {\n    id 'nf-schema@2.1.1' // ours\n}\n"},
    )

    # Then
    assert "BumpVersion(" in generated.source
    assert report.succeeded, report.render()
    assert (pipeline / "nextflow.config").read_text() == (
        "plugins {\n    id 'nf-schema@2.3.0' // ours\n}\n"
    )


def test_a_deleted_code_block_is_not_split_into_unbalanced_paragraphs(
    tmp_path: Path,
) -> None:
    # Given a template release that drops a block holding a blank line
    help_block = (
        "validation {\n"
        "    help {\n"
        '        afterText = """\n'
        "* The pipeline\n"
        "\n"
        "* Software dependencies\n"
        '"""\n'
        "    }\n"
        "}\n"
        "\n"
    )
    repo, old_ref, new_ref = _two_renders(
        tmp_path,
        "nextflow.config",
        f"params {{}}\n\n{help_block}// Load modules\n",
        "params {}\n\n// Load modules\n",
    )

    # And a pipeline that edited the second half of it
    customised = help_block.replace("* Software dependencies", "* Our tools")

    # When
    generated = generate_migration(repo, old_ref, new_ref)
    pipeline, report = _upgrade_with(
        tmp_path,
        generated.source,
        {"nextflow.config": f"params {{}}\n\n{customised}// Load modules\n"},
    )

    # Then the block stays whole, for a maintainer to remove
    assert not report.succeeded
    assert (pipeline / "nextflow.config").read_text() == (
        f"params {{}}\n\n{customised}// Load modules\n"
    )
