"""Helpers to hand-edit operations of a migration file by index."""

import ast
import importlib.util
import re
from pathlib import Path

from nf_migrate.autogenerate import _call


def load(path: Path):
    spec = importlib.util.spec_from_file_location("_edit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_ops(path: Path, replacements: dict[int, str]) -> None:
    """Swap the source of operations by index for the given source."""
    source = path.read_text()
    tree = ast.parse(source)
    operations = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign) and node.targets[0].id == "operations"
    )
    lines = source.splitlines(keepends=True)
    for index in sorted(replacements, reverse=True):
        node = operations.elts[index]
        start = node.lineno - 1
        # Keep comment lines directly above an operation with it.
        while start > 0 and lines[start - 1].lstrip().startswith("#"):
            start -= 1
        lines[start : node.end_lineno] = [
            replacements[index].rstrip("\n") + "\n"
        ]
    path.write_text("".join(lines))


def op(name: str, *positional, comment: str = "", **keyword) -> str:
    text = _call(name, *positional, **keyword)
    if comment:
        text = (
            "".join(f"    # {line}\n" for line in comment.splitlines()) + text
        )
    return text


def regex(
    path: str,
    pattern: str,
    replacement: str,
    applied: str,
    comment: str,
    every: bool = False,
) -> str:
    """RegexReplace source with raw-string patterns."""
    lines = [f"    # {line}" for line in comment.splitlines()]
    lines += [
        "    RegexReplace(",
        f"        {path!r},",
        f"        pattern={_raw(pattern)},",
        f"        replacement={_raw(replacement)},",
        f"        applied={_raw(applied)},",
        *(["        every=True,"] if every else []),
        "    ),",
    ]
    return "\n".join(lines)


def _raw(text: str) -> str:
    if "'" not in text and "\n" not in text and not text.endswith("\\"):
        return f"r'{text}'"
    if '"' not in text and "\n" not in text and not text.endswith("\\"):
        return f'r"{text}"'
    return repr(text)


def find(operations, path: str, **conditions) -> int:
    """Index of the one operation on `path` matching every condition.

    A condition `old_startswith="x"` checks `operation.old.startswith("x")`;
    `old_contains`, `new_contains`, `text_startswith`, `kind` work alike.
    """
    matches = []
    for index, operation in enumerate(operations):
        # A generated FirstOf is found by its exact template change.
        if type(operation).__name__ == "FirstOf":
            operation = operation.operations[0]
        if getattr(operation, "path", None) != path:
            continue
        ok = True
        for key, wanted in conditions.items():
            if key == "kind":
                ok &= type(operation).__name__ == wanted
                continue
            attribute, test = key.rsplit("_", 1)
            value = getattr(operation, attribute, None)
            if not isinstance(value, str):
                ok = False
            elif test == "startswith":
                ok &= value.startswith(wanted)
            elif test == "endswith":
                ok &= value.endswith(wanted)
            elif test == "contains":
                ok &= wanted in value
            elif test == "equals":
                ok &= value == wanted
        if ok:
            matches.append(index)
    if len(matches) != 1:
        raise LookupError(f"{path} {conditions}: {len(matches)} matches")
    return matches[0]


def migration_path(version: str) -> Path:
    name = "v" + version.replace(".", "_") + ".py"
    return Path("src/nf_migrate/nf_core_migrations") / name


def _escape(text: str) -> str:
    """A literal for a pattern, keeping {{placeholders}} fillable."""
    escaped = re.sub(r"([.^$*+?{}\[\]\\|()])", r"\\\1", text)
    return escaped.replace(r"\{\{", "{{").replace(r"\}\}", "}}")


def varying(operation, varies, path=None, comment="") -> str:
    """RegexReplace source for a Replace whose lines matching `varies` may
    differ in a pipeline. Such a line is captured and, where the new text
    keeps it, put back as the pipeline wrote it.
    """
    pattern_parts, groups = [], {}
    for number, line in enumerate(operation.old.splitlines(keepends=True)):
        if any(text in line for text in varies):
            name = f"line{number}"
            groups[line] = name
            pattern_parts.append(f"(?P<{name}>[^\\n]*\\n)")
        else:
            pattern_parts.append(_escape(line))
    replacement_parts, applied_parts = [], []
    for line in operation.new.splitlines(keepends=True):
        if line in groups:
            replacement_parts.append(f"\\g<{groups[line]}>")
            applied_parts.append("[^\\n]*\\n")
        else:
            replacement_parts.append(line.replace("\\", "\\\\"))
            applied_parts.append(_escape(line))
    return regex(
        path or operation.path,
        "^" + "".join(pattern_parts),
        "".join(replacement_parts),
        "^" + "".join(applied_parts),
        comment,
    )


def first_of(path: str, sources: list[str], comment: str) -> str:
    """FirstOf source holding operation sources, tried in order."""
    lines = [f"    # {line}" for line in comment.splitlines()]
    lines += ["    FirstOf(", f"        {path!r},", "        operations=("]
    for source in sources:
        body = "\n".join(
            line
            for line in source.splitlines()
            if not line.lstrip().startswith("#")
        )
        # Not re-indented: that would change template text inside
        # triple-quoted strings.
        lines.append(body)
    lines += ["        ),", "    ),"]
    return "\n".join(lines)


def original_source(path: Path, index: int) -> str:
    """The generated source of operation `index`, as it stands in the file."""
    source = path.read_text()
    tree = ast.parse(source)
    operations = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign) and node.targets[0].id == "operations"
    )
    node = operations.elts[index]
    lines = source.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1 : node.end_lineno])
