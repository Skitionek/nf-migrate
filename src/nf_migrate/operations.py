"""Idempotent file operations that a migration is made of.

Every operation inspects the pipeline before changing it and reports one of
three outcomes. Running an operation twice is safe: the second run sees the
new text and reports ALREADY_APPLIED. Anything the operation cannot place
unambiguously is a CONFLICT for a human to resolve.
"""

import difflib
import enum
import json
import re
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
    # An edit to a file the pipeline no longer has. Reported, not blocking.
    SKIPPED = "skipped"


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


def missing_file_result(path: str, change: str) -> OperationResult:
    """An edit has nothing to edit. The pipeline deleted or moved the file,
    which is its own choice, so this is not a conflict; the report names the
    file so a reviewer can check where the content went.
    """
    message = "the pipeline has no such file"
    return OperationResult(path, Outcome.SKIPPED, message, change)


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
    """Replace one exact block of text, usually a template diff hunk.

    `context_before` and `context_after` are the template lines around
    `old`. They only pick an occurrence when a pipeline has `old` more than
    once, so edits to them never block the change. With `every`, each
    occurrence changes instead, as for a CI step a pipeline copied.

    With `requires`, the change only applies while the file still contains
    that text: template boilerplate such as a `TODO nf-core` note means
    nothing to a pipeline that has filled in all of them.
    """

    path: str
    old: str
    new: str
    context_before: str = ""
    context_after: str = ""
    every: bool = False
    requires: str = ""

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        old = workspace.expand(self.old)
        new = workspace.expand(self.new)
        context_before = workspace.expand(self.context_before)
        context_after = workspace.expand(self.context_after)

        change = _change_diff(path, old, new)

        content = workspace.read(path)
        if content is None:
            return missing_file_result(path, change)
        if self.requires and self.requires not in content:
            message = f"not needed: the file has no {self.requires!r} left"
            return OperationResult(
                path, Outcome.ALREADY_APPLIED, message, change
            )

        result = self._place(
            workspace,
            path,
            content,
            old,
            new,
            context_before,
            context_after,
            change,
        )
        # Maintainers delete the template's TODO notes once they act on
        # them, so try again without those lines.
        if result is None and TODO_NOTE in old:
            old_without_notes = without_todo_notes(old)
            new_without_notes = without_todo_notes(new)
            if any(line.strip() for line in old_without_notes.splitlines()):
                result = self._place(
                    workspace,
                    path,
                    content,
                    old_without_notes,
                    new_without_notes,
                    context_before,
                    context_after,
                    change,
                )
            elif PLACEHOLDER_PROSE not in new_without_notes:
                # Nothing but notes: put the new text where they were.
                # Placeholder prose ("a pipeline that ...") replacing a note
                # is boilerplate still, which the pipeline has replaced.
                result = self._place_between(
                    workspace,
                    path,
                    content,
                    without_todo_notes(context_before),
                    new_without_notes,
                    without_todo_notes(context_after),
                    change,
                )
        if result is not None:
            return result
        message = "old text not found"
        return OperationResult(path, Outcome.CONFLICT, message, change)

    def _place_between(
        self,
        workspace: Workspace,
        path: str,
        content: str,
        before: str,
        new: str,
        after: str,
        change: str,
    ) -> OperationResult | None:
        """Insert new between the context lines, trying both, then one."""
        anchors = [(before, after)]
        if before.strip():
            anchors.append((before, ""))
        if after.strip():
            anchors.append(("", after))
        for anchor_before, anchor_after in anchors:
            anchor = anchor_before + anchor_after
            if not any(_has_letters(line) for line in anchor.splitlines()):
                continue
            result = self._place(
                workspace,
                path,
                content,
                anchor,
                anchor_before + new + anchor_after,
                "",
                "",
                change,
            )
            if result is not None and result.outcome is not Outcome.CONFLICT:
                return result
        return None

    def _place(
        self,
        workspace: Workspace,
        path: str,
        content: str,
        old: str,
        new: str,
        context_before: str,
        context_after: str,
        change: str,
    ) -> OperationResult | None:
        """Apply old -> new to content; None when old is nowhere."""
        # Pipelines often re-align assignments or trim trailing spaces, so
        # when the exact text is nowhere, compare lines without that.
        for find_spans in (find_exact_spans, find_realigned_spans):
            old_spans = find_spans(content, old)
            new_spans = find_spans(content, new) if new else []
            # When the template appended to the end of the old text, the
            # new text contains the old; a match inside the new text is the
            # change already made, not a place to make it again.
            old_spans = [
                span
                for span in old_spans
                if not _is_inside_span(span, new_spans)
            ]
            if not old_spans and new_spans:
                outcome = Outcome.ALREADY_APPLIED
                return OperationResult(path, outcome, "", change)
            if len(old_spans) > 1 and self.every:
                updated = content
                for start, end in reversed(old_spans):
                    updated = updated[:start] + new + updated[end:]
                workspace.write(path, updated)
                return OperationResult(path, Outcome.APPLIED, "", change)
            if len(old_spans) > 1:
                best_span = _best_span_by_context(
                    content, old_spans, context_before, context_after
                )
                if best_span is not None:
                    old_spans = [best_span]
            if len(old_spans) == 1:
                start, end = old_spans[0]
                workspace.write(path, content[:start] + new + content[end:])
                return OperationResult(path, Outcome.APPLIED, "", change)
            if len(old_spans) > 1:
                message = f"old text found {len(old_spans)} times"
                return OperationResult(path, Outcome.CONFLICT, message, change)

        # Where indentation is only layout, follow the pipeline's own.
        if _may_reindent(path, old):
            new_matches = find_reindented(content, new) if new else []
            new_spans = [span for span, _ in new_matches]
            old_matches = [
                (span, indents)
                for span, indents in find_reindented(content, old)
                if not _is_inside_span(span, new_spans)
            ]
            if not old_matches and new_spans:
                outcome = Outcome.ALREADY_APPLIED
                return OperationResult(path, outcome, "", change)
            if len(old_matches) == 1:
                (start, end), indents = old_matches[0]
                reindented = reindent(new, indents)
                updated = content[:start] + reindented + content[end:]
                workspace.write(path, updated)
                return OperationResult(path, Outcome.APPLIED, "", change)
        return None


def _has_letters(line: str) -> bool:
    return sum(character.isalnum() for character in line) >= 3


# Marks template boilerplate a maintainer is expected to resolve.
TODO_NOTE = "TODO nf-core"
# Ends the template's placeholder sentences for a pipeline to complete.
PLACEHOLDER_PROSE = "..."


def without_todo_notes(text: str) -> str:
    return "".join(
        line for line in text.splitlines(keepends=True) if TODO_NOTE not in line
    )


# Markdown, where formatters re-indent nested lists.
REINDENTABLE_SUFFIXES = (".md",)
# Nextflow and Groovy, where pipelines nest template code in their own
# blocks. A short block indented differently is often a different block,
# so only distinctive ones follow the pipeline's indentation.
CODE_SUFFIXES = (".nf", ".groovy", ".config")
DISTINCTIVE_LINES = 3
DISTINCTIVE_CHARACTERS = 30


def _may_reindent(path: str, old: str) -> bool:
    if path.endswith(REINDENTABLE_SUFFIXES):
        return True
    if not path.endswith(CODE_SUFFIXES):
        return False
    content_lines = [line for line in old.splitlines() if _has_letters(line)]
    characters = sum(c.isalnum() for line in content_lines for c in line)
    return (
        len(content_lines) >= DISTINCTIVE_LINES
        or characters >= DISTINCTIVE_CHARACTERS
    )


def _indentation(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def find_reindented(
    content: str, text: str
) -> list[tuple[tuple[int, int], dict[int, str]]]:
    """Spans of lines equal to `text`'s but for a consistent re-indent.

    Each match comes with how the pipeline indents each of the template's
    indentation widths, so new text can be indented the same way.
    """
    wanted = text.splitlines()
    if not any(line.strip() for line in wanted):
        return []
    wanted_words = [_markdown_words(line) for line in wanted]
    lines = content.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    matches = []
    size = len(wanted)
    for index in range(len(lines) - size + 1):
        window = lines[index : index + size]
        if [_markdown_words(line) for line in window] != wanted_words:
            continue
        indents: dict[int, str] = {}
        is_consistent = True
        for template_line, line in zip(wanted, window, strict=True):
            if not template_line.strip():
                continue
            width = len(_indentation(template_line))
            indent = _indentation(line)
            if indents.setdefault(width, indent) != indent:
                is_consistent = False
        widths = sorted(indents)
        is_ordered = all(
            len(indents[a]) < len(indents[b])
            for a, b in zip(widths, widths[1:], strict=False)
        )
        if not is_consistent or not is_ordered:
            continue
        end = offsets[index + size]
        if not text.endswith("\n"):
            last_line = window[-1]
            end -= len(last_line) - len(last_line.rstrip("\r\n"))
        matches.append(((offsets[index], end), indents))
    return matches


def _markdown_words(line: str) -> list[str]:
    """A line's words with Markdown styles formatters rewrite made equal:
    `__bold__` as `**bold**`, and `*` or `+` bullets as `-`.
    """
    words = line.replace("__", "**").split()
    if words and words[0] in ("*", "+"):
        words[0] = "-"
    return words


def reindent(text: str, indents: dict[int, str]) -> str:
    """`text` with template indentation widths mapped as in `indents`."""
    scaled = [
        (width, len(indent)) for width, indent in indents.items() if width
    ]
    ratio = scaled[0][1] / scaled[0][0] if scaled else 1
    character = next((i[0] for i in indents.values() if i), " ")
    lines = []
    for line in text.splitlines(keepends=True):
        if not line.strip():
            lines.append(line)
            continue
        width = len(_indentation(line))
        indent = indents.get(width, character * round(width * ratio))
        lines.append(indent + line.lstrip())
    return "".join(lines)


def _best_span_by_context(
    content: str,
    spans: list[tuple[int, int]],
    context_before: str,
    context_after: str,
) -> tuple[int, int] | None:
    """The one span whose neighbouring lines match the most context lines."""
    before_lines = [_realigned(line) for line in context_before.splitlines()]
    after_lines = [_realigned(line) for line in context_after.splitlines()]
    if not before_lines and not after_lines:
        return None

    def score(span: tuple[int, int]) -> int:
        start, end = span
        lines_before = content[:start].splitlines()[-len(before_lines) :]
        lines_after = content[end:].splitlines()[: len(after_lines)]
        if not before_lines:
            lines_before = []
        matches = sum(
            _realigned(line) == wanted
            for line, wanted in zip(
                reversed(lines_before), reversed(before_lines), strict=False
            )
        )
        matches += sum(
            _realigned(line) == wanted
            for line, wanted in zip(lines_after, after_lines, strict=False)
        )
        return matches

    scores = [score(span) for span in spans]
    best_score = max(scores)
    if best_score == 0 or scores.count(best_score) > 1:
        return None
    return spans[scores.index(best_score)]


@dataclass(frozen=True, slots=True)
class RemoveText:
    """Make sure one paragraph the template dropped is gone.

    Large template deletions are split into paragraphs: pipelines keep some
    generic sections verbatim and rewrite others, and only the verbatim
    ones should go. A paragraph that is no longer there needs nothing done.
    """

    path: str
    text: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        text = workspace.expand(self.text)

        change = _change_diff(path, text, "")

        content = workspace.read(path)
        if content is None:
            return OperationResult(path, Outcome.ALREADY_APPLIED, "", change)

        for find_spans in (find_exact_spans, find_realigned_spans):
            spans = find_spans(content, text)
            if len(spans) == 1:
                start, end = spans[0]
                workspace.write(path, content[:start] + content[end:])
                return OperationResult(path, Outcome.APPLIED, "", change)
            if len(spans) > 1:
                message = f"text found {len(spans)} times"
                return OperationResult(path, Outcome.CONFLICT, message, change)
        return OperationResult(path, Outcome.ALREADY_APPLIED, "", change)


def find_exact_spans(content: str, text: str) -> list[tuple[int, int]]:
    return [
        (start, start + len(text)) for start in find_line_aligned(content, text)
    ]


def find_realigned_spans(content: str, text: str) -> list[tuple[int, int]]:
    """Spans of whole lines equal to `text`'s lines but for spacing.

    Runs of spaces inside a line and at its end do not count; indentation
    does, as it carries meaning in YAML and Python.
    """
    wanted = [_realigned(line) for line in text.splitlines()]
    if not wanted:
        return []
    lines = content.splitlines(keepends=True)
    keys = [_realigned(line) for line in lines]
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    spans: list[tuple[int, int]] = []
    size = len(wanted)
    for index in range(len(lines) - size + 1):
        if keys[index : index + size] != wanted:
            continue
        end = offsets[index + size]
        if not text.endswith("\n"):
            last_line = lines[index + size - 1]
            end -= len(last_line) - len(last_line.rstrip("\r\n"))
        spans.append((offsets[index], end))
    return spans


def _realigned(line: str) -> str:
    words = line.split()
    if not words:
        return ""
    indentation = line[: len(line) - len(line.lstrip())]
    return indentation + " ".join(words)


@dataclass(frozen=True, slots=True)
class RegexReplace:
    """Replace a template block that pipelines customise in known places.

    `pattern` matches the template's old text but lets the parts pipelines
    change vary; its groups capture them, and `replacement` puts them back
    with `\\g<name>`. `applied` matches the text once changed, which tells
    a second run that the change is already made. Patterns are compiled
    with re.MULTILINE, and {{placeholders}} in them match the pipeline's
    values literally.
    """

    path: str
    pattern: str
    replacement: str
    applied: str
    # Change every match, not just a single one.
    every: bool = False

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        pattern = re.compile(_expand_pattern(self.pattern, workspace))
        applied = re.compile(_expand_pattern(self.applied, workspace))
        replacement = _expand_replacement(self.replacement, workspace)

        change = _change_diff(path, self.pattern, self.replacement)

        content = workspace.read(path)
        if content is None:
            return missing_file_result(path, change)

        applied_spans = [match.span() for match in applied.finditer(content)]
        # As for Replace: text the change appended to keeps matching the
        # pattern, but inside the applied text it is the change already made.
        matches = [
            match
            for match in pattern.finditer(content)
            if not _is_inside_span(match.span(), applied_spans)
        ]
        if not matches and applied_spans:
            return OperationResult(path, Outcome.ALREADY_APPLIED, "", change)
        if matches and self.every:
            updated = content
            for match in reversed(matches):
                start, end = match.span()
                updated = (
                    updated[:start] + match.expand(replacement) + updated[end:]
                )
            workspace.write(path, updated)
            return OperationResult(path, Outcome.APPLIED, "", change)
        if len(matches) == 1:
            match = matches[0]
            new_text = match.expand(replacement)
            start, end = match.span()
            workspace.write(path, content[:start] + new_text + content[end:])
            return OperationResult(path, Outcome.APPLIED, "", change)
        if len(matches) > 1:
            message = f"pattern found {len(matches)} times"
            return OperationResult(path, Outcome.CONFLICT, message, change)
        message = "pattern not found"
        return OperationResult(path, Outcome.CONFLICT, message, change)


def _expand_pattern(pattern: str, workspace: Workspace) -> str:
    escaped_variables = {
        name: re.escape(value) for name, value in workspace.variables.items()
    }
    expanded = expand(pattern, escaped_variables)
    return f"(?m){expanded}"


def _expand_replacement(replacement: str, workspace: Workspace) -> str:
    # A backslash in a value would read as a group reference or escape.
    escaped_variables = {
        name: value.replace("\\", "\\\\")
        for name, value in workspace.variables.items()
    }
    return expand(replacement, escaped_variables)


def _is_inside_span(
    span: tuple[int, int], spans: list[tuple[int, int]]
) -> bool:
    start, end = span
    return any(
        outer_start <= start and end <= outer_end
        for outer_start, outer_end in spans
    )


VERSION = r"\d+(?:\.\d+)+"


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@dataclass(frozen=True, slots=True)
class BumpVersion:
    """Raise a version wherever `prefix` precedes it.

    `prefix` is a pattern for the text before the version on its line (a
    plugin id, a setting). The rest of the line is the pipeline's own, so
    an edited comment or a reordered option does not stop the bump. A
    version already at `new` or newer stays.
    """

    path: str
    prefix: str
    old: str
    new: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        prefix = _expand_pattern(self.prefix, workspace)
        pattern = re.compile(f"{prefix}(?P<version>{VERSION})")
        change = f"{self.prefix}: {self.old} -> {self.new}"

        content = workspace.read(path)
        if content is None:
            return missing_file_result(path, change)
        matches = list(pattern.finditer(content))
        if not matches:
            message = "versioned text not found"
            return OperationResult(path, Outcome.CONFLICT, message, change)

        wanted = _version_key(self.new)
        older = [m for m in matches if _version_key(m["version"]) < wanted]
        if not older:
            newer = [m for m in matches if _version_key(m["version"]) > wanted]
            message = (
                f"the pipeline has a newer {newer[0]['version']}"
                if newer
                else ""
            )
            return OperationResult(
                path, Outcome.ALREADY_APPLIED, message, change
            )
        updated = content
        for match in reversed(older):
            start, end = match.span("version")
            updated = updated[:start] + self.new + updated[end:]
        workspace.write(path, updated)
        return OperationResult(path, Outcome.APPLIED, "", change)


@dataclass(frozen=True, slots=True)
class FirstOf:
    """The first of `operations` that does not conflict.

    Lists the exact template change first and a more tolerant way of
    making it after, so untouched pipelines get the template's text
    byte for byte and customised ones still get the change.
    """

    path: str
    operations: tuple

    def apply(self, workspace: Workspace) -> OperationResult:
        first_conflict = None
        for operation in self.operations:
            result = operation.apply(workspace)
            if result.outcome is not Outcome.CONFLICT:
                return result
            if first_conflict is None:
                first_conflict = result
        return first_conflict


@dataclass(frozen=True, slots=True)
class ReplaceFile:
    """Swap in the template's file, for a release that rewrote it.

    When a release restructures a file entirely (2.0 turned main.nf into a
    DSL2 entry point), its hunks cannot match a pipeline's own version,
    and maintainers took the template's file, porting their code by hand.
    A file that already contains `already` is on the new structure and is
    left alone.
    """

    path: str
    content: str
    already: str

    def apply(self, workspace: Workspace) -> OperationResult:
        path = workspace.expand(self.path)
        content = workspace.expand(self.content)
        already = workspace.expand(self.already)

        existing = workspace.read(path)
        if existing == content or (existing and already in existing):
            return OperationResult(path, Outcome.ALREADY_APPLIED)
        workspace.write(path, content)
        message = ""
        if existing is not None:
            message = "replaced as a whole; port the pipeline's own code"
        return OperationResult(path, Outcome.APPLIED, message)


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


@dataclass(frozen=True, slots=True)
class SnapNormalize:
    """Sort JSON keys in nf-test snapshot files.

    Nextflow 26.04.0 changed the order in which it reports tool versions,
    switching from insertion order to alphabetical. Sorting the keys in all
    leaf dicts (version maps) normalises snapshots so they pass regardless
    of the Nextflow version that ran them.

    A leaf dict is one whose values are all non-dicts (strings, numbers).
    Those are the per-tool version maps; the enclosing tool-group dicts have
    dict values and are left in place.
    """

    glob: str = "**/*.snap"

    @property
    def path(self) -> str:
        return self.glob

    def apply(self, workspace: Workspace) -> list[OperationResult]:
        paths = sorted(
            str(p.relative_to(workspace.root))
            for p in workspace.root.glob(self.glob)
            if p.is_file()
        )
        if not paths:
            return [
                OperationResult(self.glob, Outcome.SKIPPED, "no files matched")
            ]
        results = []
        for path in paths:
            content = workspace.read(path)
            if content is None:
                continue
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                results.append(
                    OperationResult(path, Outcome.CONFLICT, "invalid JSON")
                )
                continue
            sorted_data = _sort_leaf_dicts(data)
            sorted_content = json.dumps(sorted_data, indent=4) + "\n"
            if sorted_content == content:
                results.append(OperationResult(path, Outcome.ALREADY_APPLIED))
            else:
                workspace.write(path, sorted_content)
                results.append(OperationResult(path, Outcome.APPLIED))
        return results


def _sort_leaf_dicts(obj: object) -> object:
    """Recursively sort keys in dicts whose values are all non-dicts."""
    if isinstance(obj, dict):
        processed = {k: _sort_leaf_dicts(v) for k, v in obj.items()}
        if all(not isinstance(v, dict) for v in obj.values()):
            return dict(sorted(processed.items()))
        return processed
    if isinstance(obj, list):
        return [_sort_leaf_dicts(item) for item in obj]
    return obj


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
