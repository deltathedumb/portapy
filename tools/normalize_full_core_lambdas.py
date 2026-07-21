"""Normalize unsupported syntax shims in the full-core CI probe source."""
from __future__ import annotations

from pathlib import Path
import re


VM_PATH = Path("src/portapy/core/vm.py")
FRONTEND_PATH = Path("src/portapy/core/frontend.py")


def _normalize_ascii(source: str) -> tuple[str, int, int]:
    call_count = source.count("ascii(")
    conversion_count = source.count("!a")
    source = source.replace("ascii(", "str(")
    source = source.replace("!a", "!r")
    return source, call_count, conversion_count


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
