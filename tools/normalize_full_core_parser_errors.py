"""Make the embedded parser's unexpected-token diagnostic compiler-safe.

INDENT/DEDENT token values are integers. The pinned compiler lowers the original
f-string as raw string concatenation and passes that integer to ``strlen``, causing
a segfault before PortaPy can report a compile error. The public ABI only promises
the error category and source coordinates, so use a stable constant message while
preserving the token position and error code.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_PARSER_CLASS = "_npr_parser_Parser"


def _parser_method(module: ast.Module, name: str) -> ast.FunctionDef:
    classes = [
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == _PARSER_CLASS
    ]
    if len(classes) != 1:
        raise RuntimeError(
            f"embedded native Parser expected one class, found {len(classes)}"
        )
    methods = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(methods) != 1:
        raise RuntimeError(
            f"embedded native Parser.{name} expected one method, found {len(methods)}"
        )
    return methods[0]


def _is_parse_error_call(node: ast.expr | None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"ParseError", "_npr_errors_ParseError"}
        and bool(node.args)
    )


def _contains_unexpected_token_text(node: ast.expr) -> bool:
    return any(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and "unexpected token" in item.value
        for item in ast.walk(node)
    )


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    method = _parser_method(module, "_parse_primary")

    rewrites = 0
    for node in ast.walk(method):
        if not isinstance(node, ast.Raise) or not _is_parse_error_call(node.exc):
            continue
        assert isinstance(node.exc, ast.Call)
        if not _contains_unexpected_token_text(node.exc.args[0]):
            continue
        node.exc.args[0] = ast.copy_location(
            ast.Constant(value="unexpected token"),
            node.exc.args[0],
        )
        rewrites += 1

    if rewrites != 1:
        raise RuntimeError(
            "native parser unexpected-token diagnostic expected one rewrite, "
            f"found {rewrites}"
        )

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    verified_method = _parser_method(verified, "_parse_primary")
    messages = [
        node.exc.args[0]
        for node in ast.walk(verified_method)
        if isinstance(node, ast.Raise)
        and _is_parse_error_call(node.exc)
        and isinstance(node.exc, ast.Call)
        and node.exc.args
        and isinstance(node.exc.args[0], ast.Constant)
        and node.exc.args[0].value == "unexpected token"
    ]
    if len(messages) != rewrites:
        raise RuntimeError(
            "native parser unexpected-token diagnostic was not preserved"
        )

    print("NORMALIZED NATIVE UNEXPECTED-TOKEN ERROR", rewrites)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
