"""Print source-positioned asmpython parse failures for PortaPy core files."""
from __future__ import annotations

import argparse
from pathlib import Path

from asmpython._compiler.lexer import Lexer
from asmpython._compiler.parser import Parser


def audit(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    try:
        Parser(Lexer(source).tokenize()).parse()
    except Exception as error:
        position = getattr(error, "pos", None)
        line = getattr(position, "line", 0)
        column = getattr(position, "col", 0)
        print(f"FAIL {path} {type(error).__name__}: {error}")
        if line > 0:
            lines = source.splitlines()
            if line <= len(lines):
                text = lines[line - 1]
                print(f"  {line}:{column}: {text}")
                print("  " + " " * max(column - 1, 0) + "^")
        return False
    print(f"PASS {path}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    success = True
    for path in args.paths:
        if not audit(path):
            success = False
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
