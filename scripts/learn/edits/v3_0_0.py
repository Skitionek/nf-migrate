from editops import find, first_of, load, migration_path, original_source, regex, replace_ops, varying

path = migration_path("3.0.0")
operations = load(path).operations
utils = "subworkflows/local/utils_nfcore_{{pipeline_name}}_pipeline/main.nf"


def source(index: int) -> str:
    return original_source(path, index)


CHECK_MAX = regex(
    "conf/base.config",
    r"check_max\(\s*([^,]+?)\s*,\s*'(?:cpus|memory|time)'\s*\)",
    r"\1",
    r"\A(?![\s\S]*check_max\()[\s\S]*",
    "",
    every=True,
)

replacements = {}
for index, o in enumerate(operations):
    if getattr(o, "path", None) == "conf/base.config" and "check_max(" in getattr(o, "old", ""):
        replacements[index] = first_of(
            "conf/base.config",
            [source(index), CHECK_MAX],
            "Hand-edited: 3.0 dropped check_max for resourceLimits. Pipelines set\n"
            "their own resources, so check_max goes around whatever values they have.",
        )

schema_plugin = find(operations, utils, old_startswith="    pre_help_text = nfCoreLogo")
replacements[schema_plugin] = first_of(utils, [
    source(schema_plugin),
    varying(operations[schema_plugin], ["def String workflow_command"]),
], "Hand-edited: pipelines write their own workflow_command example.")

samplesheet = find(operations, utils, old_equals='        .fromSamplesheet("input")\n')
replacements[samplesheet] = first_of(utils, [
    source(samplesheet),
    regex(
        utils,
        r'\.fromSamplesheet\("input"\)',
        '.fromList(samplesheetToList(params.input, "${projectDir}/assets/schema_input.json"))',
        r"samplesheetToList\(params\.input",
        "",
        every=True,
    ),
], "Hand-edited: pipelines read the samplesheet in their own channel chain.")

plugins = find(operations, "nextflow.config", old_equals="    doi             = ''\n}\n")
block = operations[plugins].new[len(operations[plugins].old):]
replacements[plugins] = first_of("nextflow.config", [
    source(plugins),
    regex(
        "nextflow.config",
        r"^manifest \{\n[\s\S]*?^\}\n",
        r"\g<0>" + block.replace("\\", "\\\\"),
        r"\A(?=[\s\S]*^validation \{)[\s\S]*",
        "",
    ),
], "Hand-edited: pipelines fill in the manifest's doi this was anchored on;\n"
   "the plugins and validation blocks follow the manifest either way.")

replace_ops(path, replacements)
