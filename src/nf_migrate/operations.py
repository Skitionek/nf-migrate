"""Idempotent file operations that a migration is made of.

Every operation inspects the pipeline before changing it and reports one of
three outcomes. Running an operation twice is safe: the second run sees the
new text and reports ALREADY_APPLIED. Anything the operation cannot place
unambiguously is a CONFLICT for a human to resolve.
"""

import difflib
import enum
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nf_migrate import json_text
from nf_migrate.variables import expand

# How a binary file reads as text; no template text matches it.
BINARY_FILE_TEXT = "<binary file>\n"


class Outcome(enum.Enum):
    APPLIED = "applied"
    ALREADY_APPLIED = "already applied"
    CONFLICT = "conflict"
    # Work nf-migrate leaves to nf-core's own tooling. Reported, not blocking.
    MANUAL = "manual step"
    # A template change that did not fit a file the pipeline owns, such as
    # its README. Reported with the change, not blocking.
    SUGGESTED = "suggested"


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

    def read_bytes(self, path: str) -> bytes | None:
        if path in self._pending:
            content = self._pending[path]
            return None if content is None else content.encode()
        file_path = self.root / path
        if not file_path.is_file():
            return None
        return file_path.read_bytes()

    def _read_from_disk(self, path: str) -> str | None:
        file_path = self.root / path
        if not file_path.is_file():
            return None
        try:
            return file_path.read_text()
        except UnicodeDecodeError:
            # Text operations then see a file they cannot match, and a
            # dry-run diff shows the binary file going away.
            return BINARY_FILE_TEXT


def _change_diff(path: str, old: str, new: str) -> str:
    diff_lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(diff_lines)


def is_inside_match(
    position: int, length: int, match_positions: list[int], match: str
) -> bool:
    """Whether [position, position + length) lies within a match."""
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
            if not is_inside_match(position, len(old), new_positions, new)
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
        return _replace_ignoring_whitespace(workspace, path, old, new, change)


@dataclass(frozen=True, slots=True)
class WhitespaceMatch:
    """Lines [first_line, end_line) equal a block up to whitespace."""

    first_line: int
    end_line: int
    # How many spaces deeper the pipeline indents the block.
    indent_shift: int


def _replace_ignoring_whitespace(
    workspace: Workspace, path: str, old: str, new: str, change: str
) -> OperationResult:
    """Fall back to matching lines without their surrounding whitespace.

    Pipelines often re-indent or reformat template blocks. A match only
    counts when every line moved by the same indentation, and the new text
    is re-indented by that amount, so nesting (YAML, Groovy) stays intact.
    """
    content = workspace.read(path) or ""
    old_matches = find_ignoring_whitespace(content, old)
    new_matches = find_ignoring_whitespace(content, new) if new else []

    if not old_matches and new_matches:
        message = "already applied, up to whitespace"
        return OperationResult(path, Outcome.ALREADY_APPLIED, message, change)
    if len(old_matches) == 1:
        match = old_matches[0]
        lines = content.splitlines(keepends=True)
        reindented = reindent(new, match.indent_shift)
        updated = lines[: match.first_line] + [reindented]
        updated += lines[match.end_line :]
        workspace.write(path, "".join(updated))
        message = "matched ignoring whitespace"
        return OperationResult(path, Outcome.APPLIED, message, change)
    if len(old_matches) > 1:
        message = f"old text found {len(old_matches)} times ignoring whitespace"
        return OperationResult(path, Outcome.CONFLICT, message, change)

    anchored = _replace_anchored_on_one_side(workspace, path, old, new, change)
    if anchored is not None:
        return anchored
    message = "old text not found"
    return OperationResult(path, Outcome.CONFLICT, message, change)


def _replace_anchored_on_one_side(
    workspace: Workspace, path: str, old: str, new: str, change: str
) -> OperationResult | None:
    """Fall back to the context on one side of the change only.

    A hunk keeps context lines around its change, and a pipeline that edited
    the lines on one side (say, added its own keys after the template's)
    breaks the match although the change itself still fits. Dropping that
    side keeps the match exact and unique on the other; a side made only of
    punctuation, like a closing brace, is too weak to anchor on.
    """
    content = workspace.read(path) or ""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    shared_before = _shared_prefix_length(old_lines, new_lines)
    shared_after = _shared_prefix_length(
        old_lines[shared_before:][::-1], new_lines[shared_before:][::-1]
    )
    context_before = old_lines[:shared_before]
    context_after = old_lines[len(old_lines) - shared_after :]
    removed = old_lines[shared_before : len(old_lines) - shared_after]
    added = new_lines[shared_before : len(new_lines) - shared_after]

    candidates = []
    if shared_after and _is_substantial(context_before):
        candidates.append(
            (context_before + removed, context_before + added, "before")
        )
    if shared_before and _is_substantial(context_after):
        candidates.append(
            (removed + context_after, added + context_after, "after")
        )

    for old_part_lines, new_part_lines, side in candidates:
        old_part = "".join(old_part_lines)
        new_part = "".join(new_part_lines)
        new_positions = find_line_aligned(content, new_part)
        old_positions = [
            position
            for position in find_line_aligned(content, old_part)
            if not is_inside_match(
                position, len(old_part), new_positions, new_part
            )
        ]
        # Without added lines the new part is only the anchor, which proves
        # nothing about whether the change was made.
        if not old_positions and new_positions and added:
            message = f"already applied, anchored on the lines {side}"
            return OperationResult(
                path, Outcome.ALREADY_APPLIED, message, change
            )
        if len(old_positions) == 1:
            start = old_positions[0]
            end = start + len(old_part)
            workspace.write(path, content[:start] + new_part + content[end:])
            message = f"anchored on the lines {side} only"
            return OperationResult(path, Outcome.APPLIED, message, change)
    return None


def _shared_prefix_length(first: list[str], second: list[str]) -> int:
    length = 0
    for first_line, second_line in zip(first, second, strict=False):
        if first_line != second_line:
            break
        length += 1
    return length


def _is_substantial(lines: list[str]) -> bool:
    return any(sum(c.isalnum() for c in line) >= 3 for line in lines)


def find_ignoring_whitespace(content: str, block: str) -> list[WhitespaceMatch]:
    block_lines = block.splitlines()
    if not any(line.strip() for line in block_lines):
        return []
    content_lines = content.splitlines()
    block_stripped = [line.strip() for line in block_lines]
    content_stripped = [line.strip() for line in content_lines]

    matches: list[WhitespaceMatch] = []
    last_start = len(content_lines) - len(block_lines)
    for first_line in range(last_start + 1):
        # Cheap first-line check before building the window.
        if content_stripped[first_line] != block_stripped[0]:
            continue
        end_line = first_line + len(block_lines)
        if content_stripped[first_line:end_line] != block_stripped:
            continue
        window = content_lines[first_line:end_line]
        shift = _uniform_indent_shift(window, block_lines)
        if shift is not None:
            matches.append(WhitespaceMatch(first_line, end_line, shift))
    return matches


def _uniform_indent_shift(
    lines: list[str], block_lines: list[str]
) -> int | None:
    """The one indentation change from `block_lines` to `lines`, if any."""
    shifts = set()
    for line, block_line in zip(lines, block_lines, strict=True):
        if not block_line.strip():
            continue
        indent = line[: len(line) - len(line.lstrip())]
        block_indent = block_line[: len(block_line) - len(block_line.lstrip())]
        if indent == block_indent:
            shifts.add(0)
        elif set(indent + block_indent) <= {" "}:
            shifts.add(len(indent) - len(block_indent))
        else:
            # Tabs on one side and spaces on the other: no safe shift.
            return None
    if len(shifts) != 1:
        return None
    return shifts.pop()


def reindent(text: str, shift: int) -> str:
    """Move every non-blank line `shift` spaces right (or left)."""
    lines = []
    for line in text.splitlines(keepends=True):
        if not line.strip() or shift == 0:
            lines.append(line)
        elif shift > 0:
            lines.append(" " * shift + line)
        else:
            removable = len(line) - len(line.lstrip(" "))
            lines.append(line[min(-shift, removable) :])
    return "".join(lines)


@dataclass(frozen=True, slots=True)
class JsonEdit:
    """Set, add or remove the value at one key path of a JSON file.

    Matches by keys, not by surrounding text, so it still applies when the
    pipeline added, removed or reordered other members. `old` and `new`
    are JSON text; None means the key is absent. A new value keeps the
    template's formatting, indented to where it lands.

    Where the pipeline lacks the key path, say because it renamed a
    property, the template's text hunk over the same lines is tried
    instead, so a JSON file never does worse than with text hunks alone.
    """

    path: str
    pointer: list[str]
    old: str | None
    new: str | None
    # The member to insert after when adding; the last one if missing.
    after: str | None = None
    fallback_old: str | None = None
    fallback_new: str | None = None

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        pointer = [workspace.expand(key) for key in self.pointer]
        old = None if self.old is None else workspace.expand(self.old)
        new = None if self.new is None else workspace.expand(self.new)
        after = None if self.after is None else workspace.expand(self.after)
        change = _json_change(path, pointer, old, new)

        content = workspace.read(path)
        if content is None:
            message = "file does not exist"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        try:
            document = json_text.parse(content)
        except json_text.JsonTextError:
            message = "file is not valid JSON"
            return OperationResult(path, Outcome.CONFLICT, message, change)

        member = json_text.find_member(document, pointer)
        if len(pointer) == 1:
            parent_node = document
        else:
            parent = json_text.find_member(document, pointer[:-1])
            parent_node = parent.value if parent is not None else None
        if parent_node is None or not parent_node.is_object:
            message = f"no object at {'/'.join(pointer[:-1])}"
            return self._fall_back(workspace, path, message, change)

        current = _member_value(content, member)
        if current == _parse_value(new):
            return OperationResult(path, Outcome.ALREADY_APPLIED, "", change)
        if member is None and old is not None:
            message = f"no {'/'.join(pointer)} to change"
            return self._fall_back(workspace, path, message, change)
        if current != _parse_value(old):
            message = f"{'/'.join(pointer)} has a different value"
            return OperationResult(path, Outcome.CONFLICT, message, change)

        if new is None:
            content = json_text.delete_member(content, document, member)
        elif member is None:
            content = json_text.insert_member(
                content, parent_node, pointer[-1], new, after
            )
        else:
            content = json_text.replace_value(content, member, new)
        workspace.write(path, content)
        return OperationResult(path, Outcome.APPLIED, "", change)

    def _fall_back(
        self, workspace: Workspace, path: str, message: str, change: str
    ) -> OperationResult:
        if self.fallback_old is None:
            return OperationResult(path, Outcome.CONFLICT, message, change)
        hunk = Replace(self.path, self.fallback_old, self.fallback_new or "")
        return hunk.apply(workspace)


# Stands for a missing key when comparing values; JSON has no such value.
_ABSENT = object()


def _parse_value(value_text: str | None) -> object:
    if value_text is None:
        return _ABSENT
    return json.loads(value_text)


def _member_value(content: str, member: json_text.Member | None) -> object:
    if member is None:
        return _ABSENT
    return json.loads(content[member.value.start : member.value.end])


def _json_change(
    path: str, pointer: list[str], old: str | None, new: str | None
) -> str:
    """The edit as a small diff, for reports."""
    key_path = "/".join(pointer)
    old_text = f"{key_path}: {old}\n" if old is not None else ""
    new_text = f"{key_path}: {new}\n" if new is not None else ""
    return _change_diff(path, old_text, new_text)


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
class DeleteBinaryFile:
    """Delete a binary template file the pipeline left untouched.

    Only for files that are the same in every pipeline, such as example
    images; the SHA-256 of the template's copy tells untouched from replaced.
    """

    path: str
    sha256: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        existing = workspace.read_bytes(path)
        if existing is None:
            return OperationResult(path, Outcome.ALREADY_APPLIED)
        if hashlib.sha256(existing).hexdigest() == self.sha256:
            workspace.delete(path)
            return OperationResult(path, Outcome.APPLIED)
        message = (
            "the template deleted it, but yours differs: delete it if unused"
        )
        return OperationResult(path, Outcome.MANUAL, message)


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
