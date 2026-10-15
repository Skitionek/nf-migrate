import json
import subprocess
from pathlib import Path

from nf_migrate.autogenerate import generate_migration
from nf_migrate.migrations import load_migrations
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
