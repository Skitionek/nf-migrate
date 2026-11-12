import re
from pathlib import Path

from nf_migrate.migrations import Migration, load_migrations
from nf_migrate.runner import UpgradeReport, upgrade
from nf_migrate.version import stamp_version

BUNDLED_MIGRATIONS = (
    Path(__file__).parent.parent / "src/nf_migrate/nf_core_migrations"
)
NF_CORE_YML = (
    "nf_core_version: 2.14.1\n"
    "repository_type: pipeline\n"
    "template:\n"
    "  name: demo\n"
    "  author: me\n"
    "  description: demo pipeline\n"
    "  version: 1.0.0dev\n"
)
SNAKE_CASE = ".github/workflows/template_version_comment.yml"
KEBAB_CASE = ".github/workflows/template-version-comment.yml"
# What the template's own workflow has: its checkout takes the PR head.
HEAD_CHECKOUT = (
    "        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n"
)
CHECKOUT_STEP = re.compile(
    r"^( +- name: Check out pipeline code\n +uses: [^\n]*\n)", re.MULTILINE
)


def is_privileged_head_checkout(workflow: str) -> bool:
    """A pull_request_target workflow (base secrets, a write token even for
    fork PRs) that reads the pull request's head, which a fork controls."""
    on_pull_request_target = re.search(
        r"^on:[ \t]*pull_request_target[ \t]*$", workflow, re.MULTILINE
    )
    return bool(on_pull_request_target) and "pull_request.head" in workflow


def with_head_checkout(workflow: str) -> str:
    if HEAD_CHECKOUT in workflow:
        return workflow
    return CHECKOUT_STEP.sub(lambda m: m.group(1) + HEAD_CHECKOUT, workflow)


def read_workflows(project: Path) -> dict[str, str]:
    return {
        path: (project / path).read_text()
        for path in (SNAKE_CASE, KEBAB_CASE)
        if (project / path).exists()
    }


def conflicting_paths(report: UpgradeReport) -> set[str]:
    return {
        result.path
        for migration in report.migrations
        for result in migration.conflicts
        if result.path in (SNAKE_CASE, KEBAB_CASE)
    }


def upgrade_to(
    project: Path, chain: list[Migration], revision: str
) -> UpgradeReport:
    return upgrade(project, chain, target=revision, allow_conflicts=True)


def releases_after(chain: list[Migration], revision: str) -> list[str]:
    revisions = [migration.revision for migration in chain]
    return revisions[revisions.index(revision) + 1 :]


def test_created_version_comment_workflow_never_checks_out_pr_head(
    tmp_path: Path,
) -> None:
    # Given a pipeline from before the workflow existed
    chain = load_migrations(BUNDLED_MIGRATIONS)
    (tmp_path / ".nf-core.yml").write_text(NF_CORE_YML)

    # When it is upgraded release by release
    privileged = []
    pull_request_target_seen = False
    for revision in releases_after(chain, "2.14.1"):
        report = upgrade_to(tmp_path, chain, revision)
        assert not conflicting_paths(report), revision
        for path, workflow in read_workflows(tmp_path).items():
            pull_request_target_seen |= "pull_request_target" in workflow
            if is_privileged_head_checkout(workflow):
                privileged.append((revision, path))

    # Then no release leaves the privileged workflow reading the PR head
    assert pull_request_target_seen
    assert privileged == []


def test_templates_head_checkout_is_dropped_when_the_workflow_is_renamed(
    tmp_path: Path,
) -> None:
    # Given a pipeline on the template's 3.2.1 workflow, with its PR head
    # checkout
    chain = load_migrations(BUNDLED_MIGRATIONS)
    (tmp_path / ".nf-core.yml").write_text(NF_CORE_YML)
    upgrade_to(tmp_path, chain, "3.2.1")
    template_workflow = with_head_checkout((tmp_path / SNAKE_CASE).read_text())
    assert is_privileged_head_checkout(template_workflow)
    (tmp_path / SNAKE_CASE).write_text(template_workflow)

    # When it is upgraded to 3.3.0, which renames the workflow
    report = upgrade_to(tmp_path, chain, "3.3.0")

    # Then the old file is gone and the new one does not read the PR head
    assert not conflicting_paths(report)
    assert not (tmp_path / SNAKE_CASE).exists()
    assert not is_privileged_head_checkout((tmp_path / KEBAB_CASE).read_text())


def test_templates_renamed_workflow_is_left_as_the_pipeline_has_it(
    tmp_path: Path,
) -> None:
    # Given a pipeline stamped 3.2.1 that already has the template's 3.3.0
    # workflow, with its PR head checkout
    chain = load_migrations(BUNDLED_MIGRATIONS)
    (tmp_path / ".nf-core.yml").write_text(NF_CORE_YML)
    upgrade_to(tmp_path, chain, "3.3.0")
    template_workflow = with_head_checkout((tmp_path / KEBAB_CASE).read_text())
    (tmp_path / KEBAB_CASE).write_text(template_workflow)
    nf_core_yml = tmp_path / ".nf-core.yml"
    nf_core_yml.write_text(stamp_version(nf_core_yml.read_text(), "3.2.1"))

    # When it is upgraded to 3.3.0 again
    report = upgrade_to(tmp_path, chain, "3.3.0")

    # Then the file is not a conflict, and is not rewritten
    assert not conflicting_paths(report)
    assert (tmp_path / KEBAB_CASE).read_text() == template_workflow
