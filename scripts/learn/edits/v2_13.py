import os
import subprocess
from pathlib import Path

from editops import load, migration_path, op, replace_ops

from nf_migrate.variables import template_variables, templatize

HISTORY = Path(os.environ["NF_MIGRATE_HISTORY"])


def show(path: str) -> str:
    return subprocess.run(["git", "-C", HISTORY, "show", f"v2.13:{path}"],
                          capture_output=True, text=True, check=True).stdout


path = migration_path("2.13")
operations = load(path).operations
render_variables = template_variables(show(".nf-core.yml"))
main_ops = [i for i, o in enumerate(operations) if getattr(o, "path", None) == "main.nf"]
replacements = {i: "" for i in main_ops}
replacements[main_ops[0]] = "\n".join([
    op("ReplaceFile", "main.nf", content=templatize(show("main.nf"), render_variables),
       already="PIPELINE_INITIALISATION",
       comment="Hand-edited: 2.13 rewrote main.nf around the new utils subworkflows.\n"
               "Its hunks cannot match a pipeline's own main.nf; maintainers took the\n"
               "template's file and re-added their own genome parameters."),
    op("ManualStep", "main.nf",
       "re-add pipeline-specific genome parameters (getGenomeAttribute) and includes"),
])
replace_ops(path, replacements)
