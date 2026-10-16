from editops import load, migration_path, regex, replace_ops

path = migration_path("2.11")
operations = load(path).operations
fences = [
    index for index, operation in enumerate(operations)
    if getattr(operation, "path", None) == "docs/usage.md"
    and "```console\n" in getattr(operation, "old", "")
    and '```csv title="samplesheet.csv"\n' in getattr(operation, "new", "")
]
assert len(fences) == 2, fences
replacements = {index: "" for index in fences}
replacements[fences[0]] = regex(
    "docs/usage.md",
    r"^```console\n(?=sample,)",
    '```csv title="samplesheet.csv"\n',
    r'^```csv title="samplesheet\.csv"\n',
    "Hand-edited: the samplesheet examples hold each pipeline's own\n"
    "columns, which the hunks carried as context; any console fence\n"
    "opening a samplesheet becomes a csv one.",
    every=True,
)
replace_ops(path, replacements)
