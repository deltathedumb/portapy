"""Rewrite asmpython legacy NASM output into ELF shared-library-safe PIC.

This is build/ABI glue only. It does not implement any PortaPy interpreter
semantics. The pass is intentionally narrow and fails on unsupported references
rather than producing a library with text relocations.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_EXTERN_DATA = {"stdin", "stdout", "stderr", "environ"}
_CALL_RE = re.compile(r"^(?P<indent>\s*)(?P<op>call|jmp)\s+(?P<symbol>[A-Za-z_.$?][\w.$?@]*)\s*$")
_DATA_LOAD_RE = re.compile(
    r"^(?P<indent>\s*)mov\s+(?P<register>[A-Za-z][A-Za-z0-9]*),\s*"
    r"\[(?:rel\s+)?(?P<symbol>[A-Za-z_.$?][\w.$?@]*)\]\s*$"
)
_EXTERNAL_MEMORY_RE = re.compile(
    r"\[(?:rel\s+)?(?P<symbol>[A-Za-z_.$?][\w.$?@]*)[^\]]*\]"
)


def _extern_symbols(lines: list[str]) -> set[str]:
    symbols: set[str] = set()
    for raw in lines:
        stripped = raw.strip()
        if not stripped.startswith("extern "):
            continue
        payload = stripped.split(None, 1)[1]
        for symbol in payload.replace(",", " ").split():
            symbols.add(symbol)
    return symbols


def make_elf_pic(source: str) -> str:
    lines = source.splitlines()
    externs = _extern_symbols(lines)
    output: list[str] = []

    for line_number, raw in enumerate(lines, start=1):
        call_match = _CALL_RE.match(raw)
        if call_match is not None:
            symbol = call_match.group("symbol")
            if symbol in externs:
                output.append(
                    f'{call_match.group("indent")}{call_match.group("op")} '
                    f'{symbol} wrt ..plt'
                )
                continue

        data_match = _DATA_LOAD_RE.match(raw)
        if data_match is not None:
            symbol = data_match.group("symbol")
            if symbol in externs and symbol in _EXTERN_DATA:
                indent = data_match.group("indent")
                register = data_match.group("register")
                output.append(f"{indent}mov {register}, [rel {symbol} wrt ..got]")
                output.append(f"{indent}mov {register}, [{register}]")
                continue

        for memory_match in _EXTERNAL_MEMORY_RE.finditer(raw):
            symbol = memory_match.group("symbol")
            if symbol in externs:
                raise ValueError(
                    f"line {line_number}: unsupported external memory reference "
                    f"to {symbol!r}: {raw.strip()}"
                )

        output.append(raw)

    if not any(line.strip() == 'section .note.GNU-stack noalloc noexec nowrite progbits' for line in output):
        output.extend(["", "section .note.GNU-stack noalloc noexec nowrite progbits"])
    return "\n".join(output) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    rewritten = make_elf_pic(args.assembly.read_text(encoding="utf-8"))
    output.write_text(rewritten, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
