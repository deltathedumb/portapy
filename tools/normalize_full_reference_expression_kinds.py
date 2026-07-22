"""Install source-kind inference that respects expression structure.

The native ABI keeps a lightweight source-derived kind ledger because raw native
values cannot always distinguish ``None``, ``False``, and integer zero.  The
original classifier checked literal prefixes before comparisons, so
``\"a\" < \"b\"`` was exposed as a string even though the VM correctly returned a
boolean.  It also treated every ``and``/``or`` expression as boolean even though
Python returns one of the operands.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_REPLACEMENT = r'''
def _native_has_top_level_comparison(text: str) -> bool:
    depth = 0
    quote = ""
    escaped = False
    token = ""
    index = 0
    while index <= len(text):
        char = text[index] if index < len(text) else " "
        if quote != "":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "'" or char == '"':
            quote = char
            token = ""
        elif char == "(" or char == "[" or char == "{":
            depth += 1
            token = ""
        elif char == ")" or char == "]" or char == "}":
            depth -= 1
            token = ""
        elif depth == 0:
            if char.isalpha() or char == "_":
                token += char
            else:
                if token == "is" or token == "in" or token == "not":
                    return True
                token = ""
                if char == "<" or char == ">":
                    return True
                if (
                    (char == "=" or char == "!")
                    and index + 1 < len(text)
                    and text[index + 1] == "="
                ):
                    return True
        index += 1
    return False


def _native_top_level_bool_rhs(text: str) -> str:
    depth = 0
    quote = ""
    escaped = False
    token = ""
    result = ""
    index = 0
    while index <= len(text):
        char = text[index] if index < len(text) else " "
        if quote != "":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "'" or char == '"':
            quote = char
            token = ""
        elif char == "(" or char == "[" or char == "{":
            depth += 1
            token = ""
        elif char == ")" or char == "]" or char == "}":
            depth -= 1
            token = ""
        elif depth == 0:
            if char.isalpha() or char == "_":
                token += char
            else:
                if token == "and" or token == "or":
                    result = text[index:]
                token = ""
        index += 1
    return result.strip()


def _native_expression_kind(runtime: int, expression: str) -> int:
    text = expression.strip()
    if text == "None":
        return PORTAPY_VALUE_NONE
    if text == "True" or text == "False":
        return PORTAPY_VALUE_BOOL
    if len(text) == 0:
        return PORTAPY_VALUE_OBJECT
    lower = text.lower()
    if lower.startswith("lambda "):
        return PORTAPY_VALUE_CALLABLE
    if _native_has_top_level_comparison(text):
        return PORTAPY_VALUE_BOOL
    bool_rhs = _native_top_level_bool_rhs(text)
    if len(bool_rhs) > 0:
        return _native_expression_kind(runtime, bool_rhs)
    if (
        lower.startswith("b'")
        or lower.startswith('b"')
        or lower.startswith("br'")
        or lower.startswith('br"')
        or lower.startswith("rb'")
        or lower.startswith('rb"')
    ):
        return PORTAPY_VALUE_BYTES
    if (
        text[0] == "'"
        or text[0] == '"'
        or lower.startswith("r'")
        or lower.startswith('r"')
        or lower.startswith("f'")
        or lower.startswith('f"')
        or lower.startswith("fr'")
        or lower.startswith('fr"')
        or lower.startswith("rf'")
        or lower.startswith('rf"')
    ):
        return PORTAPY_VALUE_STRING
    if text[0] == "[":
        return PORTAPY_VALUE_LIST
    if text[0] == "{":
        return PORTAPY_VALUE_DICT
    if text[0] == "(" and text[len(text) - 1] == ")":
        inner = text[1:len(text) - 1]
        if _native_has_top_level_comma(inner):
            return PORTAPY_VALUE_TUPLE
        return _native_expression_kind(runtime, inner)
    if _native_has_top_level_comma(text):
        return PORTAPY_VALUE_TUPLE
    if _native_is_identifier(text):
        return _native_global_kind(runtime, text)
    if _native_is_number(text):
        if "." in text or "e" in lower:
            return PORTAPY_VALUE_FLOAT
        return PORTAPY_VALUE_INT
    open_at = text.find("(")
    if open_at > 0:
        callee = text[0:open_at].strip()
        if _native_is_identifier(callee):
            callee_kind = _native_global_kind(runtime, callee)
            if callee_kind == PORTAPY_VALUE_CALLABLE:
                return PORTAPY_VALUE_OBJECT
    if _native_expression_has_kind(runtime, text, PORTAPY_VALUE_FLOAT):
        return PORTAPY_VALUE_FLOAT
    if "/" in text and "//" not in text:
        return PORTAPY_VALUE_FLOAT
    if _native_expression_has_kind(runtime, text, PORTAPY_VALUE_STRING):
        if "+" in text:
            return PORTAPY_VALUE_STRING
    return PORTAPY_VALUE_INT
'''


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    matches = [
        index
        for index, node in enumerate(module.body)
        if isinstance(node, ast.FunctionDef)
        and node.name == "_native_expression_kind"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "native expression-kind helper: expected 1, "
            f"found {len(matches)}"
        )
    existing = {
        node.name
        for node in module.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "_native_has_top_level_comparison",
            "_native_top_level_bool_rhs",
        }
    }
    if existing:
        raise RuntimeError(
            "native expression-kind structural helpers already exist: "
            + ", ".join(sorted(existing))
        )

    replacement = ast.parse(_REPLACEMENT).body
    index = matches[0]
    module.body[index:index + 1] = replacement
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    functions = {
        node.name: node
        for node in verified.body
        if isinstance(node, ast.FunctionDef)
    }
    required = {
        "_native_has_top_level_comparison",
        "_native_top_level_bool_rhs",
        "_native_expression_kind",
    }
    missing = sorted(required - functions.keys())
    if missing:
        raise RuntimeError(
            "native expression-kind normalization lost helpers: "
            + ", ".join(missing)
        )
    expression_text = ast.unparse(functions["_native_expression_kind"])
    if expression_text.find("_native_has_top_level_comparison(text)") < 0:
        raise RuntimeError("native comparison kind inference was not installed")
    if expression_text.find("_native_top_level_bool_rhs(text)") < 0:
        raise RuntimeError("native boolean-operand kind inference was not installed")
    print("NORMALIZED NATIVE EXPRESSION VALUE KINDS", len(replacement))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
