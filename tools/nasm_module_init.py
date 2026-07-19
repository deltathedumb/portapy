"""Convert asmpython's generated executable entry into a library initializer.

The generated module body is authoritative Python-compiled code. This build/ABI
pass only changes its entry/exit convention: ``main`` becomes a private callable
initializer, its terminal ``exit(0)`` becomes a normal return, and a public
zero-argument wrapper supplies deterministic argc/argv values.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_TOP_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_$?][\w.$?@]*):\s*(?:;.*)?$")


def make_module_initializer(
    source: str,
    *,
    target: str,
    public_symbol: str,
) -> str:
    if target not in ("linux", "windows"):
        raise ValueError(f"unsupported initializer target: {target}")

    lines = source.splitlines()
    main_index = -1
    main_global_index = -1
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped == "main:":
            main_index = index
        if stripped == "global main":
            main_global_index = index
    if main_index < 0:
        raise ValueError("generated NASM does not define main")
    if main_global_index < 0:
        raise ValueError("generated NASM does not declare global main")

    end_index = len(lines)
    for index in range(main_index + 1, len(lines)):
        match = _TOP_LABEL_RE.match(lines[index].strip())
        if match is not None:
            end_index = index
            break

    exit_indices: list[int] = []
    for index in range(main_index + 1, end_index):
        stripped = lines[index].strip()
        if stripped == "call exit" or stripped == "call exit wrt ..plt":
            exit_indices.append(index)
    if not exit_indices:
        raise ValueError("generated main has no terminal exit call")
    exit_index = exit_indices[-1]

    lines[main_global_index] = "; executable global main removed for shared library"
    lines[main_index] = "_portapy_module_init:"
    indent = lines[exit_index][: len(lines[exit_index]) - len(lines[exit_index].lstrip())]
    lines[exit_index:exit_index + 1] = [
        f"{indent}xor eax, eax",
        f"{indent}mov rsp, rbp",
        f"{indent}pop rbp",
        f"{indent}ret",
    ]

    wrapper: list[str] = ["", "section .text", f"{public_symbol}:"]
    if target == "linux":
        wrapper.extend(
            [
                "    sub rsp, 8",
                "    xor edi, edi",
                "    xor esi, esi",
                "    call _portapy_module_init",
                "    add rsp, 8",
                "    ret",
            ]
        )
    else:
        wrapper.extend(
            [
                "    sub rsp, 40",
                "    xor ecx, ecx",
                "    xor edx, edx",
                "    call _portapy_module_init",
                "    add rsp, 40",
                "    ret",
            ]
        )
    lines.extend(wrapper)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--target", choices=("linux", "windows"), required=True)
    parser.add_argument("--public-symbol", default="portapy_library_initialize")
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    rewritten = make_module_initializer(
        args.assembly.read_text(encoding="utf-8"),
        target=args.target,
        public_symbol=args.public_symbol,
    )
    output.write_text(rewritten, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
