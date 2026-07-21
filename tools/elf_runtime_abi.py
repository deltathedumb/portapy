"""Fix System V argument registers in generated private runtime helpers.

The pinned legacy backend emits a small group of handwritten container/string
helpers with Win64 RCX/RDX argument setup even for ELF targets. Compiled Python
code already uses the correct ABI, so this pass is deliberately restricted to
``_runtime_*`` helper bodies and only rewrites external allocation calls whose
recent instructions have no RDI setup.
"""
from __future__ import annotations

import argparse
from pathlib import Path


_MALLOC_CALLS = {"call malloc", "call malloc wrt ..plt"}
_REALLOC_CALLS = {"call realloc", "call realloc wrt ..plt"}


def _top_level_label(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.endswith(":") or stripped.startswith("."):
        return None
    return stripped[:-1]


def fix_linux_runtime_abi(source: str) -> tuple[str, int, int]:
    lines = source.splitlines()
    output: list[str] = []
    current_function = ""
    malloc_rewrites = 0
    realloc_rewrites = 0

    for index, raw in enumerate(lines):
        label = _top_level_label(raw)
        if label is not None:
            current_function = label
        stripped = raw.strip()
        recent = "\n".join(lines[max(0, index - 8):index])
        indent = raw[: len(raw) - len(raw.lstrip())]

        if (
            current_function.startswith("_runtime_")
            and stripped in _MALLOC_CALLS
            and "mov rdi," not in recent
            and (
                "mov rcx," in recent
                or "shl rcx," in recent
                or "inc rcx" in recent
            )
        ):
            output.append(indent + "mov rdi, rcx")
            malloc_rewrites += 1

        if (
            current_function.startswith("_runtime_")
            and stripped in _REALLOC_CALLS
            and "mov rdi," not in recent
            and "mov rcx," in recent
            and "mov rdx," in recent
        ):
            output.append(indent + "mov rdi, rcx")
            output.append(indent + "mov rsi, rdx")
            realloc_rewrites += 1

        output.append(raw)

    if malloc_rewrites < 10:
        raise ValueError(
            "generated ELF runtime exposed fewer malloc ABI mismatches than "
            f"expected: {malloc_rewrites}"
        )
    if realloc_rewrites < 1:
        raise ValueError(
            "generated ELF runtime exposed no realloc ABI mismatch"
        )
    return "\n".join(output) + "\n", malloc_rewrites, realloc_rewrites


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    rewritten, malloc_count, realloc_count = fix_linux_runtime_abi(
        args.assembly.read_text(encoding="utf-8")
    )
    output.write_text(rewritten, encoding="utf-8")
    print("FIXED ELF RUNTIME ABI", malloc_count, realloc_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
