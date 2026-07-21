"""Prepare PortaPy's standalone AST bridge for the native full-core build."""
from __future__ import annotations

from pathlib import Path

from asmpython._compiler.lexer import Lexer
from asmpython._compiler.parser import Parser

from tools.vendor_full_core_native_parser import vendor_native_parser


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
NATIVE_AST_PATH = Path("src/portapy/core/native_ast.py")
RUNTIME_PATH = Path("src/portapy/core/native_parser_runtime.py")


def _validate_generated_parser() -> None:
    runtime = Parser(Lexer(RUNTIME_PATH.read_text(encoding="utf-8")).tokenize()).parse()
    bridge = Parser(Lexer(NATIVE_AST_PATH.read_text(encoding="utf-8")).tokenize()).parse()
    bridge_functions = {function.name for function in bridge.funcs}
    required = {"parse", "walk", "unparse"}
    missing = sorted(required - bridge_functions)
    if missing:
        raise RuntimeError(
            "standalone AST parser lost required functions: " + ", ".join(missing)
        )
    if not runtime.classes or not runtime.funcs:
        raise RuntimeError("generated parser runtime has no definitions")
    print(
        "VALIDATED PRIVATE NATIVE PARSER",
        len(runtime.funcs),
        len(runtime.classes),
        len(bridge_functions),
    )


def _select_native_ast() -> None:
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    import_old = "import ast\n"
    import_new = (
        "from . import native_ast as ast\n"
        "from .native_ast import parse as _native_ast_parse\n"
    )
    import_count = source.count(import_old)
    if import_count != 1:
        raise RuntimeError(
            f"expected one frontend ast import, found {import_count}"
        )
    source = source.replace(import_old, import_new, 1)

    call_old = "module = ast.parse(source, filename=filename, mode=mode)"
    call_new = "module = _native_ast_parse(source, filename, mode)"
    call_count = source.count(call_old)
    if call_count != 1:
        raise RuntimeError(
            f"expected one frontend ast.parse call, found {call_count}"
        )
    source = source.replace(call_old, call_new, 1)

    FRONTEND_PATH.write_text(source, encoding="utf-8")
    print("ENABLED DIRECT SELF-HOSTED PARSER CALL", call_count)


def main() -> int:
    vendor_native_parser()
    _validate_generated_parser()
    _select_native_ast()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
