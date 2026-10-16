"""Idempotent file operations that a migration is made of.

Every operation inspects the pipeline before changing it and reports one of
three outcomes. Running an operation twice is safe: the second run sees the
new text and reports ALREADY_APPLIED. Anything the operation cannot place
unambiguously is a CONFLICT for a human to resolve.
"""

import difflib
import enum
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nf_migrate.variables import expand


class Outcome(enum.Enum):
    APPLIED = "applied"
    ALREADY_APPLIED = "already applied"
    CONFLICT = "conflict"
    # Work nf-migrate leaves to nf-core's own tooling. Reported, not blocking.
    MANUAL = "manual step"


@dataclass(frozen=True, slots=True)
class OperationResult:
    path: str
    outcome: Outcome
    message: str = ""
    # The template change as a diff; reports show it for conflicts, so a
    # maintainer can apply it by hand.
    suggestion: str = ""


class Workspace:
    """In-memory view of a pipeline directory.

    Operations read and write here, so a migration that hits a conflict can
    be dropped without having touched any file on disk.
    """

    def __init__(
        self, root: Path, variables: dict[str, str] | None = None
    ) -> None:
        self.root = root
        self.variables = variables or {}
        self._pending: dict[str, str | None] = {}

    def expand(self, text: str) -> str:
        """Fill a migration's {{placeholders}} with this pipeline's values."""
        return expand(text, self.variables)

    def read(self, path: str) -> str | None:
        if path in self._pending:
            return self._pending[path]
        return self._read_from_disk(path)

    def write(self, path: str, content: str) -> None:
        self._pending[path] = content

    def delete(self, path: str) -> None:
        self._pending[path] = None

    def snapshot(self) -> dict[str, str | None]:
        return dict(self._pending)

    def restore(self, snapshot: dict[str, str | None]) -> None:
        self._pending = dict(snapshot)

    def restore_paths(
        self, snapshot: dict[str, str | None], paths: set[str]
    ) -> None:
        """Undo changes to `paths` made since `snapshot`."""
        for path in paths:
            if path in snapshot:
                self._pending[path] = snapshot[path]
            else:
                self._pending.pop(path, None)

    def changed_paths(self) -> list[str]:
        return [
            path
            for path, content in sorted(self._pending.items())
            if content != self._read_from_disk(path)
        ]

    def diff(self) -> str:
        diff_parts: list[str] = []
        for path in self.changed_paths():
            before = self._read_from_disk(path) or ""
            after = self._pending[path] or ""
            diff_lines = difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
            diff_parts.append("".join(diff_lines))
        return "".join(diff_parts)

    def commit(self) -> None:
        for path, content in self._pending.items():
            file_path = self.root / path
            if content is None:
                file_path.unlink(missing_ok=True)
                continue
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
        self._pending.clear()

    def _read_from_disk(self, path: str) -> str | None:
        file_path = self.root / path
        if not file_path.is_file():
            return None
        return file_path.read_text()


def _change_diff(path: str, old: str, new: str) -> str:
    diff_lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff_lines)


def _is_inside_match(
    position: int, length: int, match_positions: list[int], match: str
) -> bool:
    return any(
        start <= position and position + length <= start + len(match)
        for start in match_positions
    )


def find_line_aligned(content: str, text: str) -> list[int]:
    """Start offsets where `text` occurs beginning at the start of a line.

    Without this, a hunk for "line 3" would also match inside "line 13".
    """
    positions: list[int] = []
    start = content.find(text)
    while start != -1:
        if start == 0 or content[start - 1] == "\n":
            positions.append(start)
        start = content.find(text, start + 1)
    return positions


class Operation(Protocol):
    """Anything a migration lists in `operations`.

    Migrations may define their own operation classes for changes that a
    text replacement cannot express, as long as they follow this protocol.
    """

    path: str

    def apply(self, workspace: Workspace) -> OperationResult: ...


@dataclass(frozen=True, slots=True)
class Replace:
    """Replace one exact block of text, usually a template diff hunk."""

    path: str
    old: str
    new: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        old = workspace.expand(self.old)
        new = workspace.expand(self.new)

        change = _change_diff(path, old, new)

        content = workspace.read(path)
        if content is None:
            message = "file does not exist"
            return OperationResult(path, Outcome.CONFLICT, message, change)

        old_positions = find_line_aligned(content, old)
        new_positions = find_line_aligned(content, new) if new else []
        # When the template appended to the end of the old text, the new
        # text contains the old; a match inside the new text is the change
        # already made, not a place to make it again.
        old_positions = [
            position
            for position in old_positions
            if not _is_inside_match(position, len(old), new_positions, new)
        ]
        if not old_positions and new_positions:
            return OperationResult(path, Outcome.ALREADY_APPLIED, "", change)
        if len(old_positions) == 1:
            start = old_positions[0]
            end = start + len(old)
            workspace.write(path, content[:start] + new + content[end:])
            return OperationResult(path, Outcome.APPLIED, "", change)
        if len(old_positions) > 1:
            message = f"old text found {len(old_positions)} times"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        message = "old text not found"
        return OperationResult(path, Outcome.CONFLICT, message, change)


@dataclass(frozen=True, slots=True)
class CreateFile:
    path: str
    content: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        content = workspace.expand(self.content)

        existing = workspace.read(path)
        if existing is None:
            workspace.write(path, content)
            return OperationResult(path, Outcome.APPLIED)
        if existing == content:
            return OperationResult(path, Outcome.ALREADY_APPLIED)
        message = "file exists with different content"
        return OperationResult(path, Outcome.CONFLICT, message)


@dataclass(frozen=True, slots=True)
class DeleteFile:
    """Delete a template file, but only if the pipeline left it untouched."""

    path: str
    expected_content: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        expected_content = workspace.expand(self.expected_content)

        existing = workspace.read(path)
        if existing is None:
            return OperationResult(path, Outcome.ALREADY_APPLIED)
        if existing == expected_content:
            workspace.delete(path)
            return OperationResult(path, Outcome.APPLIED)
        message = "file was modified locally"
        return OperationResult(path, Outcome.CONFLICT, message)


@dataclass(frozen=True, slots=True)
class ManualStep:
    """A change nf-core's own tooling makes better than a text patch."""

    path: str
    instruction: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        return OperationResult(path, Outcome.MANUAL, self.instruction)


NF_CORE_MODULES_REPO = "https://github.com/nf-core/modules.git"


@dataclass(frozen=True, slots=True)
class NfCoreComponent:
    """An nf-core module or subworkflow the template pins at `git_sha`.

    Pipelines update these with `nf-core modules update`, often past the
    template's version, so patching their files would conflict. Instead
    this compares modules.json and names the command to run. A `git_sha`
    of None means the template dropped the component.
    """

    kind: str
    name: str
    git_sha: str | None
    path: str = "modules.json"

    def apply(self, workspace: Workspace) -> OperationResult:
        try:
            installed_sha = self._installed_sha(workspace)
        except json.JSONDecodeError:
            message = f"{self.path} is not valid JSON"
            return self._result(Outcome.CONFLICT, message)
        command = f"nf-core {self.kind}"

        if self.git_sha is None:
            if installed_sha is None:
                return self._result(Outcome.ALREADY_APPLIED)
            message = f"template dropped it: `{command} remove {self.name}`"
            return self._result(Outcome.MANUAL, message)

        if installed_sha == self.git_sha:
            return self._result(Outcome.ALREADY_APPLIED)
        if installed_sha is None:
            message = (
                f"not installed: `{command} install {self.name}` "
                f"(template has {self.git_sha})"
            )
            return self._result(Outcome.MANUAL, message)
        message = (
            f"pipeline has {installed_sha}, template {self.git_sha}: "
            f"`{command} update {self.name}` if yours is older"
        )
        return self._result(Outcome.MANUAL, message)

    def _installed_sha(self, workspace: Workspace) -> str | None:
        content = workspace.read(self.path)
        if content is None:
            return None
        repos = json.loads(content).get("repos", {})
        components = (
            repos.get(NF_CORE_MODULES_REPO, {})
            .get(self.kind, {})
            .get("nf-core", {})
        )
        entry = components.get(self.name)
        if entry is None:
            return None
        return entry.get("git_sha")

    def _result(self, outcome: Outcome, message: str = "") -> OperationResult:
        return OperationResult(
            f"{self.kind}/nf-core/{self.name}", outcome, message
        )
