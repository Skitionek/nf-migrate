"""Replay merged template updates with the chain, scored against the humans.

For every merge: apply the migrations from its from-version to its
to-version to the commit before the merge (all operations, no stop at a
conflict), then compare with the merge itself.

Two scores, both blind to edits that have nothing to do with the template:

- per operation, what the maintainer did with that template change:
  `applied` (the new text is there), `kept` (the old text is still there),
  `other` (neither: adapted, moved, or removed);
- per file the template changed, the lines the template adds or removes
  between the two releases: does our result add/remove each such line
  where the maintainer's does (match), where it does not (extra), or not
  where it does (missed).

usage: evaluate.py MERGES.jsonl HISTORY_REPO MIGRATIONS_DIR OUT.jsonl
       [--to VERSION ...] [--pipelines NAME ...]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gitread import GitReader, GitWorkspace, variables_at  # noqa: E402

from nf_migrate.autogenerate import RENDER_METADATA  # noqa: E402
from nf_migrate.migrations import (  # noqa: E402
    MigrationError,
    load_migrations,
    pending_migrations,
)
from nf_migrate.operations import (  # noqa: E402
    CreateFile,
    DeleteFile,
    FirstOf,
    RegexReplace,
    RemoveText,
    Replace,
    ReplaceFile,
    find_line_aligned,
    is_inside_match,
)
from nf_migrate.runner import stamp_workspace  # noqa: E402
from nf_migrate.variables import (  # noqa: E402
    TemplateVariableError,
    expand,
    template_variables,
    templatize,
)
from nf_migrate.version import NF_CORE_YML  # noqa: E402
from nf_migrate.yaml_edit import (  # noqa: E402
    YamlListItem,
    YamlSet,
    _find,
    _scalar_value,
    _select,
)

# Clones of the pipelines named in the merges file, one directory each.
PIPELINES_DIR = Path(os.environ.get("NF_MIGRATE_PIPELINES", "pipelines"))

SKIPPED_PREFIXES = ("modules/nf-core/", "subworkflows/nf-core/")
SKIPPED_FILES = {"modules.json", "ro-crate-metadata.json", RENDER_METADATA}
BINARY_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".jar", ".ico", ".pdf")
EXAMPLE_LIMIT = 6


CONFLICT_MARKER = re.compile(r"^(<<<<<<<|>>>>>>>) ", re.MULTILINE)


def has_conflict_markers(text: str | None) -> bool:
    """A merge committed with unresolved conflicts holds both sides."""
    return text is not None and CONFLICT_MARKER.search(text) is not None


def normalise(line: str) -> str | None:
    """Whitespace-insensitive line, None for lines without content."""
    collapsed = " ".join(line.split())
    if not re.search(r"[A-Za-z0-9]", collapsed):
        return None
    # The runner writes the stamp; its quoting is not a template change.
    if collapsed.startswith("nf_core_version:"):
        return None
    return collapsed


def line_counts(text: str | None) -> Counter:
    counts: Counter = Counter()
    for line in (text or "").splitlines():
        normalised = normalise(line)
        if normalised is not None:
            counts[normalised] += 1
    return counts


class History:
    """The template rendered per release, with placeholder values."""

    def __init__(self, repo: Path) -> None:
        self.reader = GitReader(repo)
        self.repo = repo
        self._variables: dict[str, dict[str, str]] = {}
        self._changed: dict[tuple[str, str], list[str]] = {}

    def render_variables(self, version: str) -> dict[str, str]:
        if version not in self._variables:
            tag = f"v{version}"
            metadata = self.reader.read(tag, RENDER_METADATA)
            if metadata is None:
                metadata = self.reader.read(tag, NF_CORE_YML) or ""
            self._variables[version] = template_variables(metadata)
        return self._variables[version]

    def changed_paths(self, old: str, new: str) -> list[str]:
        """Placeholder paths of text files the template changed."""
        key = (old, new)
        if key not in self._changed:
            completed = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.repo),
                    "diff",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    f"v{old}",
                    f"v{new}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            variables = self.render_variables(new)
            paths = [
                templatize(path, variables)
                for path in completed.stdout.split("\0")
                if path
            ]
            self._changed[key] = [path for path in paths if is_scored(path)]
        return self._changed[key]

    def template_file(
        self, version: str, path: str, pipeline_variables: dict[str, str]
    ) -> str | None:
        variables = self.render_variables(version)
        text = self.reader.read(f"v{version}", expand(path, variables))
        if text is None:
            return None
        return expand(templatize(text, variables), pipeline_variables)


def is_scored(path: str) -> bool:
    if path.startswith(SKIPPED_PREFIXES) or path in SKIPPED_FILES:
        return False
    if path.startswith("conf/containers_"):
        return False
    return not path.lower().endswith(BINARY_SUFFIXES)


def human_status(operation, workspace, after: str | None) -> str | None:
    """What the maintainers did with this template change."""
    if isinstance(operation, Replace):
        old = workspace.expand(operation.old)
        new = workspace.expand(operation.new)
        if after is None:
            return "deleted"
        new_positions = find_line_aligned(after, new) if new else []
        old_positions = [
            position
            for position in find_line_aligned(after, old)
            if not is_inside_match(position, len(old), new_positions, new)
        ]
        if not new:
            return "kept" if old_positions else "applied"
        if new_positions and not old_positions:
            return "applied"
        if old_positions and not new_positions:
            return "kept"
        return "other"
    if isinstance(operation, RegexReplace):
        if after is None:
            return "deleted"
        applied = re.compile(
            "(?m)" + _escaped(operation.applied, workspace.variables)
        )
        pattern = re.compile(
            "(?m)" + _escaped(operation.pattern, workspace.variables)
        )
        applied_spans = [match.span() for match in applied.finditer(after)]
        unapplied = [
            match
            for match in pattern.finditer(after)
            if not any(
                start <= match.start() and match.end() <= end
                for start, end in applied_spans
            )
        ]
        if applied_spans and not unapplied:
            return "applied"
        if unapplied and not applied_spans:
            return "kept"
        return "other"
    if isinstance(operation, RemoveText):
        if after is None:
            return "applied"
        removed = workspace.expand(operation.text)
        return "kept" if find_line_aligned(after, removed) else "applied"
    if isinstance(operation, YamlSet | YamlListItem):
        return yaml_status(operation, workspace, after)
    if isinstance(operation, ReplaceFile):
        if after is None:
            return "deleted"
        content = workspace.expand(operation.content)
        already = workspace.expand(operation.already)
        return "applied" if after == content or already in after else "kept"
    if isinstance(operation, CreateFile):
        if after is None:
            return "kept"
        content = workspace.expand(operation.content)
        return "applied" if after == content else "other"
    if isinstance(operation, DeleteFile):
        return "applied" if after is None else "kept"
    return None


def yaml_status(operation, workspace, text: str | None) -> str:
    """applied / kept / other for the value at the operation's key."""
    import yaml

    if text is None:
        return "deleted"
    from nf_migrate.yaml_edit import _expand_part

    key = [_expand_part(p, workspace) for p in operation.key]
    try:
        _, _, node = _find(yaml.compose(text), key)
        if isinstance(operation, YamlListItem):
            match = _expand_part(operation.match, workspace)
            found = node is not None and _select(node, match, False) is not None
            if operation.item is None:
                return "kept" if found else "applied"
            return "applied" if found else "kept"
    except Exception:  # noqa: BLE001 - unparsable or reshaped file
        return "other"
    if operation.value is None:
        return "applied" if node is None else "kept"
    if node is None:
        return "kept" if operation.old is None else "other"
    if not isinstance(node, yaml.ScalarNode):
        return "other"
    value = _scalar_value(workspace.expand(operation.value))
    if node.value == value:
        return "applied"
    if operation.old is not None and node.value == _scalar_value(
        workspace.expand(operation.old)
    ):
        return "kept"
    return "other"


def _escaped(pattern: str, variables: dict[str, str]) -> str:
    return expand(
        pattern, {name: re.escape(value) for name, value in variables.items()}
    )


def score_file(
    template_old: str | None,
    template_new: str | None,
    before: str | None,
    after: str | None,
    ours: str | None,
) -> dict:
    old_counts = line_counts(template_old)
    new_counts = line_counts(template_new)
    before_counts = line_counts(before)
    after_counts = line_counts(after)
    our_counts = line_counts(ours)

    added = set(new_counts) - set(old_counts)
    removed = set(old_counts) - set(new_counts)
    tally = Counter()
    examples: dict[str, list[str]] = {"missed": [], "extra": []}
    for lines, sign in ((added, 1), (removed, -1)):
        for line in sorted(lines):
            human = (after_counts[line] - before_counts[line]) * sign > 0
            ours_changed = (our_counts[line] - before_counts[line]) * sign > 0
            if human and ours_changed:
                tally["match"] += 1
            elif human:
                tally["missed"] += 1
                if len(examples["missed"]) < EXAMPLE_LIMIT:
                    examples["missed"].append(("+" if sign > 0 else "-") + line)
            elif ours_changed:
                tally["extra"] += 1
                if len(examples["extra"]) < EXAMPLE_LIMIT:
                    examples["extra"].append(("+" if sign > 0 else "-") + line)
    return {
        **tally,
        "identical": ours == after,
        "touched": ours != before,
        "examples": examples,
    }


def stripped_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()]


def whitespace_matches(text: str, block: str) -> int:
    """How often block occurs in text, comparing lines stripped."""
    text_lines = stripped_lines(text)
    block_lines = stripped_lines(block)
    if not block_lines:
        return 0
    size = len(block_lines)
    return sum(
        text_lines[start : start + size] == block_lines
        for start in range(len(text_lines) - size + 1)
    )


def conflict_reason(content: str | None, old: str, new: str) -> str:
    if content is None:
        return "missing-file"
    if len(find_line_aligned(content, old)) > 1:
        return "ambiguous"
    old_count = whitespace_matches(content, old)
    if old_count == 1:
        return "whitespace"
    if old_count > 1:
        return "whitespace-ambiguous"
    if new and whitespace_matches(content, new):
        return "whitespace-applied"
    return "content"


def concept_status(
    old: str, new: str, before: str | None, text: str | None
) -> str | None:
    """Whether `text` made the lines this change adds and removes.

    Context lines and spacing do not count, so a maintainer who applied a
    change around their own edits still counts as having applied it.
    """
    old_counts = line_counts(old)
    new_counts = line_counts(new)
    added = new_counts - old_counts
    removed = old_counts - new_counts
    if not added and not removed:
        return None
    if text is None:
        return "deleted"
    before_counts = line_counts(before)
    counts = line_counts(text)
    done = [
        counts[line] >= 1 and counts[line] >= before_counts[line]
        for line in added
    ] + [
        counts[line] == 0 or counts[line] < before_counts[line]
        for line in removed
    ]
    if all(done):
        return "applied"
    if not any(done):
        return "kept"
    return "partial"


def lines_agree(
    old: str, new: str, after: str | None, ours: str | None
) -> bool | None:
    """Whether ours and the maintainers' text agree on the changed lines."""
    old_counts = line_counts(old)
    new_counts = line_counts(new)
    changed = set(new_counts - old_counts) | set(old_counts - new_counts)
    if not changed:
        return None
    after_counts = line_counts(after)
    our_counts = line_counts(ours)
    return all(
        (after_counts[line] > 0) == (our_counts[line] > 0) for line in changed
    )


def survives(operation, workspace, template_target: str | None) -> bool:
    """Whether the change is still there in the target release's render."""
    return human_status(operation, workspace, template_target) == "applied"


def evaluate_merge(
    merge: dict,
    chain: list,
    history: History,
    reader: GitReader,
    resolved: Path | None = None,
) -> dict:
    result = {key: merge[key] for key in ("pipeline", "merge", "from", "to")}
    result["pr"] = merge.get("pr")
    try:
        migrations = pending_migrations(chain, merge["from"], merge["to"])
    except MigrationError as error:
        result["skipped"] = str(error)
        return result
    if not migrations:
        result["skipped"] = "nothing to apply"
        return result

    before, after = merge["before"], merge["merge"]
    variables = variables_at(reader, before)
    workspace = GitWorkspace(reader, before, variables)
    target = merge["to"]

    def our_text_of(path: str) -> str | None:
        """Our result: the migrated workspace, or a tree resolved after it
        (by hand or by an agent) when scoring that instead."""
        if resolved is None:
            return workspace.read(path)
        file_path = resolved / path
        return file_path.read_text() if file_path.is_file() else None

    operations = []
    # (entry, old, new) for Replace operations, scored on the final texts.
    replacements = []
    yaml_operations = []
    for migration in migrations:
        stamp_workspace(workspace, migration.revision)
        for index, operation in enumerate(migration.operations):
            kind = type(operation).__name__
            # Scored like its exact template change, which comes first.
            scored = operation
            if isinstance(operation, FirstOf):
                scored = operation.operations[0]
            entry = {"rev": migration.revision, "index": index, "kind": kind}
            try:
                outcome = operation.apply(workspace)
            except TemplateVariableError as error:
                entry.update(outcome="ERROR", message=str(error))
                operations.append(entry)
                continue
            entry.update(
                path=outcome.path,
                outcome=outcome.outcome.name,
                message=outcome.message,
            )
            if outcome.outcome.name == "CONFLICT" and kind == "Replace":
                entry["why"] = conflict_reason(
                    workspace.read(outcome.path),
                    workspace.expand(operation.old),
                    workspace.expand(operation.new),
                )
            operation = scored
            kind = type(operation).__name__
            if has_conflict_markers(reader.read(after, outcome.path)):
                entry["survives"] = None
                entry["noisy"] = "conflict markers"
                operations.append(entry)
                continue
            scored_kinds = (
                "Replace",
                "RegexReplace",
                "RemoveText",
                "CreateFile",
                "DeleteFile",
                "ReplaceFile",
                "YamlSet",
                "YamlListItem",
            )
            if kind in scored_kinds:
                path = outcome.path
                if kind in ("YamlSet", "YamlListItem"):
                    yaml_operations.append((entry, operation))
                if kind == "ReplaceFile":
                    replacements.append(
                        (
                            entry,
                            reader.read(before, outcome.path) or "",
                            workspace.expand(operation.content),
                        )
                    )
                if kind == "RemoveText":
                    replacements.append(
                        (entry, workspace.expand(operation.text), "")
                    )
                if kind == "Replace":
                    replacements.append(
                        (
                            entry,
                            workspace.expand(operation.old),
                            workspace.expand(operation.new),
                        )
                    )
                entry["human"] = human_status(
                    operation, workspace, reader.read(after, path)
                )
                template_path = templatize(path, variables)
                try:
                    template_target = history.template_file(
                        target, template_path, variables
                    )
                    entry["survives"] = survives(
                        operation, workspace, template_target
                    )
                except TemplateVariableError:
                    entry["survives"] = None
            operations.append(entry)

    for entry, operation in yaml_operations:
        path = entry["path"]
        human = yaml_status(operation, workspace, reader.read(after, path))
        ours = yaml_status(operation, workspace, our_text_of(path))
        entry["hc"] = human
        entry["oc"] = ours
        entry["agree"] = human == ours
    for entry, old, new in replacements:
        path = entry["path"]
        before_text = reader.read(before, path)
        entry["hc"] = concept_status(
            old, new, before_text, reader.read(after, path)
        )
        our_text = our_text_of(path)
        entry["oc"] = concept_status(old, new, before_text, our_text)
        entry["agree"] = lines_agree(
            old, new, reader.read(after, path), our_text
        )

    files = {}
    for template_path in history.changed_paths(merge["from"], target):
        try:
            path = expand(template_path, variables)
            template_old = history.template_file(
                merge["from"], template_path, variables
            )
            template_new = history.template_file(
                target, template_path, variables
            )
        except TemplateVariableError:
            continue
        after_text = reader.read(after, path)
        if has_conflict_markers(after_text):
            continue
        files[path] = score_file(
            template_old,
            template_new,
            reader.read(before, path),
            after_text,
            our_text_of(path),
        )
    result.update(operations=operations, files=files)
    return result


def evaluate_pipeline(task: tuple) -> list[dict]:
    pipeline, merges, history_repo, migrations_dir, resolved = task
    chain = load_migrations(Path(migrations_dir))
    history = History(Path(history_repo))
    reader = GitReader(PIPELINES_DIR / pipeline)
    results = []
    for merge in merges:
        try:
            results.append(
                evaluate_merge(
                    merge,
                    chain,
                    history,
                    reader,
                    Path(resolved) if resolved else None,
                )
            )
        except Exception:  # noqa: BLE001 - keep going, report the sample
            results.append(
                {
                    "pipeline": pipeline,
                    "merge": merge["merge"],
                    "from": merge["from"],
                    "to": merge["to"],
                    "error": traceback.format_exc(),
                }
            )
    reader.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("merges", type=Path)
    parser.add_argument("history", type=Path)
    parser.add_argument("migrations", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--to", nargs="*")
    parser.add_argument("--pipelines", nargs="*")
    parser.add_argument(
        "--covers", help="only merges whose range includes this release"
    )
    parser.add_argument("--merge", help="only this merge commit")
    parser.add_argument(
        "--resolved",
        type=Path,
        help="with --merge: score this pipeline directory instead of the "
        "migrations' result, e.g. after resolving its conflicts",
    )
    arguments = parser.parse_args()
    revisions = [
        migration.revision
        for migration in load_migrations(arguments.migrations)
    ]
    root = load_migrations(arguments.migrations)[0].down_revision
    order = {version: index for index, version in enumerate([root, *revisions])}

    by_pipeline: dict[str, list[dict]] = {}
    for line in arguments.merges.read_text().splitlines():
        merge = json.loads(line)
        if arguments.to and merge["to"] not in arguments.to:
            continue
        if arguments.covers:
            start = order.get(merge["from"])
            end = order.get(merge["to"])
            wanted = order[arguments.covers]
            if start is None or end is None or not start < wanted <= end:
                continue
        if arguments.pipelines and merge["pipeline"] not in arguments.pipelines:
            continue
        if arguments.merge and not merge["merge"].startswith(arguments.merge):
            continue
        by_pipeline.setdefault(merge["pipeline"], []).append(merge)

    tasks = [
        (
            pipeline,
            merges,
            str(arguments.history),
            str(arguments.migrations),
            str(arguments.resolved) if arguments.resolved else None,
        )
        for pipeline, merges in sorted(by_pipeline.items())
    ]
    with arguments.out.open("w") as out, ProcessPoolExecutor(8) as executor:
        for results in executor.map(evaluate_pipeline, tasks):
            for result in results:
                out.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
