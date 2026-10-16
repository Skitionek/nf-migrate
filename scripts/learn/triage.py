"""Compact view of one release's disagreeing operations, for editing it.

For each operation that disagrees with the maintainers in at least
--min samples: the template change, then per sample how the pipeline's text
differed from the template's old text, and what the maintainers merged.

usage: triage.py EVAL.jsonl MERGES.jsonl MIGRATIONS_DIR VERSION
       [--min 2] [--samples 3] [--width 160] [--only INDEX ...]
"""

import argparse
import difflib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evaluate import PIPELINES_DIR  # noqa: E402
from gitread import GitReader, GitWorkspace, variables_at  # noqa: E402
from report import locate  # noqa: E402

from nf_migrate.migrations import load_migrations  # noqa: E402
from nf_migrate.operations import RegexReplace, Replace  # noqa: E402


def clip(line: str, width: int) -> str:
    line = line.rstrip("\n")
    return line if len(line) <= width else line[: width - 1] + "…"


def compact_diff(old: str, new: str, width: int, label: str) -> list[str]:
    diff = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            "template",
            label,
            n=0,
            lineterm="",
        )
    )[2:]
    return [clip("    " + line, width) for line in diff]


def region(text: str | None, block: str, context: int = 0) -> str | None:
    if text is None:
        return None
    span = locate(text, block)
    if span is None:
        return None
    lines = text.splitlines(keepends=True)
    start = max(span[0] - context, 0)
    end = min(span[1] + context, len(lines))
    return "".join(lines[start:end])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("eval", type=Path)
    parser.add_argument("merges", type=Path)
    parser.add_argument("migrations", type=Path)
    parser.add_argument("version")
    parser.add_argument("--min", type=int, default=2)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--only", type=int, nargs="*")
    arguments = parser.parse_args()

    merges = {
        merge["merge"]: merge
        for merge in map(json.loads, arguments.merges.read_text().splitlines())
    }
    chain = {m.revision: m for m in load_migrations(arguments.migrations)}
    migration = chain[arguments.version]

    disagreements: dict[int, list[tuple[dict, dict]]] = defaultdict(list)
    totals: dict[int, int] = defaultdict(int)
    for line in arguments.eval.read_text().splitlines():
        sample = json.loads(line)
        for entry in sample.get("operations", []):
            if entry["rev"] != arguments.version or not entry.get("survives"):
                continue
            totals[entry["index"]] += 1
            agree = entry.get("agree")
            if agree is None:
                agree = entry.get("human") == "applied" or (
                    entry["outcome"] == "CONFLICT"
                    and entry.get("human") != "applied"
                )
            if not agree:
                disagreements[entry["index"]].append((sample, entry))

    ranked = sorted(disagreements.items(), key=lambda item: -len(item[1]))
    readers: dict[str, GitReader] = {}
    for index, items in ranked:
        if arguments.only and index not in arguments.only:
            continue
        if len(items) < arguments.min:
            continue
        operation = migration.operations[index]
        kinds = defaultdict(int)
        for _, entry in items:
            human = entry.get("hc") or entry.get("human")
            kinds[f"{entry['outcome']}/{human}"] += 1
        print(
            "=" * 30,
            f"op {index}",
            type(operation).__name__,
            operation.path,
            f"disagree {len(items)}/{totals[index]}",
            dict(kinds),
        )
        if isinstance(operation, Replace):
            print("  template change:")
            for diff_line in compact_diff(
                operation.old, operation.new, arguments.width, "new"
            ):
                print(diff_line)
        elif isinstance(operation, RegexReplace):
            print(f"  pattern: {operation.pattern!r}")
            print(f"  replacement: {operation.replacement!r}")
        for sample, entry in items[: arguments.samples]:
            merge = merges[sample["merge"]]
            pipeline = sample["pipeline"]
            if pipeline not in readers:
                readers[pipeline] = GitReader(PIPELINES_DIR / pipeline)
            reader = readers[pipeline]
            variables = variables_at(reader, merge["before"])
            workspace = GitWorkspace(reader, merge["before"], variables)
            print(
                f"  -- {pipeline} #{sample.get('pr')} "
                f"{sample['from']}->{sample['to']}: {entry['outcome']} "
                f"{entry.get('message') or ''} human={entry.get('human')}"
                f"/{entry.get('hc')}"
            )
            if not isinstance(operation, Replace):
                continue
            old = workspace.expand(operation.old)
            new = workspace.expand(operation.new)
            path = entry["path"]
            before = region(reader.read(merge["before"], path), old)
            after = region(reader.read(merge["merge"], path), new)
            if entry["outcome"] == "CONFLICT":
                if before is None:
                    print("    before: nothing similar")
                else:
                    print("    before vs template old:")
                    for diff_line in compact_diff(
                        old, before, arguments.width, "before"
                    ) or ["    (same)"]:
                        print(diff_line)
            if after is None:
                print("    after: nothing similar")
            else:
                print("    after vs template new:")
                for diff_line in compact_diff(
                    new, after, arguments.width, "after"
                ) or ["    (same)"]:
                    print(diff_line)


if __name__ == "__main__":
    main()
