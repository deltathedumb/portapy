"""Build PortaPy's full parser/VM Runtime behind the stable public C ABI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import tools.build_native as base_build
from tools.build_native import BuildFailure, _sha256
from tools.build_native_host_calls import _upgrade_linked_artifact
from tools.elf_runtime_abi import fix_linux_runtime_abi
from tools.nasm_direct_float_abi import append_direct_float_abi
from tools.native_surface import public_exports
from tools.normalize_full_core_validation import main as normalize_full_runtime
from tools.python_surface import PYTHON_MODULE_EXPORTS


SOURCE = REPOSITORY_ROOT / "src" / "portapy" / "native_full_reference_entry.py"
COMPILER_WRAPPER = REPOSITORY_ROOT / "tools" / "run_full_core_asmpython.py"


def _prepare_full_runtime_sources() -> None:
    """Apply the complete verified native normalization pipeline once."""
    normalize_full_runtime()


def _install_full_runtime_compiler() -> None:
    """Route production compilation through the proven full-core CLI wrapper."""

    def compile_python_source(
        *,
        target: str,
        source: Path,
        output: Path,
        build_log: Path,
    ) -> Path:
        command = [
            sys.executable,
            str(COMPILER_WRAPPER),
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
        return assembly

    base_build._compile_python_source = compile_python_source


def _install_full_runtime_transforms() -> None:
    original_transform = base_build._transform_assembly

    def transform(
        assembly: Path,
        *,
        target: str,
        host_bridge: bool,
    ) -> None:
        original_float = base_build.append_float_abi
        try:
            base_build.append_float_abi = append_direct_float_abi
            original_transform(
                assembly,
                target=target,
                host_bridge=host_bridge,
            )
        finally:
            base_build.append_float_abi = original_float

        if target == "linux":
            source = assembly.read_text(encoding="utf-8")
            marker = "section .rodata"
            count = source.count(marker)
            if count < 1:
                raise BuildFailure(
                    "full Runtime assembly has no relocatable constant section"
                )
            source = source.replace(marker, "section .data")
            source, malloc_count, realloc_count = fix_linux_runtime_abi(source)
            assembly.write_text(source, encoding="utf-8")
            print("MOVED FULL RUNTIME RELOCATABLE CONSTANTS", count)
            print(
                "FIXED FULL RUNTIME ELF ALLOCATION ABI",
                malloc_count,
                realloc_count,
            )

    base_build._transform_assembly = transform


def build_full_runtime(
    *,
    target: str,
    output: Path,
    work_dir: Path,
    normalize: bool = True,
) -> dict[str, object]:
    if normalize:
        _prepare_full_runtime_sources()
    _install_full_runtime_compiler()
    _install_full_runtime_transforms()

    metadata = base_build.build_native(
        target=target,
        output=output,
        source=SOURCE,
        work_dir=work_dir,
        host_bridge=True,
    )
    _upgrade_linked_artifact(
        target=target,
        output=output.resolve(),
        work_dir=work_dir.resolve(),
    )

    metadata["size"] = output.stat().st_size
    metadata["sha256"] = _sha256(output)
    metadata["full_frontend_vm"] = True
    metadata["standalone_parser"] = True
    metadata["reference_runtime_handles"] = True
    metadata["host_calls"] = True
    metadata["native_environment_adapter"] = True
    metadata["public_environment_api"] = True
    metadata["public_tuple_abi"] = True
    metadata["public_dict_abi"] = True
    metadata["public_list_abi"] = True
    metadata["direct_float_abi"] = True
    metadata["public_exports"] = list(
        public_exports(host_bridge=True, host_calls=True)
    )
    metadata["python_module_exports"] = list(PYTHON_MODULE_EXPORTS)
    metadata["python_module_entry"] = "portapy"
    metadata_path = output.with_suffix(output.suffix + ".json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument(
        "--already-normalized",
        action="store_true",
        help="skip source materialization/normalization",
    )
    args = parser.parse_args(argv)
    try:
        metadata = build_full_runtime(
            target=args.target,
            output=args.output.resolve(),
            work_dir=args.work_dir.resolve(),
            normalize=not args.already_normalized,
        )
    except (BuildFailure, ValueError, RuntimeError) as error:
        print(f"portapy full Runtime build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(metadata, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
