"""Finalize generated NASM source and declare its public-symbol allowlist.

This build/ABI pass validates exports and aliases, then repairs generated
exception-handler epilogues before assembly. Requested symbols and alias
targets must exist or the pass fails closed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.nasm_exception_handlers import restore_exception_handler_epilogues


_SYMBOL = r"[A-Za-z_.$?][\w.$?@]*"
_LABEL_RE = re.compile(rf"^(?P<label>{_SYMBOL}):\s*(?:;.*)?$")
_GLOBAL_RE = re.compile(r"^\s*global\s+(?P<payload>.+?)\s*$")
_SYMBOL_RE = re.compile(rf"^{_SYMBOL}$")


def declare_exports(
    source: str,
    exports: list[str],
    aliases: dict[str, str] | None = None,
) -> str:
    aliases = aliases or {}
    requested: list[str] = []
    for symbol in [*exports, *aliases.keys()]:
        if symbol and symbol not in requested:
            requested.append(symbol)

    lines = source.splitlines()
    label_indices: dict[str, int] = {}
    globals_seen: set[str] = set()
    declaration_insertion = 0

    for index, raw in enumerate(lines):
        label_match = _LABEL_RE.match(raw.strip())
        if label_match is not None:
            label_indices[label_match.group("label")] = index
        global_match = _GLOBAL_RE.match(raw)
        if global_match is not None:
            for symbol in global_match.group("payload").replace(",", " ").split():
                globals_seen.add(symbol)
            declaration_insertion = index + 1
        elif raw.strip().lower().startswith(("bits ", "default ")):
            declaration_insertion = index + 1

    for alias, target in aliases.items():
        if not _SYMBOL_RE.match(alias) or not _SYMBOL_RE.match(target):
            raise ValueError(f"invalid NASM alias {alias!r}={target!r}")
        if alias in label_indices:
            raise ValueError(f"NASM alias label already exists: {alias}")
        if target not in label_indices:
            raise ValueError(f"NASM alias target not found: {target}")

    missing = [
        symbol
        for symbol in requested
        if symbol not in label_indices and symbol not in aliases
    ]
    if missing:
        raise ValueError(
            "requested NASM export label(s) not found: " + ", ".join(missing)
        )

    aliases_by_index: dict[int, list[str]] = {}
    for alias, target in aliases.items():
        aliases_by_index.setdefault(label_indices[target], []).append(alias)
    for index in sorted(aliases_by_index, reverse=True):
        lines[index:index] = [f"{alias}:" for alias in aliases_by_index[index]]

    declarations = [
        f"global {symbol}" for symbol in requested if symbol not in globals_seen
    ]
    if declarations:
        lines[declaration_insertion:declaration_insertion] = declarations

    rewritten, function_count, epilogue_count = restore_exception_handler_epilogues(
        "\n".join(lines) + "\n"
    )
    if function_count:
        print(
            "RESTORED EXCEPTION HANDLER EPILOGUES",
            function_count,
            epilogue_count,
        )
    return rewritten


def _parse_alias(value: str) -> tuple[str, str]:
    alias, separator, target = value.partition("=")
    if not separator or not alias or not target:
        raise argparse.ArgumentTypeError("alias must use PUBLIC=TARGET")
    return alias, target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly", type=Path)
    parser.add_argument("--export", action="append", default=[])
    parser.add_argument("--alias", action="append", type=_parse_alias, default=[])
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output or args.assembly
    rewritten = declare_exports(
        args.assembly.read_text(encoding="utf-8"),
        args.export,
        dict(args.alias),
    )
    output.write_text(rewritten, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
