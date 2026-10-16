import re

from editops import find, load, migration_path, regex, replace_ops

path = migration_path("1.13")
operations = load(path).operations
first = find(operations, "main.nf", old_startswith="def helpMessage() {")
rest = find(operations, "main.nf", old_endswith="// Show help message\n")
replacement = (operations[first].new + "\n" + operations[rest].new).replace("\\", "\\\\")
replace_ops(path, {
    rest: "",
    first: regex(
        "main.nf",
        r"^def helpMessage\(\) \{\n[\s\S]*?^\}\n\n// Show help message\n",
        replacement,
        r"^/\* --               PRINT HELP                 -- \*/\n",
        "Hand-edited: 1.13 moved the help text into the schema. Pipelines\n"
        "list their own parameters in helpMessage(), which goes whatever it\n"
        "holds.",
    ),
})
