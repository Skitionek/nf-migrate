from editops import find, load, migration_path, op, regex, replace_ops

path = migration_path("1.10")
operations = load(path).operations
todo_old = "<!-- TODO nf-core: Document required command line parameters to run the pipeline-->\n"

toc = find(operations, "docs/usage.md", kind="RemoveText", text_contains="## Table of contents\n")
outdir = find(operations, "nextflow.config", new_contains="  publish_dir_mode = 'copy'\n", old_startswith="  outdir")
running = find(operations, "docs/usage.md", old_startswith="Nextflow handles job submissions")
old_running = operations[running].old
first, rest = old_running.split("\n\n", 1)
second = rest[: rest.index(todo_old)]

replace_ops(path, {
    outdir: regex(
        "nextflow.config",
        r"^([ \t]*)outdir\s*=.*\n(?![ \t]*publish_dir_mode)",
        r"\g<0>\1publish_dir_mode = 'copy'\n",
        r"^[ \t]*publish_dir_mode\s*=",
        "Hand-edited: pipelines change the outdir default this was anchored on.",
    ),
    running: "\n".join([
        op("RemoveText", "docs/usage.md", text=first + "\n\n",
           comment="Hand-edited: pipelines edit the TODO below, so the generic\nparagraphs go on their own."),
        op("RemoveText", "docs/usage.md", text=second),
        op("Replace", "docs/usage.md", old=todo_old, new=operations[running].new),
    ]),
    toc: regex(
        "docs/usage.md",
        r"^## Table of contents\n\n(?:[ \t]*[*-] \[.*\n)+\n",
        "",
        r"\A(?![\s\S]*^## Table of contents\n)",
        "Hand-edited: pipelines list their own parameters in the table of\ncontents, which the template drops whatever it holds.",
    ),
})
