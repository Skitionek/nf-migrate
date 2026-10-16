import hashlib
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


# JSON files
SCHEMA_OLD = """\
{
    "properties": {
        "igenomes_base": {
            "type": "string",
            "format": "directory-path"
        },
        "hook_url": {
            "type": "string"
        },
        "multiqc_config": {
            "type": "string"
        }
    }
}
"""
SCHEMA_NEW = """\
{
    "properties": {
        "igenomes_base": {
            "type": "string"
        },
        "multiqc_config": {
            "type": "string"
        },
        "trace_report_suffix": {
            "type": "string"
        }
    }
}
"""


def test_json_changes_apply_by_key_beside_pipeline_parameters(
    tmp_path: Path,
) -> None:
    # Given a template release that edits, removes and adds properties
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    old_ref = commit_files(
        template_repo,
        {".nf-core.yml": "nf_core_version: 3.2.1\n", "schema.json": SCHEMA_OLD},
    )
    new_ref = commit_files(
        template_repo,
        {".nf-core.yml": "nf_core_version: 3.3.1\n", "schema.json": SCHEMA_NEW},
    )

    # And a pipeline that added its own parameter between them
    pipeline_schema = SCHEMA_OLD.replace(
        '        "hook_url": {',
        '        "my_param": {\n            "type": "integer"\n        },\n'
        '        "hook_url": {',
    )
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / ".nf-core.yml").write_text("nf_core_version: 3.2.1\n")
    (pipeline / "schema.json").write_text(pipeline_schema)

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "v3_3_1.py").write_text(generated.source)
    report = upgrade(pipeline, load_migrations(migrations_dir), target="head")

    # Then
    assert "JsonEdit(" in generated.source
    assert report.succeeded, report.render()
    expected = SCHEMA_NEW.replace(
        '        "multiqc_config": {',
        '        "my_param": {\n            "type": "integer"\n        },\n'
        '        "multiqc_config": {',
    )
    assert (pipeline / "schema.json").read_text() == expected


def test_json_changes_fall_back_to_text_where_the_pipeline_renamed_keys(
    tmp_path: Path,
) -> None:
    # Given a template release that changes a property's pattern
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    schema = (
        '{{\n    "properties": {{\n        "fastq_1": {{\n'
        '            "pattern": "{}",\n'
        '            "errorMessage": "FastQ file for reads 1"\n'
        "        }}\n    }}\n}}\n"
    )
    old_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 3.3.1\n",
            "schema.json": schema.format("old"),
        },
    )
    new_ref = commit_files(
        template_repo,
        {
            ".nf-core.yml": "nf_core_version: 3.3.2\n",
            "schema.json": schema.format("new"),
        },
    )

    # And a pipeline that named the property differently
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / ".nf-core.yml").write_text("nf_core_version: 3.3.1\n")
    (pipeline / "schema.json").write_text(
        schema.format("old").replace("fastq_1", "forward_reads")
    )

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "v3_3_2.py").write_text(generated.source)
    report = upgrade(pipeline, load_migrations(migrations_dir), target="head")

    # Then
    assert "JsonEdit(" in generated.source
    assert report.succeeded, report.render()
    assert (pipeline / "schema.json").read_text() == (
        schema.format("new").replace("fastq_1", "forward_reads")
    )


# Binary files
def commit_binary_files(repo: Path, files: dict[str, bytes | None]) -> str:
    for relative_path, content in files.items():
        file_path = repo / relative_path
        if content is None:
            file_path.unlink()
            continue
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "template")
    return git(repo, "rev-parse", "HEAD")


def test_binary_files_are_deleted_by_hash_and_logos_regenerated(
    tmp_path: Path,
) -> None:
    # Given a release that deletes an example image and redraws the logo
    template_repo = tmp_path / "template"
    template_repo.mkdir()
    git(template_repo, "init", "-q")
    git(template_repo, "config", "user.email", "t@example.com")
    git(template_repo, "config", "user.name", "t")
    nf_core_yml = "nf_core_version: {}\ntemplate:\n  name: sentinelpipe\n"
    image = b"\x89PNG\r\n\x1a\n\x00\xff example"
    old_ref = commit_binary_files(
        template_repo,
        {
            ".nf-core.yml": nf_core_yml.format("3.2.1").encode(),
            "docs/images/mqc.png": image,
            "docs/images/nf-core-sentinelpipe_logo.png": b"\x89PNG\x00 old",
        },
    )
    new_ref = commit_binary_files(
        template_repo,
        {
            ".nf-core.yml": nf_core_yml.format("3.3.1").encode(),
            "docs/images/mqc.png": None,
            "docs/images/nf-core-sentinelpipe_logo.png": b"\x89PNG\x00 new",
        },
    )

    # When
    generated = generate_migration(template_repo, old_ref, new_ref)

    # Then
    image_sha = hashlib.sha256(image).hexdigest()
    assert "DeleteBinaryFile(" in generated.source
    assert image_sha in generated.source
    assert "nf-core-{{pipeline_name}}_logo.png" in generated.source
    assert "nf-core pipelines create-logo" in generated.source


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
