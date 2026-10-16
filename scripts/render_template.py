"""Render a pipeline's nf-core template with the installed nf-core/tools.

Run it under the tools release to render, for example:

    uvx --from nf-core==4.0.3 python scripts/render_template.py \
        path/to/.nf-core.yml path/to/output

This mirrors `PipelineSync.make_template_pipeline` in nf-core/tools: it
renders from the pipeline's `.nf-core.yml` template settings, so the output
matches what that release would commit to the TEMPLATE branch.

Releases before 3.0 have no `nf_core.pipelines` package. Their sync passed
the pipeline's manifest values to `nf_core.create.PipelineCreate` instead,
so the same values come from the `template:` section here, and they are
recorded in .nf-migrate-render.yml rather than .nf-core.yml. Those releases
need an older Python; build_template_history.sh picks one. Keep this file
importable on Python 3.8 for that reason.
"""

import inspect
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import nf_core
import yaml


class PrettierDumper(yaml.SafeDumper):
    """Indent list items under their key, as prettier formats YAML."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


# nf-core/tools 4.0.x parses `nextflow inspect` stdout as JSON, but
# Nextflow 26 wraps it in [PIPELINE]/[WORKDIR]/[SUCCESS] status lines. The
# shim keeps only the JSON block for `inspect` and passes other calls on.
NEXTFLOW_INSPECT_SHIM = """#!/usr/bin/env bash
if [ "$1" = "inspect" ]; then
    "$REAL_NEXTFLOW" "$@" | sed -n '/^{/,/^}/p'
    exit "${PIPESTATUS[0]}"
fi
exec "$REAL_NEXTFLOW" "$@"
"""


def install_nextflow_shim(shim_dir: Path) -> None:
    real_nextflow = shutil.which("nextflow")
    if real_nextflow is None:
        return
    shim = shim_dir / "nextflow"
    shim.write_text(NEXTFLOW_INSPECT_SHIM)
    shim.chmod(0o755)
    os.environ["REAL_NEXTFLOW"] = real_nextflow
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{os.environ['PATH']}"


def render(nf_core_yml: Path, output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    # nf-core formats the result with prettier through `prek run`, which
    # works on the git repo of the current directory. Sync runs inside the
    # pipeline repo, so the template's own .prettierignore applies there.
    # The RO-Crate step also reads git history, so seed one empty commit.
    subprocess.run(
        ["git", "init", "-q", "--initial-branch=master", str(output)],
        check=True,
    )
    os.chdir(output)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=nf-migrate",
            "-c",
            "user.email=nf-migrate@localhost",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "render",
        ],
        check=True,
    )

    config = yaml.safe_load(nf_core_yml.read_text())
    # Sync wrote nothing back into .nf-core.yml before 3.0.
    if is_legacy_release():
        create_legacy(config["template"], output)
        write_render_metadata(config, output)
        return

    create(config, output)

    # Same post-processing as sync: record the version, reset force.
    config["template"]["force"] = False
    config["nf_core_version"] = nf_core.__version__
    (output / ".nf-core.yml").write_text(
        yaml.dump(config, Dumper=PrettierDumper, sort_keys=False)
    )


def is_legacy_release() -> bool:
    try:
        import nf_core.pipelines.create.create  # noqa: F401
    except ImportError:
        return True
    return False


def create(config: dict, output: Path) -> None:
    import nf_core.pipelines.create.create

    config["template"]["force"] = True
    config["template"]["outdir"] = "."
    (output / ".nf-core.yml").write_text(yaml.safe_dump(config))

    logging.getLogger("nf_core.pipelines.create").setLevel(logging.ERROR)
    pipeline_create = nf_core.pipelines.create.create.PipelineCreate(
        outdir=str(output),
        from_config_file=True,
        no_git=True,
        force=True,
        default_branch="master",
    )
    pipeline_create.init_pipeline()


def create_legacy(template: dict, output: Path) -> None:
    """Render as sync did before 3.0, from the pipeline's manifest values."""
    import nf_core.create

    # 1.14 to 2.4 call nf_core.utils without importing it; the CLI had
    # always imported it already. Without it every file is copied with its
    # Jinja tags unrendered.
    import nf_core.utils  # noqa: F401

    logging.getLogger("nf_core.create").setLevel(logging.ERROR)
    parameters = inspect.signature(nf_core.create.PipelineCreate).parameters
    arguments = {
        "name": template["name"],
        "description": template["description"],
        "author": template["author"],
        "no_git": True,
        "force": True,
        "outdir": str(output),
    }
    # 1.x called the version `new_version`; 2.x renamed it.
    version_argument = (
        "new_version" if "new_version" in parameters else "version"
    )
    arguments[version_argument] = template["version"]
    # Sync passed these once the releases that added them were out.
    if "plain" in parameters:
        arguments["plain"] = True
    if "default_branch" in parameters:
        arguments["default_branch"] = "master"

    pipeline_create = nf_core.create.PipelineCreate(**arguments)
    pipeline_create.init_pipeline()
    check_tags_rendered(output)


# Template variables of the 1.x (cookiecutter) and 2.x (Jinja) templates.
UNRENDERED_TAG = re.compile(
    r"\{\{ ?(cookiecutter\.|name|short_name|version|description|author)\b"
)


def check_tags_rendered(output: Path) -> None:
    """Fail on files create copied without rendering their template tags.

    Releases before 3.0 copy a file verbatim when rendering it raises, and
    only log it at debug level, so a broken render would otherwise end up
    in a migration.
    """
    unrendered = []
    for path in sorted(output.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue
        if UNRENDERED_TAG.search(content):
            unrendered.append(str(path.relative_to(output)))
    if unrendered:
        raise SystemExit("unrendered template tags in " + ", ".join(unrendered))


def write_render_metadata(config: dict, output: Path) -> None:
    """Record the version and template values `nf-migrate revision` reads.

    They go beside the render rather than into .nf-core.yml, which these
    releases left alone: text added there would end up in migrations,
    although no pipeline of that age has it.
    """
    metadata = {
        "nf_core_version": nf_core.__version__,
        "template": config["template"],
    }
    (output / ".nf-migrate-render.yml").write_text(
        yaml.dump(metadata, Dumper=PrettierDumper, sort_keys=False)
    )


if __name__ == "__main__":
    # nf-core caches `nextflow config` output under $NXF_HOME/nf-core, keyed
    # only by file hashes, and the cache format differs between releases.
    # A per-run NXF_HOME stops one release reading another release's cache.
    # Nextflow's own downloads (framework jars, plugins) are shared through
    # symlinks so a per-run home does not re-download them.
    real_nxf_home = Path(os.environ.get("NXF_HOME", Path.home() / ".nextflow"))
    with tempfile.TemporaryDirectory() as nxf_home:
        for shared in ("framework", "plugins", "capsule"):
            if (real_nxf_home / shared).is_dir():
                (Path(nxf_home) / shared).symlink_to(real_nxf_home / shared)
        os.environ["NXF_HOME"] = nxf_home
        shim_dir = Path(nxf_home) / "bin"
        shim_dir.mkdir()
        install_nextflow_shim(shim_dir)
        render(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
