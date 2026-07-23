"""Preserve source bytes literals at the native ABI boundary.

The current compiled VM retains a placeholder for bytes constants rather than their
original payload. Source kind tracking already knows which globals/eval results are
bytes, so this pass parses Python bytes-literal syntax into the native byte arena and
associates that exact payload with the public opaque handle.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_HELPERS = r'''
_native_literal_start: dict[str, int] = {}
_native_literal_size: dict[str, int] = {}


def _native_hex_value(char: str) -> int:
    code = ord(char)
    if code >= 48 and code <= 57:
        return code - 48
    if code >= 65 and code <= 70:
        return code - 55
    if code >= 97 and code <= 102:
        return code - 87
    return -1


def _native_is_octal(char: str) -> bool:
    code = ord(char)
    return code >= 48 and code <= 55


def _native_store_bytes_literal(key: str, expression: str) -> bool:
    text = expression.strip()
    index = 0
    while index < len(text) and (
        text[index] == "b"
        or text[index] == "B"
        or text[index] == "r"
        or text[index] == "R"
    ):
        index += 1
    prefix = text[0:index].lower()
    if "b" not in prefix or index >= len(text):
        return False
    quote = text[index]
    if quote != "'" and quote != '"':
        return False
    quote_size = 1
    if (
        index + 2 < len(text)
        and text[index + 1] == quote
        and text[index + 2] == quote
    ):
        quote_size = 3
    content_start = index + quote_size
    content_end = len(text) - quote_size
    if content_end < content_start:
        return False
    check = 0
    while check < quote_size:
        if text[content_end + check] != quote:
            return False
        check += 1
    raw = "r" in prefix
    start = len(_native_byte_data)
    count = 0
    index = content_start
    while index < content_end:
        char = text[index]
        value = -1
        if not raw and char == "\\":
            index += 1
            if index >= content_end:
                return False
            escape = text[index]
            if escape == "x":
                if index + 2 >= content_end:
                    return False
                high = _native_hex_value(text[index + 1])
                low = _native_hex_value(text[index + 2])
                if high < 0 or low < 0:
                    return False
                value = high * 16 + low
                index += 2
            elif _native_is_octal(escape):
                value = ord(escape) - 48
                digits = 1
                while (
                    digits < 3
                    and index + 1 < content_end
                    and _native_is_octal(text[index + 1])
                ):
                    index += 1
                    value = value * 8 + ord(text[index]) - 48
                    digits += 1
            elif escape == "n":
                value = 10
            elif escape == "r":
                value = 13
            elif escape == "t":
                value = 9
            elif escape == "b":
                value = 8
            elif escape == "f":
                value = 12
            elif escape == "v":
                value = 11
            elif escape == "a":
                value = 7
            elif escape == "\\":
                value = 92
            elif escape == "'":
                value = 39
            elif escape == '"':
                value = 34
            elif escape == "\n":
                index += 1
                continue
            else:
                _native_byte_data.append(92)
                count += 1
                value = ord(escape)
        else:
            value = ord(char)
        if value < 0 or value > 255:
            return False
        _native_byte_data.append(value)
        count += 1
        index += 1
    _native_literal_start[key] = start
    _native_literal_size[key] = count
    return True


def _native_record_global_bytes(
    runtime: int,
    name: str,
    expression: str,
) -> None:
    _native_store_bytes_literal(_native_kind_key(runtime, name), expression)


def _native_attach_global_bytes(runtime: int, name: str, handle: int) -> None:
    source_key = _native_kind_key(runtime, name)
    start = _native_literal_start.get(source_key, -1)
    if start < 0:
        return
    handle_key = _native_builder_key(runtime, handle)
    _native_literal_start[handle_key] = start
    _native_literal_size[handle_key] = _native_literal_size.get(source_key, 0)


def _native_attach_expression_bytes(
    runtime: int,
    expression: str,
    handle: int,
) -> None:
    _native_store_bytes_literal(
        _native_builder_key(runtime, handle),
        expression,
    )
'''


def _call_name(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
    )


def _inject_statement_recording(function: ast.FunctionDef) -> int:
    body: list[ast.stmt] = []
    count = 0
    for statement in function.body:
        body.append(statement)
        if (
            isinstance(statement, ast.Expr)
            and _call_name(statement.value, "_native_set_global_kind")
        ):
            body.extend(
                ast.parse(
                    '''if kind == PORTAPY_VALUE_BYTES:
    _native_record_global_bytes(runtime, name, text[equals + 1:])'''
                ).body
            )
            count += 1
    function.body = body
    return count


def _inject_after_handle_tag(function: ast.FunctionDef, *, mode: str) -> int:
    count = 0
    for node in ast.walk(function):
        if not isinstance(node, ast.If):
            continue
        for index, statement in enumerate(list(node.body)):
            if (
                isinstance(statement, ast.Expr)
                and _call_name(statement.value, "_native_set_handle_kind")
            ):
                if mode == "global":
                    source = "_native_attach_global_bytes(runtime, name_text, value)"
                else:
                    source = '''if _native_expression_kind(runtime, source_text) == PORTAPY_VALUE_BYTES:
    _native_attach_expression_bytes(runtime, source_text, value)'''
                node.body[index + 1:index + 1] = ast.parse(source).body
                count += 1
    return count


def _inject_literal_data(function: ast.FunctionDef, *, byte: bool) -> int:
    if byte:
        statements = ast.parse(
            '''literal_key = _native_builder_key(runtime, handle)
literal_start = _native_literal_start.get(literal_key, -1)
if literal_start >= 0:
    literal_size = _native_literal_size.get(literal_key, 0)
    if index < 0 or index >= literal_size:
        return -1
    return _native_byte_data[literal_start + index]'''
        ).body
    else:
        statements = ast.parse(
            '''literal_size = _native_literal_size.get(
    _native_builder_key(runtime, handle),
    -1,
)
if literal_size >= 0:
    return literal_size'''
        ).body
    function.body[0:0] = statements
    return 1


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.statement = 0
        self.global_handle = 0
        self.eval_handle = 0
        self.data_size = 0
        self.data_byte = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        if node.name == "_native_record_statement_kind":
            self.statement += _inject_statement_recording(node)
        elif node.name == "_portapy_get_global_span_impl":
            self.global_handle += _inject_after_handle_tag(node, mode="global")
        elif node.name == "_portapy_eval_span_impl":
            self.eval_handle += _inject_after_handle_tag(node, mode="eval")
        elif node.name == "_native_data_size":
            self.data_size += _inject_literal_data(node, byte=False)
        elif node.name == "_native_data_byte":
            self.data_byte += _inject_literal_data(node, byte=True)
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.FunctionDef)
        and node.name == "_native_store_bytes_literal"
        for node in module.body
    ):
        raise RuntimeError("native bytes-literal helpers are already installed")
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    counts = (
        rewriter.statement,
        rewriter.global_handle,
        rewriter.eval_handle,
        rewriter.data_size,
        rewriter.data_byte,
    )
    if counts != (1, 1, 1, 1, 1):
        raise RuntimeError(f"native bytes-literal normalization missed shapes: {counts}")
    module.body.extend(ast.parse(_HELPERS).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    text = ast.unparse(ast.parse(source))
    required = (
        "_native_record_global_bytes(runtime, name, text[equals + 1:])",
        "_native_attach_global_bytes(runtime, name_text, value)",
        "_native_attach_expression_bytes(runtime, source_text, value)",
        "literal_start = _native_literal_start.get(literal_key, -1)",
        "_native_store_bytes_literal",
        "high * 16 + low",
    )
    absent = [marker for marker in required if marker not in text]
    if absent:
        raise RuntimeError(f"native bytes-literal validation failed: {absent}")
    print("NORMALIZED NATIVE BYTES LITERALS", sum(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
