"""Install compiler-safe native source error location heuristics."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_LOCATION_BODY = r'''
lines = source.split("\n")
line_index = 0
allowed_indent = 0
previous_opens_block = False
while line_index < len(lines):
    text = lines[line_index]
    indent = 0
    while indent < len(text) and (
        text[indent] == " " or text[indent] == "\t"
    ):
        indent += 1
    stripped = text[indent:].strip()
    if stripped != "" and not stripped.startswith("#"):
        if indent > allowed_indent:
            if previous_opens_block:
                allowed_indent = indent
            else:
                return line_index + 1, indent + 1
        elif indent < allowed_indent:
            allowed_indent = indent
        column_index = indent
        quote = ""
        escaped = False
        while column_index < len(text):
            char = text[column_index]
            if quote != "":
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char == "'" or char == '"':
                quote = char
            elif char == "#":
                break
            elif char == "%" or char == "/":
                operator_size = 1
                if (
                    char == "/"
                    and column_index + 1 < len(text)
                    and text[column_index + 1] == "/"
                ):
                    operator_size = 2
                lookahead = column_index + operator_size
                while lookahead < len(text) and (
                    text[lookahead] == " " or text[lookahead] == "\t"
                ):
                    lookahead += 1
                if lookahead < len(text) and text[lookahead] == "0":
                    return line_index + 1, column_index + 1
            column_index += 1
        previous_opens_block = stripped.endswith(":")
    line_index += 1
return 1, 1
'''


def _is_name_plus_one(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Add)
        and isinstance(node.left, ast.Name)
        and node.left.id == name
        and isinstance(node.right, ast.Constant)
        and node.right.value == 1
    )


def _has_return_pair(function: ast.FunctionDef, second_name: str) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Tuple):
            continue
        if len(node.value.elts) != 2:
            continue
        if _is_name_plus_one(node.value.elts[0], "line_index") and _is_name_plus_one(
            node.value.elts[1], second_name
        ):
            return True
    return False


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_native_error_location"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"native error locator expected one function, found {len(matches)}"
        )
    matches[0].body = ast.parse(_LOCATION_BODY).body
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    locator = next(
        node
        for node in verified.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_native_error_location"
    )
    has_newline_split = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "split"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "source"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "\n"
        for node in ast.walk(locator)
    )
    names = {
        node.id
        for node in ast.walk(locator)
        if isinstance(node, ast.Name)
    }
    ready = (
        has_newline_split
        and "previous_opens_block" in names
        and _has_return_pair(locator, "indent")
        and _has_return_pair(locator, "column_index")
    )
    if not ready:
        raise RuntimeError("native error location semantic validation failed")
    print("NORMALIZED NATIVE ERROR LOCATIONS", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
