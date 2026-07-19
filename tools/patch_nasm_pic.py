"""Normalize asmpython's Linux NASM output for shared-library linking.

The legacy backend already emits RIP-relative references for local data, but its
external calls use direct PC32 relocations. Those are valid for executables and
invalid for preemptible symbols in ELF shared objects. This build-only pass sends
external function calls through the PLT and external data through the GOT.

No PortaPy interpreter semantics live here; this only adjusts relocation forms.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


_CALL_RE = re.compile(r"^(?P<indent>\s*)call\s+(?P<symbol>[A-Za-z_.$][\w.$@]*)\s*$")
_LOAD_RE = re.compile(
    r"^(?P<indent>\s*)mov\s+(?P<reg>[A-Za-z0-9]+),\s*\[(?P<symbol>[A-Za-z_.$][\w.$@]*)\]\s*$"
)


def patch_source(source: str) -> str:
    lines = source.splitlines()
    externs: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("extern "):
            externs.update(
                symbol.strip()
                for symbol in stripped[len("extern ") :].split(",")
                if symbol.strip()
            )

    patched: list[str] = []
    for line in lines:
        call_match = _CALL_RE.match(line)
        if call_match and call_match.group("symbol") in externs:
            patched.append(
                f"{call_match.group('indent')}call "
                f"{call_match.group('symbol')} wrt ..plt"
            )
            continue

        load_match = _LOAD_RE.match(line)
        if load_match and load_match.group("symbol") in externs:
            reg = load_match.group("reg")
            indent = load_match.group("indent")
            symbol = load_match.group("symbol")
            patched.append(f"{indent}mov {reg}, [rel {symbol} wrt ..got]")
            patched.append(f"{indent}mov {reg}, [{reg}]")
            continue

        patched.append(line)

    result = "\n".join(patched) + ("\n" if source.endswith("\n") else "")

    # Refuse to silently leave a bare external reference in an instruction.
    for line_number, line in enumerate(result.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("extern "):
            continue
        for symbol in externs:
            if not re.search(rf"\b{re.escape(symbol)}\b", stripped):
                continue
            if stripped.startswith("call ") and "wrt ..plt" in stripped:
                break
            if "wrt ..got" in stripped:
                break
            raise ValueError(
                f"unhandled external reference {symbol!r} at line "
                f"{line_number}: {stripped}"
            )

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    source = args.path.read_text(encoding="utf-8")
    args.path.write_text(patch_source(source), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
