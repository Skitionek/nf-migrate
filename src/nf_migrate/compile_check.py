"""Check that Nextflow can compile a pipeline.

nf-core lint only notices a script that no longer compiles through its
container_configs test, so a migration that leaves a stale `include` is
found late and under a misleading name. `nextflow inspect` parses the
pipeline's scripts the way a run does and fails on a compile error, without
running a process; `nextflow config` does not parse them and passes.

A preview run of the test profile then validates the parameters against the
schema. An nf-schema release that is stricter than the one the pipeline was
written for, such as one that rejects an empty string for a `file-path`
parameter, otherwise only fails in CI's nf-test.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from nf_migrate.migrations import MigrationError

ERROR_LINES_SHOWN = 5
COMPILE_SUMMARY = (
    "Nextflow could not compile the merged pipeline (`nextflow inspect`):"
)
PREVIEW_SUMMARY = (
    "Nextflow could not validate the merged pipeline in a preview run "
    "(`nextflow run -preview -profile test,docker`):"
)


@dataclass(frozen=True, slots=True)
class CompileCheck:
    passed: bool
    error: str = ""
    summary: str = ""

    def render_markdown(self) -> str:
        quoted_error = [f"> {line}" for line in self.error.splitlines()]
        lines = [
            "> [!WARNING]",
            f"> {self.summary}",
            "> ```",
            *quoted_error,
            "> ```",
        ]
        return "\n".join(lines)


def run_compile_check(pipeline: Path) -> CompileCheck:
    """Inspect, then preview `pipeline`; a failure is a result, not a raise.

    Nextflow can also fail on a missing network resource, so the caller
    reports a failed check as a warning. A missing `nextflow` command is a
    usage error instead, because no check happened at all.
    """
    inspect_command = [
        "nextflow",
        "inspect",
        "-format",
        "json",
        str(pipeline),
    ]
    inspected = _run_nextflow(inspect_command)
    if inspected.returncode != 0:
        return CompileCheck(False, _first_lines(inspected), COMPILE_SUMMARY)

    # A pipeline that does not compile cannot be previewed, so this only
    # runs on one that does. The outdir keeps the run's files out of the tree.
    with tempfile.TemporaryDirectory() as outdir:
        preview_command = [
            "nextflow",
            "run",
            str(pipeline),
            "-profile",
            "test,docker",
            "-preview",
            "--outdir",
            outdir,
        ]
        previewed = _run_nextflow(preview_command)
    if previewed.returncode != 0:
        return CompileCheck(False, _first_lines(previewed), PREVIEW_SUMMARY)
    return CompileCheck(passed=True)


def _run_nextflow(command: list[str]) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "NXF_ANSI_LOG": "false"}
    # Nextflow writes .nextflow/ and work/ into its working directory.
    with tempfile.TemporaryDirectory() as working_directory:
        try:
            return subprocess.run(
                command,
                cwd=working_directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise MigrationError(
                "--compile-check needs the nextflow command"
            ) from None


def _first_lines(completed: subprocess.CompletedProcess[str]) -> str:
    output = completed.stderr.strip() or completed.stdout.strip()
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[:ERROR_LINES_SHOWN])
