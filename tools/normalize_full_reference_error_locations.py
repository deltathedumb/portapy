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

    locator = ast.unparse(
        next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_native_error_location"
        )
    )
    required = (
        'lines = source.split("\\n")',
        "previous_opens_block",
        "return line_index + 1, indent + 1",
        "return line_index + 1, column_index + 1",
    )
    absent = [marker for marker in required if marker not in locator]
    if absent:
        raise RuntimeError(f"native error location validation failed: {absent}")
    print("NORMALIZED NATIVE ERROR LOCATIONS", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
