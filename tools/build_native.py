"""Build PortaPy's asmpython-generated native shared library.

Interpreter/runtime semantics remain in ``src/portapy/native_api.py``. This tool
only orchestrates asmpython, audited ABI transformations, NASM, the public C ABI
boundary, and the platform linker. It deliberately fails closed when generated
assembly or required tools are missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.elf_pic import make_elf_pic
from tools.nasm_eval_abi import append_eval_abi
from tools.nasm_exports import declare_exports
from tools.nasm_float_abi import append_float_abi
from tools.nasm_handle_abi import append_handle_abi
from tools.nasm_module_init import make_module_initializer
from tools.nasm_scalar_abi import append_scalar_abi
from tools.nasm_state_abi import append_state_abi
from tools.native_surface import PUBLIC_EXPORTS, linux_version_script, windows_definition


class BuildFailure(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise BuildFailure(f"required native build tool is unavailable: {name}")
    return resolved


def _run(command: list[str], *, log: Path | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        rendered = shlex.join(command)
        raise BuildFailure(
            f"command failed with exit code {completed.returncode}: {rendered}\n"
            f"{completed.stdout}"
        )
    return completed


def _compile_python_source(
    *,
    target: str,
    source: Path,
    output: Path,
    build_log: Path,
) -> Path:
    command = [
        sys.executable,
        "-m",
        "asmpython",
        "build",
        str(source),
        "--target",
        target,
        "--type",
        "library",
        "--backend",
        "legacy",
        "--no-pyinbin-fallback",
        "--keep-assembly",
        "-o",
        str(output),
    ]
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    build_log.parent.mkdir(parents=True, exist_ok=True)
    build_log.write_text(completed.stdout, encoding="utf-8")

    assembly = output.with_suffix(".asm")
    if not assembly.is_file():
        rendered = shlex.join(command)
        raise BuildFailure(
            f"asmpython did not emit assembly (exit {completed.returncode}): "
            f"{rendered}\n{completed.stdout}"
        )

    # The legacy driver has historically reached complete NASM emission before
    # failing in its own process-spawn step. Assembly presence is the boundary
    # that matters here because this tool performs NASM/linking itself.
    return assembly


def _transform_assembly(assembly: Path, *, target: str) -> None:
    source = assembly.read_text(encoding="utf-8")
    source = make_module_initializer(
        source,
        target=target,
        public_symbol="portapy_library_initialize",
    )
    source = append_handle_abi(source, target=target)
    source = append_scalar_abi(source, target=target)
    source = append_float_abi(source, target=target)
    source = append_eval_abi(source, target=target)
    source = append_state_abi(source, target=target)
    source = declare_exports(source, list(PUBLIC_EXPORTS))
    if target == "linux":
        source = make_elf_pic(source)
    assembly.write_text(source, encoding="utf-8")


def build_native(
    *,
    target: str,
    output: Path,
    source: Path,
    work_dir: Path,
) -> dict[str, object]:
    if target not in {"linux", "windows"}:
        raise BuildFailure(f"unsupported native target: {target}")
    if not source.is_file():
        raise BuildFailure(f"Python native API source does not exist: {source}")

    glue_source = REPOSITORY_ROOT / "native" / "text_error_glue.c"
    if not glue_source.is_file():
        raise BuildFailure(f"public C ABI glue does not exist: {glue_source}")

    output = output.resolve()
    work_dir = work_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    build_log = work_dir / f"{target}-asmpython-build.log"

    assembly = _compile_python_source(
        target=target,
        source=source.resolve(),
        output=output,
        build_log=build_log,
    )
    _transform_assembly(assembly, target=target)

    nasm = _tool("nasm")
    gcc = _tool("gcc")
    object_suffix = ".o" if target == "linux" else ".obj"
    object_path = work_dir / f"portapy-python{object_suffix}"
    glue_object = work_dir / f"portapy-glue{object_suffix}"
    nasm_format = "elf64" if target == "linux" else "win64"
    _run(
        [
            nasm,
            "-f",
            nasm_format,
            "-w-label-redef-late",
            str(assembly),
            "-o",
            str(object_path),
        ],
        log=work_dir / f"{target}-nasm.log",
    )

    compile_glue = [
        gcc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(REPOSITORY_ROOT / "include"),
        "-c",
        str(glue_source),
        "-o",
        str(glue_object),
    ]
    if target == "linux":
        compile_glue.insert(1, "-fPIC")
    _run(compile_glue, log=work_dir / f"{target}-glue.log")

    if target == "linux":
        version_script = work_dir / "portapy.map"
        version_script.write_text(linux_version_script(), encoding="utf-8")
        link_command = [
            gcc,
            "-shared",
            str(object_path),
            str(glue_object),
            f"-Wl,--version-script={version_script}",
            "-o",
            str(output),
        ]
    else:
        definition = work_dir / "portapy.def"
        definition.write_text(windows_definition(), encoding="ascii")
        link_command = [
            gcc,
            "-shared",
            str(object_path),
            str(glue_object),
            str(definition),
            "-o",
            str(output),
        ]

    _run(link_command, log=work_dir / f"{target}-link.log")
    if not output.is_file() or output.stat().st_size == 0:
        raise BuildFailure(f"linker did not produce a native library: {output}")

    metadata: dict[str, object] = {
        "schema": 1,
        "target": target,
        "artifact": output.name,
        "size": output.stat().st_size,
        "sha256": _sha256(output),
        "source": str(source.resolve().relative_to(REPOSITORY_ROOT)),
        "source_sha256": _sha256(source),
        "abi_glue": str(glue_source.relative_to(REPOSITORY_ROOT)),
        "abi_glue_sha256": _sha256(glue_source),
        "public_exports": list(PUBLIC_EXPORTS),
        "python_built_runtime": True,
    }
    metadata_path = output.with_suffix(output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source",
        type=Path,
        default=REPOSITORY_ROOT / "src" / "portapy" / "native_api.py",
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        metadata = build_native(
            target=args.target,
            output=args.output,
            source=args.source,
            work_dir=args.work_dir,
        )
    except BuildFailure as error:
        print(f"portapy native build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
