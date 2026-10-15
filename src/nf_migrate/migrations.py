"""Discover migration modules and order them into a single chain."""

import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from nf_migrate.operations import Operation


class MigrationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Migration:
    revision: str
    down_revision: str | None
    operations: Sequence[Operation]
    source: Path


def load_migrations(directory: Path) -> list[Migration]:
    """Load every `*.py` migration and return them oldest first."""
    migrations = [
        _load_migration_file(path) for path in sorted(directory.glob("*.py"))
    ]
    return _order_chain(migrations)


def _load_migration_file(path: Path) -> Migration:
    spec = importlib.util.spec_from_file_location(
        f"_migration_{path.stem}", path
    )
    if spec is None or spec.loader is None:
        raise MigrationError(f"cannot import migration {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for attribute in ("revision", "down_revision", "operations"):
        if not hasattr(module, attribute):
            raise MigrationError(f"{path} does not define `{attribute}`")

    return Migration(
        revision=module.revision,
        down_revision=module.down_revision,
        operations=module.operations,
        source=path,
    )


def _order_chain(migrations: list[Migration]) -> list[Migration]:
    if not migrations:
        return []

    by_down_revision: dict[str | None, Migration] = {}
    for migration in migrations:
        sibling = by_down_revision.get(migration.down_revision)
        if sibling is not None:
            raise MigrationError(
                f"{sibling.revision} and {migration.revision} both upgrade "
                f"from {migration.down_revision}"
            )
        by_down_revision[migration.down_revision] = migration

    known_revisions = {migration.revision for migration in migrations}
    roots = [
        migration
        for migration in migrations
        if migration.down_revision not in known_revisions
    ]
    if len(roots) != 1:
        root_names = ", ".join(root.revision for root in roots)
        raise MigrationError(
            f"expected one first migration, found {root_names}"
        )

    chain = [roots[0]]
    while chain[-1].revision in by_down_revision:
        chain.append(by_down_revision[chain[-1].revision])
    return chain


def pending_migrations(
    chain: list[Migration], current: str | None, target: str
) -> list[Migration]:
    """Migrations that take `current` to `target` ("head" is the newest)."""
    revisions = [migration.revision for migration in chain]
    target_index = len(chain) - 1 if target == "head" else None
    if target_index is None:
        if target not in revisions:
            raise MigrationError(f"unknown target revision {target}")
        target_index = revisions.index(target)

    if current in revisions:
        start_index = revisions.index(current) + 1
    elif chain and current == chain[0].down_revision:
        start_index = 0
    else:
        raise MigrationError(
            f"current version {current} is not part of the migration chain"
        )

    if start_index > target_index + 1:
        raise MigrationError(
            f"{current} is newer than {target}; only upgrades are supported"
        )
    return chain[start_index : target_index + 1]
