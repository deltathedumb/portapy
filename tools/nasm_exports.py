"""Declare an explicit public-symbol allowlist in generated NASM source.

This is build/ABI glue. It never changes function bodies or interpreter
semantics, and it fails if a requested public label is absent.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_.$?][\w.$?@]*):\s*(?:;.*)?$")
_GLOBAL_RE = re.compile(r"^\s*global\s+(?P<payload>.+?)\s*$")


def declare_exports(source: str, exports: list[str]) -> str:
    requested: list[str] = []
    for symbol in exports:
        if symbol and symbol not in requested:
            requested.append(symbol)

    lines = source.splitlines()
    labels: set[str] = set()
    globals_seen: set[str] = set()
    insertion = 0

    for index, raw in enumerate(lines):
        label_match = _LABEL_RE.match(raw.strip())
        if label_match is not None:
            labels.add(label_match.group("label"))
        global_match = _GLOBAL_RE.match(raw)
        if global_match is not None:
            for symbol in global_match.group("payload").replace(",", " ").split():
                globals_seen.add(symbol)
            insertion = index + 1
        elif raw.strip().lower().startswith(("bits ", "default ")):
            insertion = index + 1

    missing = [symbol for symbol in requested if symbol not in labels]
    if missing:
        raise ValueError(
            "requested NASM export label(s) not found: " + ", ".join(missing)
        )

    declarations = [
        f"global {symbol}" for symbol in requested if symbol not in globals_seen
    ]
    if declarations:
        lines[insertion:insertion] = declarations
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--export", action="append", default=[])
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    rewritten = declare_exports(
        args.assembly.read_text(encoding="utf-8"),
        args.export,
    )
    output.write_text(rewritten, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
