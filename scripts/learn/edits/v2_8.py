import re

from editops import find, load, migration_path, regex, replace_ops

path = migration_path("2.8")
operations = load(path).operations
chm13 = find(operations, "conf/igenomes.config", new_contains="        'CHM13' {\n")
new = operations[chm13].new
block = new[new.index("        'CHM13' {\n") : new.index("        }\n", new.index("        'CHM13' {\n")) + len("        }\n")]
replace_ops(path, {
    chm13: regex(
        "conf/igenomes.config",
        r"^        'GRCm38' \{\n",
        block.replace("\\", "\\\\").replace("$", "$") + "        'GRCm38' {\n",
        r"^[ \t]*'CHM13' \{[\s\S]*?^        'GRCm38' \{\n",
        "Hand-edited: pipelines add keys (macs_gsize, blacklist) to the GRCh38\n"
        "entry this was anchored on; CHM13 goes before GRCm38 either way.",
    ),
})
