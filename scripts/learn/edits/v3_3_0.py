from editops import find, first_of, load, migration_path, original_source, regex, replace_ops

path = migration_path("3.3.0")
operations = load(path).operations
gpu = find(operations, "nextflow.config", new_contains="    gpu {\n")
label = find(operations, "conf/base.config", new_contains="withLabel: process_gpu")
gpu_block = operations[gpu].new[len("    }\n") : operations[gpu].new.index("    test      {")]
label_block = operations[label].new[len("    }\n") : -len("}\n")]

# The template's template-version-comment.yml checks out the PR head in a
# pull_request_target workflow; see edits/v3_0_2.py.
REF = "        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n"
snake = ".github/workflows/template_version_comment.yml"
kebab = ".github/workflows/template-version-comment.yml"
create = find(operations, kebab, kind="CreateFile")
delete = find(operations, snake, kind="DeleteFile")


def without_ref(index: int) -> str:
    source = original_source(path, index)
    assert source.count(REF) == 1
    return source.replace(REF, "")


def first_of_verbatim(file: str, sources: list[str], comment: str) -> str:
    """first_of, but keeps `#` lines: the template text has some."""
    lines = [f"    # {line}" for line in comment.splitlines()]
    lines += ["    FirstOf(", f"        {file!r},", "        operations=("]
    lines += [source.rstrip("\n") for source in sources]
    lines += ["        ),", "    ),"]
    return "\n".join(lines)

replace_ops(path, {
    gpu: first_of("nextflow.config", [
        original_source(path, gpu),
        regex(
            "nextflow.config",
            r"^[ \t]*test\s*\{\s*includeConfig\s+'conf/test\.config'\s*\}\n",
            gpu_block.replace("\\", "\\\\") + r"\g<0>",
            r"\A(?=[\s\S]*^[ \t]*gpu\s*\{)[\s\S]*",
            "",
        ),
    ], "Hand-edited: pipelines add profiles before test, where this was\n"
       "anchored; the gpu profile goes right before test either way."),
    label: first_of("conf/base.config", [
        original_source(path, label),
        regex(
            "conf/base.config",
            r"\n\}\n*\Z",
            "\n" + label_block.replace("\\", "\\\\") + "}\n",
            r"\A(?=[\s\S]*withLabel:\s*process_gpu)[\s\S]*",
            "",
        ),
    ], "Hand-edited: pipelines end base.config with their own labels; the\n"
       "gpu label goes last either way."),
    create: first_of_verbatim(kebab, [
        without_ref(create),
        original_source(path, create),
    ], "Hand-edited: the template's workflow checks out\n"
       "`ref: ${{ github.event.pull_request.head.sha }}`. It runs on\n"
       "pull_request_target, with the base repository's secrets and a write token\n"
       "even for fork PRs, so the fork's .nf-core.yml (whose nf_core_version goes\n"
       "into `pip install`) would be read in a privileged job. It is created\n"
       "without that ref, reading the base branch; a pipeline that already has the\n"
       "template's file counts as done."),
    delete: first_of_verbatim(snake, [
        original_source(path, delete),
        without_ref(delete),
    ], "Hand-edited: 3.0.2 no longer adds that ref to template_version_comment.yml\n"
       "(see v3_0_2.py), so a pipeline upgraded by nf-migrate has the file without\n"
       "it, and one from the template has it. Either is deleted if untouched."),
})
