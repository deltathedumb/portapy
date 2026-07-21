"""Build a PortaPy native shared-library probe from the Python-authored API."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.nasm_eval_abi import append_eval_abi
from tools.nasm_host_abi import append_host_abi
from tools.nasm_pic import patch_elf_pic
from tools.nasm_runtime_wrappers import append_runtime_wrappers
from tools.nasm_state_abi import append_state_abi
from tools.nasm_text_error_abi import append_text_error_abi
from tools.native_surface import (
    assembly_exports,
    linux_version_script,
    public_exports,
    windows_definition,
)


class BuildFailure(RuntimeError):
    """Raised when a required native build step cannot be completed."""


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise BuildFailure(f"required build tool is unavailable: {name}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, log: Path, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise BuildFailure(
            f"command failed ({completed.returncode}): {' '.join(command)}; "
            f"see {log}"
        )


def _compile_glue(
    *,
    gcc: str,
    target: str,
    source: Path,
    output: Path,
    log: Path,
) -> None:
    command = [
        gcc,
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-I",
        str(REPOSITORY_ROOT / "include"),
        "-c",
        str(source),
        "-o",
        str(output),
    ]
    if target == "linux":
        command.insert(1, "-fPIC")
    _run(command, log=log)


def _transform_assembly(
    assembly: Path,
    target: str,
    *,
    host_bridge: bool = False,
) -> None:
    source = assembly.read_text(encoding="utf-8")
    source = append_runtime_wrappers(source, target=target)
    source = append_state_abi(source, target=target)
    source = append_eval_abi(source, target=target)
    source = append_text_error_abi(source, target=target)
    if host_bridge:
        source = append_host_abi(source, target=target)
    if target == "linux":
        source = patch_elf_pic(
            source,
            external_functions=("malloc", "free", "memcpy"),
            external_data=(),
        )
    assembly.write_text(source, encoding="utf-8")


def build_native(
    *,
    target: str,
    output: Path,
    source: Path,
    work_dir: Path,
    host_bridge: bool = False,
) -> dict[str, object]:
    if target not in {"linux", "windows"}:
        raise ValueError(f"unsupported target: {target}")
    if not source.is_file():
        raise BuildFailure(f"native API source is missing: {source}")

    asmpython = _tool("asmpython")
    nasm = _tool("nasm")
    gcc = _tool("gcc")
    work_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    suffix = ".obj" if target == "windows" else ".o"
    assembly = output.with_suffix(".asm")
    python_object = work_dir / f"portapy-python{suffix}"
    base_glue_object = work_dir / f"portapy-glue{suffix}"
    host_glue_object = work_dir / f"portapy-host-glue{suffix}"
    traceback_stub_object = work_dir / f"portapy-traceback-filename-stub{suffix}"
    base_glue = REPOSITORY_ROOT / "native" / "text_error_glue.c"
    host_glue = REPOSITORY_ROOT / "native" / "host_object_glue.c"
    traceback_stub = REPOSITORY_ROOT / "native" / "traceback_filename_stub.c"

    environment = os.environ.copy()
    existing_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        str(REPOSITORY_ROOT)
        if not existing_pythonpath
        else str(REPOSITORY_ROOT) + os.pathsep + existing_pythonpath
    )

    _run(
        [
            asmpython,
            "build",
            str(source),
            "--target",
            target,
            "-o",
            str(output),
        ],
        log=work_dir / f"{target}-asmpython.log",
        env=environment,
    )

    if not assembly.is_file():
        raise BuildFailure(f"asmpython did not emit expected assembly: {assembly}")
    _transform_assembly(assembly, target, host_bridge=host_bridge)

    _compile_glue(
        gcc=gcc,
        target=target,
        source=base_glue,
        output=base_glue_object,
        log=work_dir / f"{target}-glue.log",
    )
    _compile_glue(
        gcc=gcc,
        target=target,
        source=traceback_stub,
        output=traceback_stub_object,
        log=work_dir / f"{target}-traceback-filename-stub.log",
    )
    if host_bridge:
        _compile_glue(
            gcc=gcc,
            target=target,
            source=host_glue,
            output=host_glue_object,
            log=work_dir / f"{target}-host-glue.log",
        )

    format_name = "win64" if target == "windows" else "elf64"
    _run(
        [
            nasm,
            "-f",
            format_name,
            str(assembly),
            "-o",
            str(python_object),
        ],
        log=work_dir / f"{target}-nasm.log",
    )

    link_objects = [
        str(python_object),
        str(base_glue_object),
        str(traceback_stub_object),
    ]
    if host_bridge:
        link_objects.append(str(host_glue_object))

    if target == "linux":
        version_script = work_dir / "portapy.map"
        version_script.write_text(
            linux_version_script(host_bridge=host_bridge),
            encoding="utf-8",
        )
        link_command = [
            gcc,
            "-shared",
            *link_objects,
            f"-Wl,--version-script={version_script}",
            "-o",
            str(output),
        ]
    else:
        definition = work_dir / "portapy.def"
        definition.write_text(
            windows_definition(host_bridge=host_bridge),
            encoding="ascii",
        )
        link_command = [
            gcc,
            "-shared",
            *link_objects,
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
        "abi_glue": str(base_glue.relative_to(REPOSITORY_ROOT)),
        "abi_glue_sha256": _sha256(base_glue),
        "traceback_filename_stub": str(traceback_stub.relative_to(REPOSITORY_ROOT)),
        "traceback_filename_stub_sha256": _sha256(traceback_stub),
        "host_bridge": host_bridge,
        "public_exports": list(public_exports(host_bridge=host_bridge)),
        "python_built_runtime": True,
    }
    if host_bridge:
        metadata["host_abi_glue"] = str(host_glue.relative_to(REPOSITORY_ROOT))
        metadata["host_abi_glue_sha256"] = _sha256(host_glue)
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
    parser.add_argument("--host-bridge", action="store_true")
    args = parser.parse_args(argv)
    try:
        metadata = build_native(
            target=args.target,
            output=args.output,
            source=args.source,
            work_dir=args.work_dir,
            host_bridge=args.host_bridge,
        )
    except BuildFailure as error:
        print(f"portapy native build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
