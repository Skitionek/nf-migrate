"""Summarise evaluate.py results; show the samples behind one operation.

usage: report.py summary EVAL.jsonl [--rev VERSION] [--top N]
       report.py show EVAL.jsonl MERGES.jsonl MIGRATIONS_DIR VERSION INDEX
           [--outcome CONFLICT] [--human applied] [--limit N]
"""

import argparse
import difflib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evaluate import PIPELINES_DIR  # noqa: E402
from gitread import GitReader, GitWorkspace, variables_at  # noqa: E402

from nf_migrate.migrations import load_migrations  # noqa: E402
from nf_migrate.operations import RegexReplace, Replace  # noqa: E402


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def evaluated(results: list[dict]) -> list[dict]:
    return [r for r in results if "operations" in r]


def summary(arguments: argparse.Namespace) -> None:
    results = load(arguments.eval)
    errors = [r for r in results if "error" in r]
    skipped = Counter(r["skipped"] for r in results if "skipped" in r)
    samples = evaluated(results)
    if arguments.to:
        samples = [r for r in samples if r["to"] == arguments.to]

    file_tally = Counter()
    identical = touched = 0
    outcomes = Counter()
    for sample in samples:
        for score in sample["files"].values():
            for key in ("match", "missed", "extra"):
                file_tally[key] += score.get(key, 0)
            if score["touched"]:
                touched += 1
                identical += score["identical"]
        for operation in sample["operations"]:
            if arguments.rev and operation["rev"] != arguments.rev:
                continue
            outcomes[operation["outcome"]] += 1

    scored = sum(file_tally.values()) or 1
    print(
        f"samples {len(samples)}  errors {len(errors)}  "
        f"skipped {sum(skipped.values())}"
    )
    print(
        f"template lines: match {file_tally['match']} "
        f"missed {file_tally['missed']} extra {file_tally['extra']} "
        f"=> {file_tally['match'] / scored:.1%}"
    )
    print(f"touched files identical to human: {identical}/{touched}")
    print("operations:", dict(outcomes))

    per_operation: dict[tuple, Counter] = defaultdict(Counter)
    paths: dict[tuple, str] = {}
    agreement = Counter()
    for sample in samples:
        for operation in sample["operations"]:
            if arguments.rev and operation["rev"] != arguments.rev:
                continue
            key = (operation["rev"], operation["index"])
            paths[key] = f"{operation['kind']} {operation.get('path', '')}"
            counts = per_operation[key]
            counts["total"] += 1
            if not operation.get("survives"):
                continue
            agree = operation.get("agree")
            if agree is None:
                agree = operation.get("human") in (None, "applied") or (
                    operation["outcome"] == "CONFLICT"
                    and operation.get("human") != "applied"
                )
            agreement[agree] += 1
            counts["agree" if agree else "disagree"] += 1
            if not agree:
                human = operation.get("hc") or operation.get("human")
                counts[f"{operation['outcome'][:5]}/{human}"] += 1

    scored_operations = sum(agreement.values()) or 1
    print(
        f"operations agreeing with the maintainers: {agreement[True]}/"
        f"{scored_operations} ({agreement[True] / scored_operations:.1%})"
    )
    print(
        "\nrev index op: disagree / agree / total | disagreement kinds "
        "(our outcome/what the maintainer did)"
    )
    ranked = sorted(
        per_operation.items(),
        key=lambda item: item[1]["disagree"],
        reverse=True,
    )
    for key, counts in ranked[: arguments.top]:
        if not counts["disagree"]:
            break
        kinds = ", ".join(
            f"{kind} {count}"
            for kind, count in counts.most_common()
            if "/" in kind
        )
        print(
            f"{key[0]:>7} {key[1]:>3} {paths[key][:60]:<60} "
            f"{counts['disagree']:>3} {counts['agree']:>3} "
            f"{counts['total']:>3} | {kinds}"
        )

    missed_lines = Counter()
    extra_lines = Counter()
    for sample in samples:
        for path, score in sample["files"].items():
            for line in score["examples"]["missed"]:
                missed_lines[(path, line[:100])] += 1
            for line in score["examples"]["extra"]:
                extra_lines[(path, line[:100])] += 1
    print("\nmost missed template lines:")
    for (path, line), count in missed_lines.most_common(arguments.top):
        print(f"{count:>4} {path}: {line}")
    print("\nmost extra template lines:")
    for (path, line), count in extra_lines.most_common(arguments.top // 2):
        print(f"{count:>4} {path}: {line}")


def locate(text: str, block: str) -> tuple[int, int] | None:
    """Line span of `text` that best resembles `block`.

    Anchored on lines with content, so blank lines cannot pull it astray.
    """
    text_lines = text.splitlines()
    block_lines = block.splitlines()
    if not block_lines:
        return None
    text_keys = [" ".join(line.split()) for line in text_lines]
    block_keys = {" ".join(line.split()) for line in block_lines}
    block_keys.discard("")
    hits = [index for index, key in enumerate(text_keys) if key in block_keys]
    if not hits:
        return None
    # The window of len(block) lines holding most content lines of block.
    size = len(block_lines)
    best_start, best_count = hits[0], 0
    for hit in hits:
        count = sum(1 for other in hits if hit <= other < hit + size)
        if count > best_count:
            best_start, best_count = hit, count
    covered = [
        other for other in hits if best_start <= other < best_start + size
    ]
    return covered[0], covered[-1] + 1


def show_region(label: str, text: str | None, block: str, context: int) -> None:
    if text is None:
        print(f"  [{label}: file missing]")
        return
    span = locate(text, block)
    if span is None:
        print(f"  [{label}: nothing similar]")
        return
    lines = text.splitlines(keepends=True)
    start = max(span[0] - context, 0)
    end = min(span[1] + context, len(lines))
    region = "".join(lines[start:end])
    diff = difflib.unified_diff(
        block.splitlines(keepends=True),
        region.splitlines(keepends=True),
        fromfile="template",
        tofile=label,
        n=1,
    )
    print("".join(diff) or f"  [{label}: identical to template]")


def show(arguments: argparse.Namespace) -> None:
    results = evaluated(load(arguments.eval))
    merges = {m["merge"]: m for m in load(arguments.merges)}
    chain = {m.revision: m for m in load_migrations(arguments.migrations)}
    operation = chain[arguments.version].operations[arguments.index]
    print(operation)
    shown = 0
    for sample in results:
        for entry in sample["operations"]:
            if (entry["rev"], entry["index"]) != (
                arguments.version,
                arguments.index,
            ):
                continue
            if arguments.outcome and entry["outcome"] != arguments.outcome:
                continue
            if arguments.human and entry.get("human") != arguments.human:
                continue
            merge = merges[sample["merge"]]
            reader = GitReader(PIPELINES_DIR / sample["pipeline"])
            variables = variables_at(reader, merge["before"])
            workspace = GitWorkspace(reader, merge["before"], variables)
            print(
                f"\n=== {sample['pipeline']} #{sample['pr']} "
                f"{sample['from']}->{sample['to']} {entry['outcome']} "
                f"({entry.get('message')}) human={entry.get('human')}"
            )
            if isinstance(operation, Replace):
                old = workspace.expand(operation.old)
                new = workspace.expand(operation.new)
            elif isinstance(operation, RegexReplace):
                old, new = operation.pattern, operation.replacement
            else:
                continue
            path = entry["path"]
            show_region("before", reader.read(merge["before"], path), old, 1)
            show_region("after", reader.read(merge["merge"], path), new, 1)
            reader.close()
            shown += 1
            if shown >= arguments.limit:
                return


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(required=True)
    summary_parser = commands.add_parser("summary")
    summary_parser.add_argument("eval", type=Path)
    summary_parser.add_argument("--rev", help="only this release's ops")
    summary_parser.add_argument("--to", help="only merges to this release")
    summary_parser.add_argument("--top", type=int, default=25)
    summary_parser.set_defaults(handler=summary)

    show_parser = commands.add_parser("show")
    show_parser.add_argument("eval", type=Path)
    show_parser.add_argument("merges", type=Path)
    show_parser.add_argument("migrations", type=Path)
    show_parser.add_argument("version")
    show_parser.add_argument("index", type=int)
    show_parser.add_argument("--outcome")
    show_parser.add_argument("--human")
    show_parser.add_argument("--limit", type=int, default=5)
    show_parser.set_defaults(handler=show)

    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
