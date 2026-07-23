"""Allow full expressions in native function default arguments.

The vendored parser's ``_parse_optional_default`` delegates to a deliberately
restricted literal parser inherited from the compiler frontend. PortaPy captures
Python defaults at definition time, so defaults such as ``seed + 2`` must use the
ordinary expression grammar and stop naturally at the parameter comma or closing
parenthesis.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/core/native_ast.py")
_METHOD = "_parse_optional_default"


_REPLACEMENT = '''if not self._check("OP", "="):
    return None
self._eat()
return self._parse_expr()
'''


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"), filename=str(PATH))
    methods = [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef) and node.name == _METHOD
    ]
    if len(methods) != 1:
        raise RuntimeError(
            f"native default parser expected one {_METHOD}, found {len(methods)}"
        )

    method = methods[0]
    original = ast.unparse(method)
    if "return self._parse_default_literal()" not in original:
        raise RuntimeError(
            "native default parser no longer has the restricted literal path"
        )
    method.body = ast.parse(_REPLACEMENT).body

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source, filename=str(PATH))
    repaired = [
        node
        for node in ast.walk(verified)
        if isinstance(node, ast.FunctionDef) and node.name == _METHOD
    ]
    if len(repaired) != 1:
        raise RuntimeError("native default expression parser was not preserved")
    text = ast.unparse(repaired[0])
    required = (
        "if not self._check('OP', '='):",
        "self._eat()",
        "return self._parse_expr()",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"native default expression repair was lost: {missing}")
    if "_parse_default_literal" in text:
        raise RuntimeError("restricted default-literal parser remains active")

    print("NORMALIZED NATIVE DEFAULT EXPRESSIONS", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
