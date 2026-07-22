"""Teach the native ABI kind tracker about user-function return values."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_HELPERS = r'''
_native_function_return_kinds: dict[str, int] = {}


def _native_function_kind_key(runtime: int, name: str) -> str:
    return str(runtime) + ":" + name


def _native_function_return_kind(runtime: int, name: str) -> int:
    return _native_function_return_kinds.get(
        _native_function_kind_key(runtime, name),
        PORTAPY_VALUE_OBJECT,
    )


def _native_set_function_return_kind(runtime: int, name: str, kind: int) -> None:
    _native_function_return_kinds[_native_function_kind_key(runtime, name)] = kind


def _native_top_level_function_name(text: str) -> str:
    start = 0
    if text.startswith("def "):
        start = 4
    elif text.startswith("async def "):
        start = 10
    else:
        return ""
    end = text.find("(", start)
    if end <= start:
        return ""
    name = text[start:end].strip()
    if not _native_is_identifier(name):
        return ""
    return name


def _native_record_function_return_kinds(runtime: int, source: str) -> None:
    current = ""
    position = 0
    while position <= len(source):
        line_end = position
        while line_end < len(source) and source[line_end] != "\n":
            line_end += 1
        line = source[position:line_end]
        indentation = 0
        while indentation < len(line) and (line[indentation] == " " or line[indentation] == "\t"):
            indentation += 1
        text = line[indentation:].strip()
        if indentation == 0 and len(text) != 0:
            current = _native_top_level_function_name(text)
            if current != "":
                _native_set_function_return_kind(runtime, current, PORTAPY_VALUE_OBJECT)
        elif current != "" and text.startswith("return"):
            expression = text[6:].strip()
            if len(expression) != 0:
                kind = _native_expression_kind(runtime, expression)
                previous = _native_function_return_kind(runtime, current)
                if previous == PORTAPY_VALUE_OBJECT or previous == kind:
                    _native_set_function_return_kind(runtime, current, kind)
                else:
                    _native_set_function_return_kind(runtime, current, PORTAPY_VALUE_OBJECT)
        if line_end >= len(source):
            break
        position = line_end + 1
'''


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.expression_rewritten = False
        self.source_rewritten = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node = self.generic_visit(node)
        if node.name == "_native_expression_kind":
            for statement in node.body:
                if not isinstance(statement, ast.If):
                    continue
                test = statement.test
                if not (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "open_at"
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Gt)
                ):
                    continue
                replacement = ast.parse(
                    '''
callee = text[0:open_at].strip()
if _native_is_identifier(callee):
    callee_kind = _native_global_kind(runtime, callee)
    if callee_kind == PORTAPY_VALUE_CALLABLE:
        return _native_function_return_kind(runtime, callee)
'''
                ).body
                statement.body = replacement
                self.expression_rewritten = True
                break
        elif node.name == "_native_record_source_kinds":
            node.body.insert(
                0,
                ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id="_native_record_function_return_kinds", ctx=ast.Load()),
                        args=[
                            ast.Name(id="runtime", ctx=ast.Load()),
                            ast.Name(id="source", ctx=ast.Load()),
                        ],
                        keywords=[],
                    )
                ),
            )
            self.source_rewritten = True
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.FunctionDef)
        and node.name == "_native_record_function_return_kinds"
        for node in module.body
    ):
        raise RuntimeError("native function return-kind tracking is already installed")
    rewrite = _Rewrite()
    module = rewrite.visit(module)
    if not rewrite.expression_rewritten:
        raise RuntimeError("native callable expression-kind branch was not found")
    if not rewrite.source_rewritten:
        raise RuntimeError("native source-kind recorder was not found")
    module.body.extend(ast.parse(_HELPERS).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")
    text = ast.unparse(ast.parse(source))
    required = (
        "_native_record_function_return_kinds(runtime, source)",
        "return _native_function_return_kind(runtime, callee)",
        "_native_function_return_kinds",
    )
    absent = [marker for marker in required if marker not in text]
    if absent:
        raise RuntimeError(f"native function return-kind validation failed: {absent}")
    print("NORMALIZED NATIVE FUNCTION RETURN KINDS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
