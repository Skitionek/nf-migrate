"""Turn evaluate_pipeline.py results into the tables in docs/validation.md.

usage: summarize_evaluation.py RESULT.json...
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

OUTCOMES = ("APPLIED", "ALREADY_APPLIED", "CONFLICT", "MANUAL")


def normalise_path(path: str) -> str:
    """Fold pipeline names out of paths so pipelines group together."""
    path = re.sub(
        r"utils_nfcore_\w+_pipeline", "utils_nfcore_<name>_pipeline", path
    )
    return re.sub(r"^workflows/[\w-]+\.nf$", "workflows/<name>.nf", path)


def main() -> None:
    results = [json.loads(Path(name).read_text()) for name in sys.argv[1:]]
    results.sort(key=lambda result: result["pipeline"])

    rows: list[str] = []
    totals: Counter = Counter()
    conflict_paths: Counter = Counter()
    total_identical = 0
    total_touched = 0
    clean_steps = 0
    resyncs = 0
    evaluated_steps = 0
    skipped_steps: list[str] = []
    detection_rows: list[str] = []
    detection_agreements = 0

    for result in results:
        pipeline = result["pipeline"]
        outcomes: Counter = Counter()
        identical = 0
        touched = 0
        steps = 0
        for step in result["steps"]:
            if "skipped" in step:
                skipped_steps.append(f"{pipeline}: {step['skipped']}")
                continue
            steps += 1
            outcomes.update(step["outcomes"])
            identical += step["identical"]
            touched += step["touched"]
            # A re-sync of the version the pipeline is already on has
            # nothing to apply, so it says nothing about conflicts.
            if step["from"] == step["to"]:
                resyncs += 1
            elif not step["conflicts"]:
                clean_steps += 1
            for conflict in step["conflicts"]:
                path = conflict.split(":", 1)[0]
                conflict_paths[normalise_path(path)] += 1

            if step["detected"] == step["from"]:
                detection_agreements += 1
            else:
                detection_rows.append(
                    f"| {pipeline} | `{step['before']}` | {step['from']} "
                    f"| {step['detected']} |"
                )

        evaluated_steps += steps
        totals.update(outcomes)
        total_identical += identical
        total_touched += touched
        counts = " | ".join(str(outcomes[outcome]) for outcome in OUTCOMES)
        rows.append(
            f"| {pipeline} | {steps} | {counts} | {identical}/{touched} |"
        )

    total_counts = " | ".join(f"**{totals[outcome]}**" for outcome in OUTCOMES)
    rows.append(
        f"| **Total** | **{evaluated_steps}** | {total_counts} "
        f"| **{total_identical}/{total_touched}** |"
    )
    text_operations = (
        totals["APPLIED"] + totals["ALREADY_APPLIED"] + totals["CONFLICT"]
    )
    automatic = totals["APPLIED"] + totals["ALREADY_APPLIED"]

    print("## Per pipeline\n")
    print(
        "| Pipeline | Merges | Applied | Already applied | Conflict "
        "| Manual step | Changed files identical to the human merge |"
    )
    print("|---|---|---|---|---|---|---|")
    print("\n".join(rows))
    print(
        f"\nText operations resolved automatically: "
        f"{automatic}/{text_operations} "
        f"({automatic / text_operations:.0%}). "
        f"Merges with no conflict: {clean_steps}/{evaluated_steps - resyncs} "
        f"({resyncs} re-syncs of an unchanged version not counted)."
    )

    print("\n## Conflicts by file\n")
    print("| Conflicts | File |")
    print("|---|---|")
    for path, count in conflict_paths.most_common(15):
        print(f"| {count} | `{path}` |")

    print("\n## Version detection\n")
    print(
        f"Detected version equals `nf_core_version` for "
        f"{detection_agreements}/{evaluated_steps} pre-merge snapshots.\n"
    )
    if detection_rows:
        print("| Pipeline | Snapshot | Stamped | Detected |")
        print("|---|---|---|---|")
        print("\n".join(detection_rows))

    print("\n## Skipped merges\n")
    for skipped in skipped_steps:
        print(f"- {skipped}")

    print("\n## Evaluated commits\n")
    print("| Pipeline | `origin/dev` at evaluation |")
    print("|---|---|")
    for result in results:
        print(f"| {result['pipeline']} | `{result['dev'][:10]}` |")


if __name__ == "__main__":
    main()
