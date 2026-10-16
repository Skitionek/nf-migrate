import os
import subprocess
from pathlib import Path

from editops import load, migration_path, op, replace_ops

from nf_migrate.autogenerate import RENDER_METADATA
from nf_migrate.variables import template_variables, templatize

HISTORY = Path(os.environ["NF_MIGRATE_HISTORY"])

path = migration_path("2.0")
operations = load(path).operations
render_variables = template_variables(
    subprocess.run(["git", "-C", HISTORY, "show", f"v2.0:{RENDER_METADATA}"],
                   capture_output=True, text=True, check=True).stdout
)
main_nf = subprocess.run(["git", "-C", HISTORY, "show", "v2.0:main.nf"],
                         capture_output=True, text=True, check=True).stdout
content = templatize(main_nf, render_variables)

main_ops = [i for i, o in enumerate(operations) if getattr(o, "path", None) == "main.nf"]
assert main_ops, "no main.nf operations"
replacements = {i: "" for i in main_ops}
replacements[main_ops[0]] = "\n".join([
    op("ReplaceFile", "main.nf", content=content, already="nextflow.enable.dsl = 2",
       comment="Hand-edited: 2.0 turned main.nf into a DSL2 entry point. Its hunks\n"
               "cannot match a DSL1 pipeline's own main.nf; maintainers took the\n"
               "template's file and moved their code into workflows/."),
    op("ManualStep", "workflows/{{pipeline_name}}.nf",
       "port the pipeline's DSL1 processes and channels from the old main.nf"),
])
replace_ops(path, replacements)

# bin/scrape_software_versions.py: 2.0 made it read *.version.txt files
# instead of a per-pipeline table of regexes.
operations = load(path).operations
script = subprocess.run(["git", "-C", HISTORY, "show", "v2.0:bin/scrape_software_versions.py"],
                        capture_output=True, text=True, check=True).stdout
script_ops = [i for i, o in enumerate(operations)
              if getattr(o, "path", None) == "bin/scrape_software_versions.py"]
replacements = {i: "" for i in script_ops}
replacements[script_ops[0]] = op(
    "ReplaceFile", "bin/scrape_software_versions.py",
    content=templatize(script, render_variables),
    already='x.endswith(".version.txt")',
    comment="Hand-edited: 2.0 rewrote the script to read the version files\n"
            "modules write; pipelines' own regex tables made its hunks conflict.",
)
replace_ops(path, replacements)
