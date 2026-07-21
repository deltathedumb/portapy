"""Compile and run PortaPy's stable native release conformance hosts."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


HOSTS = (
    ("native_handle_host.c", "opaque-floats: ok"),
    ("native_statement_host.c", "statement-blocks: ok"),
    ("native_text_error_host.c", "native-text-errors: ok"),
    ("native_typed_literal_host.c", "typed-literals: ok"),
    ("native_boolean_expression_host.c", "boolean-expressions: ok"),
    ("native_expression_host.c", "general-expressions: ok"),
    ("native_control_flow_host.c", "control-flow: ok"),
    ("native_function_host.c", "native-functions: ok"),
    ("native_host_object_host.c", "native-host-objects: ok"),
    ("native_host_call_host.c", "native-host-calls: ok"),
    ("native_environment_api_host.c", "universal-environment-api: ok"),
)


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("--compiler", default="gcc" if os.name == "nt" else "cc")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[1]
    library = args.library.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for source_name, expected in HOSTS:
        source = repository / "tests" / source_name
        executable = output_dir / Path(source_name).stem
        if os.name == "nt":
            executable = executable.with_suffix(".exe")
        compile_command = [
            args.compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{repository / 'include'}",
            str(source),
            "-o",
            str(executable),
        ]
        if os.name != "nt":
            compile_command.append("-ldl")
        _run(compile_command)
        result = _run([str(executable), str(library)])
        output = result.stdout.strip()
        (output_dir / f"{Path(source_name).stem}.txt").write_text(
            output + "\n", encoding="utf-8"
        )
        if expected not in output.splitlines():
            raise RuntimeError(
                f"{source_name} did not emit {expected!r}:\n{output}"
            )
        print(expected)

    adapter = _run(
        [
            sys.executable,
            str(repository / "tests" / "native_environment_adapter_probe.py"),
            str(library),
        ],
        cwd=repository,
    )
    adapter_output = adapter.stdout.strip()
    (output_dir / "native_environment_adapter_probe.txt").write_text(
        adapter_output + "\n", encoding="utf-8"
    )
    if "native-environment-adapter: ok" not in adapter_output.splitlines():
        raise RuntimeError(f"native environment adapter failed:\n{adapter_output}")
    print("native-environment-adapter: ok")
    print("native-release-conformance: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
