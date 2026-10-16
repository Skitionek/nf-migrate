"""Write a migration from two renders of the nf-core template.

The refs are two commits holding the template as rendered by consecutive
nf-core/tools releases: a TEMPLATE branch, or a history built by
scripts/build_template_history.sh. Values from the render's `.nf-core.yml`
template section (pipeline name, author, ...) become {{placeholders}}, so
the migration applies to any pipeline.
"""

import json
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from fnmatch import fnmatch
from pathlib import Path

from nf_migrate.operations import (
    NF_CORE_MODULES_REPO,
    find_line_aligned,
    is_inside_match,
)
from nf_migrate.variables import placeholder, template_variables, templatize
from nf_migrate.version import NF_CORE_YML, parse_version, stamp_version

MODULES_JSON = "modules.json"
COMPONENT_KINDS = ("modules", "subworkflows")

# Renders of releases before 3.0 keep the version and template values here:
# those releases wrote neither into .nf-core.yml, and adding them there
# would put text into migrations that no real pipeline has.
RENDER_METADATA = ".nf-migrate-render.yml"

# Template changes a release shipped by mistake. Migrations follow what was
# intended, so these are left out: (release, file, text the change adds).
UNINTENDED_CHANGES = (
    # 2.3.1 put an nf-core/tools release note into the pipeline CHANGELOG;
    # 2.3.2 took it out again, and keeps removing it from pipelines that
    # merged it.
    ("2.3.1", "CHANGELOG.md", "Clarified conda usage"),
)

# Files nf-core generates rather than templates. The RO-Crate gets fresh
# timestamps and random IDs on every render, and the container configs
# follow the installed module versions, so their hunks would rarely match a
# pipeline. The migration names the command that rebuilds them instead.
GENERATED_FILE_INSTRUCTIONS = {
    "ro-crate-metadata.json": "regenerate with `nf-core pipelines rocrate`",
    "conf/containers_*.config": (
        "regenerate with `nf-core pipelines lint --fix container_configs`"
    ),
}


@dataclass(frozen=True, slots=True)
class FileChange:
    status: str
    path: str


@dataclass(frozen=True, slots=True)
class GeneratedMigration:
    revision: str
    down_revision: str
    source: str


@dataclass(slots=True)
class Hunk:
    """Consecutive non-equal opcodes plus the context lines around them."""

    first_opcode: int
    last_opcode: int
    context_before: int = 0
    context_after: int = 0


def generate_migration(
    repo: Path, old_ref: str, new_ref: str
) -> GeneratedMigration:
    old_metadata = _render_metadata(repo, old_ref)
    new_metadata = _render_metadata(repo, new_ref)
    old_version = parse_version(old_metadata)
    new_version = parse_version(new_metadata)
    if old_version is None or new_version is None:
        raise ValueError(f"{NF_CORE_YML} has no nf_core_version at both refs")
    variables = template_variables(new_metadata)

    old_components = _component_shas(_show(repo, old_ref, MODULES_JSON))
    new_components = _component_shas(_show(repo, new_ref, MODULES_JSON))
    changed_components: set[tuple[str, str]] = {
        component
        for component in old_components.keys() | new_components.keys()
        if old_components.get(component) != new_components.get(component)
    }
    known_components = old_components.keys() | new_components.keys()

    operation_sources: list[str] = []
    generated_file_patterns: set[str] = set()
    for change in _changed_files(repo, old_ref, new_ref):
        # modules.json follows the component updates below.
        if change.path in (MODULES_JSON, RENDER_METADATA):
            continue
        component = _component_for_path(change.path, known_components)
        if component is not None:
            changed_components.add(component)
            continue
        pattern = _generated_file_pattern(change.path)
        if pattern is not None:
            generated_file_patterns.add(pattern)
            continue
        operation_sources.extend(
            _operations_for_change(
                repo, old_ref, new_ref, change, new_version, variables
            )
        )

    for kind, name in sorted(changed_components):
        git_sha = new_components.get((kind, name))
        operation_sources.append(
            _call("NfCoreComponent", kind, name, git_sha=git_sha)
        )
    for pattern in sorted(generated_file_patterns):
        instruction = GENERATED_FILE_INSTRUCTIONS[pattern]
        operation_sources.append(_call("ManualStep", pattern, instruction))

    source = _render_module(old_version, new_version, operation_sources)
    return GeneratedMigration(new_version, old_version, source)


def _render_metadata(repo: Path, ref: str) -> str:
    """The render's nf_core_version and template values, as YAML."""
    metadata = _show(repo, ref, RENDER_METADATA)
    if metadata is not None:
        return metadata
    return _show(repo, ref, NF_CORE_YML) or ""


def _component_shas(modules_json: str | None) -> dict[tuple[str, str], str]:
    """(kind, name) -> git_sha for the nf-core components in modules.json."""
    if modules_json is None:
        return {}
    repos = json.loads(modules_json).get("repos", {})
    nf_core_repo = repos.get(NF_CORE_MODULES_REPO, {})

    shas: dict[tuple[str, str], str] = {}
    for kind in COMPONENT_KINDS:
        components = nf_core_repo.get(kind, {}).get("nf-core", {})
        for name, entry in components.items():
            shas[(kind, name)] = entry.get("git_sha")
    return shas


def _component_for_path(
    path: str, known_components: set[tuple[str, str]]
) -> tuple[str, str] | None:
    """The nf-core module or subworkflow a file belongs to, if any."""
    for kind in COMPONENT_KINDS:
        prefix = f"{kind}/nf-core/"
        if not path.startswith(prefix):
            continue
        # Longest known name first: samtools/sort before samtools.
        names = sorted(
            (
                name
                for known_kind, name in known_components
                if known_kind == kind
            ),
            key=len,
            reverse=True,
        )
        for name in names:
            if path.startswith(f"{prefix}{name}/"):
                return (kind, name)
        # Not in either modules.json: fall back to the first path segment.
        return (kind, path[len(prefix) :].split("/", 1)[0])
    return None


def _generated_file_pattern(path: str) -> str | None:
    for pattern in GENERATED_FILE_INSTRUCTIONS:
        if fnmatch(path, pattern):
            return pattern
    return None


def _operations_for_change(
    repo: Path,
    old_ref: str,
    new_ref: str,
    change: FileChange,
    version: str,
    variables: dict[str, str],
) -> list[str]:
    path = templatize(change.path, variables)
    if change.status == "binary":
        instruction = "binary file changed in the template; copy it by hand"
        return [_call("ManualStep", path, instruction)]

    old_text = _show(repo, old_ref, change.path)
    new_text = _show(repo, new_ref, change.path)
    for text in (old_text, new_text):
        _reject_placeholder_lookalikes(change.path, text, variables)

    # The runner stamps nf_core_version itself, creating .nf-core.yml if
    # need be, so the stamp line is the same on both sides and never part of
    # a change; diffing it would tie hunks to its quoting and position.
    if change.path == NF_CORE_YML:
        old_text = stamp_version(old_text or "", version)
        new_text = stamp_version(new_text or "", version)

    if old_text is None and new_text is not None:
        content = templatize(new_text, variables)
        return [_call("CreateFile", path, content=content)]
    if new_text is None and old_text is not None:
        expected_content = templatize(old_text, variables)
        return [_call("DeleteFile", path, expected_content=expected_content)]
    if old_text is None or new_text is None:
        return []

    operations: list[str] = []
    for old_block, new_block in diff_hunks(old_text, new_text):
        unintended = _unintended_change(
            version, change.path, old_block, new_block
        )
        if unintended is not None:
            operations.append(
                f"    # Left out: {version} added {unintended!r} to "
                f"{change.path} by mistake."
            )
            continue
        old = templatize(old_block, variables)
        new = templatize(new_block, variables)
        operations.append(_call("Replace", path, old=old, new=new))
    return operations


def _unintended_change(
    version: str, path: str, old_block: str, new_block: str
) -> str | None:
    for release, release_path, added_text in UNINTENDED_CHANGES:
        is_added_here = added_text in new_block and added_text not in old_block
        if release == version and release_path == path and is_added_here:
            return added_text
    return None


def _reject_placeholder_lookalikes(
    path: str, text: str | None, variables: dict[str, str]
) -> None:
    """Refuse templates that already contain a placeholder's spelling.

    The runner would fill such text with the pipeline's values, changing a
    file the template meant to ship verbatim.
    """
    if text is None:
        return
    for name in variables:
        if placeholder(name) in text:
            raise ValueError(f"{path} already contains {placeholder(name)}")


def diff_hunks(old_text: str, new_text: str) -> list[tuple[str, str]]:
    """Split a file diff into (old, new) blocks with minimal unique context.

    Each block keeps only as much surrounding context as it needs to occur
    exactly once in its template file, so local edits a few lines away from
    a template change do not make it conflict.
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    opcodes = SequenceMatcher(
        None, old_lines, new_lines, autojunk=False
    ).get_opcodes()

    hunks = [
        Hunk(index, index)
        for index, opcode in enumerate(opcodes)
        if opcode[0] != "equal"
    ]
    hunks = _choose_unique_context(hunks, opcodes, old_text, new_text)
    hunks = _merge_overlapping(hunks, opcodes)
    return [_hunk_blocks(hunk, opcodes, old_lines, new_lines) for hunk in hunks]


def _choose_unique_context(
    hunks: list[Hunk], opcodes: list, old_text: str, new_text: str
) -> list[Hunk]:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    index = 0
    while index < len(hunks):
        hunk = hunks[index]
        max_before = _equal_length(opcodes, hunk.first_opcode - 1)
        max_after = _equal_length(opcodes, hunk.last_opcode + 1)

        found_unique_context = False
        # A replacement whose changed lines are unique needs no context, so
        # local edits to neighbouring lines cannot block it. Insertions and
        # deletions keep one line: without it, already applied is
        # indistinguishable from not applicable.
        first_tag = opcodes[hunk.first_opcode][0]
        last_tag = opcodes[hunk.last_opcode][0]
        is_replacement = first_tag == last_tag == "replace"
        first_context = 0 if is_replacement else 1
        for context in range(first_context, max(max_before, max_after, 1) + 1):
            hunk.context_before = min(context, max_before)
            hunk.context_after = min(context, max_after)
            old_block, new_block = _hunk_blocks(
                hunk, opcodes, old_lines, new_lines
            )
            # Hunks apply top to bottom, so the old block has to be unique
            # in the file with the hunks above it already applied. In the
            # new file it may only remain inside the new block, which
            # Replace reads as applied; anywhere else, running the
            # migration again would apply it twice.
            text_when_applied = _text_before_hunk(
                hunk, opcodes, old_lines, new_lines
            )
            is_unambiguous = (
                _is_unique(text_when_applied, old_block)
                and _is_unique(new_text, new_block)
                and _only_inside_new_block(new_text, old_block, new_block)
            )
            if is_unambiguous:
                found_unique_context = True
                break

        # The neighbouring equal blocks are too short to make this hunk
        # unique, so grow it across them into the next or previous hunk.
        if not found_unique_context and len(hunks) > 1:
            if index + 1 < len(hunks):
                hunks[index : index + 2] = [
                    Hunk(hunk.first_opcode, hunks[index + 1].last_opcode)
                ]
            else:
                hunks[index - 1 : index + 1] = [
                    Hunk(hunks[index - 1].first_opcode, hunk.last_opcode)
                ]
                index -= 1
            continue
        index += 1
    return hunks


def _merge_overlapping(hunks: list[Hunk], opcodes: list) -> list[Hunk]:
    merged: list[Hunk] = []
    for hunk in hunks:
        if merged:
            previous = merged[-1]
            gap = _equal_length(opcodes, previous.last_opcode + 1)
            if previous.context_after + hunk.context_before > gap:
                previous.last_opcode = hunk.last_opcode
                previous.context_after = hunk.context_after
                continue
        merged.append(hunk)
    return merged


def _hunk_blocks(
    hunk: Hunk, opcodes: list, old_lines: list[str], new_lines: list[str]
) -> tuple[str, str]:
    _, old_start, _, new_start, _ = opcodes[hunk.first_opcode]
    _, _, old_end, _, new_end = opcodes[hunk.last_opcode]
    old_block = old_lines[
        old_start - hunk.context_before : old_end + hunk.context_after
    ]
    new_block = new_lines[
        new_start - hunk.context_before : new_end + hunk.context_after
    ]
    return "".join(old_block), "".join(new_block)


def _only_inside_new_block(
    new_text: str, old_block: str, new_block: str
) -> bool:
    new_positions = find_line_aligned(new_text, new_block)
    return all(
        is_inside_match(position, len(old_block), new_positions, new_block)
        for position in find_line_aligned(new_text, old_block)
    )


def _text_before_hunk(
    hunk: Hunk, opcodes: list, old_lines: list[str], new_lines: list[str]
) -> str:
    """The file once every change above `hunk` is applied."""
    _, old_start, _, new_start, _ = opcodes[hunk.first_opcode]
    lines_above = new_lines[:new_start]
    lines_from_hunk = old_lines[old_start:]
    return "".join(lines_above + lines_from_hunk)


def _equal_length(opcodes: list, index: int) -> int:
    if index < 0 or index >= len(opcodes):
        return 0
    tag, old_start, old_end, _, _ = opcodes[index]
    if tag != "equal":
        return 0
    return old_end - old_start


def _is_unique(text: str, block: str) -> bool:
    if not block:
        return False
    return len(find_line_aligned(text, block)) == 1


def _changed_files(repo: Path, old_ref: str, new_ref: str) -> list[FileChange]:
    numstat = _git(
        repo, "diff", "--no-renames", "--numstat", "-z", old_ref, new_ref
    )
    changes: list[FileChange] = []
    for entry in numstat.split("\0"):
        if not entry:
            continue
        added, _, path = entry.split("\t", 2)
        status = "binary" if added == "-" else "text"
        changes.append(FileChange(status, path))
    return changes


def _show(repo: Path, ref: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _call(operation: str, *positional: str, **keyword: str | None) -> str:
    """Source for one operation, indented as an item of `operations`."""
    arguments = [f"        {_literal(value)}," for value in positional]
    for name, value in keyword.items():
        arguments.append(f"        {name}={_literal(value)},")
    body = "\n".join(arguments)
    return f"    {operation}(\n{body}\n    ),"


def _literal(value: str | None) -> str:
    """Multi-line text as a readable triple-quoted literal when safe."""
    if value is None or "\n" not in value:
        return repr(value)
    is_safe = (
        '"""' not in value and "\\" not in value and not value.endswith('"')
    )
    if is_safe:
        return f'"""\\\n{value}"""'
    return repr(value)


def _render_module(
    old_version: str, new_version: str, operation_sources: list[str]
) -> str:
    operations_body = "\n".join(operation_sources)
    return (
        f'"""Template update for nf-core/tools {new_version}.\n\n'
        "Generated by nf-migrate; edit freely.\n"
        '"""\n'
        "# ruff: noqa: E501, F401, W291, W293\n\n"
        "from nf_migrate.operations import (\n"
        "    CreateFile,\n"
        "    DeleteFile,\n"
        "    ManualStep,\n"
        "    NfCoreComponent,\n"
        "    Replace,\n"
        ")\n\n"
        f"revision = {new_version!r}\n"
        f"down_revision = {old_version!r}\n\n"
        f"operations = [\n{operations_body}\n]\n"
    )
