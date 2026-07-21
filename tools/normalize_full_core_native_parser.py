"""Prepare PortaPy's standalone AST bridge for the native full-core build."""
from __future__ import annotations

from pathlib import Path

from asmpython._compiler.lexer import Lexer
from asmpython._compiler.parser import Parser

from tools.normalize_full_core_probe import _expand_compact_statements


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
NATIVE_AST_PATH = Path("src/portapy/core/native_ast.py")


def _normalize_native_ast() -> None:
    source = NATIVE_AST_PATH.read_text(encoding="utf-8")
    normalized = _expand_compact_statements(source)
    if normalized == source:
        raise RuntimeError("standalone AST source contained no compact statements")

    parsed = Parser(Lexer(normalized).tokenize()).parse()
    function_names = {function.name for function in parsed.funcs}
    required = {"parse", "walk", "unparse"}
    missing = sorted(required - function_names)
    if missing:
        raise RuntimeError(
            "standalone AST parser lost required functions: " + ", ".join(missing)
        )

    NATIVE_AST_PATH.write_text(normalized, encoding="utf-8")
    print("NORMALIZED STANDALONE NATIVE AST", len(function_names))


def _select_native_ast() -> None:
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    old = "import ast\n"
    new = "from . import native_ast as ast\n"
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"expected one frontend ast import, found {count}")
    FRONTEND_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("ENABLED SELF-HOSTED NATIVE PARSER", count)


def main() -> int:
    _normalize_native_ast()
    _select_native_ast()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
