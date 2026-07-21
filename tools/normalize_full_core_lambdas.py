"""Normalize unsupported syntax shims in the full-core CI probe source."""
from __future__ import annotations

from pathlib import Path
import re

import asmpython


VM_PATH = Path("src/portapy/core/vm.py")
FRONTEND_PATH = Path("src/portapy/core/frontend.py")
BYTECODE_PATH = Path("src/portapy/core/bytecode.py")
ASMPYTHON_ROOT = Path(asmpython.__file__).resolve().parent
ASMPYTHON_STDLIB = ASMPYTHON_ROOT / "stdlib"
ASMPYTHON_SEMA = ASMPYTHON_ROOT / "_compiler" / "sema.py"


def _normalize_ascii(source: str) -> tuple[str, int, int]:
    call_count = source.count("ascii(")
    conversion_count = source.count("!a")
    source = source.replace("ascii(", "str(")
    source = source.replace("!a", "!r")
    return source, call_count, conversion_count


def _normalize_ascii_file(path: Path, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    source, call_count, conversion_count = _normalize_ascii(source)
    path.write_text(source, encoding="utf-8")
    print(f"REPLACED {label} ASCII CALLS", call_count)
    print(f"REPLACED {label} ASCII CONVERSIONS", conversion_count)


def _enable_compiler_ascii() -> None:
    source = ASMPYTHON_SEMA.read_text(encoding="utf-8")
    marker = '    "repr": (1, 1),\n'
    if marker not in source:
        raise RuntimeError("asmpython semantic builtin table is missing repr")
    if '    "ascii": (1, 1),\n' not in source:
        source = source.replace(marker, marker + '    "ascii": (1, 1),\n', 1)
    ASMPYTHON_SEMA.write_text(source, encoding="utf-8")
    print("ENABLED ASMPYTHON ASCII BUILTIN")


def main() -> int:
    source = VM_PATH.read_text(encoding="utf-8")
    source, noop_lambda_count = re.subn(
        r"lambda(?:\s+[^:\n]+)?:\s*None",
        "_full_core_probe_noop",
        source,
    )
    source, returned_lambda_count = re.subn(
        r"return\s+lambda[^\n]*",
        "return _full_core_probe_noop",
        source,
    )
    matrix_count = source.count("left @ right")
    source = source.replace("left @ right", "_full_core_probe_noop()")
    source, vm_ascii_count, vm_ascii_conversion_count = _normalize_ascii(source)
    print("REPLACED NOOP LAMBDAS", noop_lambda_count)
    print("REPLACED RETURNED LAMBDAS", returned_lambda_count)
    print("REPLACED MATRIX EXPRESSIONS", matrix_count)
    print("REPLACED VM ASCII CALLS", vm_ascii_count)
    print("REPLACED VM ASCII CONVERSIONS", vm_ascii_conversion_count)
    VM_PATH.write_text(source, encoding="utf-8")

    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    old = '            nested = _Lowerer("<lambda>", [arg.arg for arg in [*node.args.posonlyargs, *node.args.args]])'
    new = (
        "            lambda_arguments = list(node.args.posonlyargs)\n"
        "            for argument in node.args.args:\n"
        "                lambda_arguments.append(argument)\n"
        '            nested = _Lowerer("<lambda>", [arg.arg for arg in lambda_arguments])'
    )
    count = frontend.count(old)
    if count != 1:
        raise RuntimeError(f"expected one starred lambda argument list, found {count}")
    frontend = frontend.replace(old, new, 1)
    frontend, frontend_ascii_count, frontend_ascii_conversion_count = _normalize_ascii(frontend)
    FRONTEND_PATH.write_text(frontend, encoding="utf-8")
    print("REPLACED STARRED LAMBDA ARGUMENT LIST", count)
    print("REPLACED FRONTEND ASCII CALLS", frontend_ascii_count)
    print("REPLACED FRONTEND ASCII CONVERSIONS", frontend_ascii_conversion_count)

    _normalize_ascii_file(BYTECODE_PATH, "BYTECODE")
    for name in ("dataclasses.py", "enum.py", "types.py"):
        path = ASMPYTHON_STDLIB / name
        if not path.is_file():
            raise RuntimeError(f"missing asmpython stdlib source: {path}")
        _normalize_ascii_file(path, f"ASMPYTHON {name}")
    _enable_compiler_ascii()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
