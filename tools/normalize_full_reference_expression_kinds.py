"""Install source-kind inference that respects expression structure.

The native ABI keeps a lightweight source-derived kind ledger because raw native
values cannot always distinguish ``None``, ``False``, and integer zero.  This
pass fixes comparison and boolean-expression precedence and records return kinds
for source-defined callables, allowing ``seven()`` and similar function results
to cross the ABI as integers instead of the previous hardcoded ``OBJECT`` kind.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_REPLACEMENT = r'''
_native_callable_return_kinds: dict[str, int] = {}


def _native_callable_key(runtime: int, name: str) -> str:
    return str(runtime) + ":" + name


def _native_set_callable_return_kind(runtime: int, name: str, kind: int) -> None:
    _native_callable_return_kinds[_native_callable_key(runtime, name)] = kind


def _native_callable_return_kind(runtime: int, name: str) -> int:
    return _native_callable_return_kinds.get(
        _native_callable_key(runtime, name),
        PORTAPY_VALUE_OBJECT,
    )


def _native_merge_callable_return_kind(runtime: int, name: str, kind: int) -> None:
    key = _native_callable_key(runtime, name)
    existing = _native_callable_return_kinds.get(key, -1)
    if existing < 0 or existing == PORTAPY_VALUE_NONE:
        _native_callable_return_kinds[key] = kind
    elif kind != PORTAPY_VALUE_NONE and existing != kind:
        _native_callable_return_kinds[key] = PORTAPY_VALUE_OBJECT


def _native_definition_name(text: str, prefix: str) -> str:
    start = len(prefix)
    end = text.find("(", start)
    if end < 0:
        end = text.find(":", start)
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def _native_record_callable_return_kinds(runtime: int, source: str) -> None:
    function_names: list[str] = []
    function_indents: list[int] = []
    depth = 0
    line = ""
    index = 0
    while index <= len(source):
        char = source[index] if index < len(source) else "\n"
        if char != "\n":
            line += char
        else:
            indentation = 0
            while indentation < len(line):
                indent_char = line[indentation]
                if indent_char != " " and indent_char != "\t":
                    break
                indentation += 1
            text = line.strip()
            if len(text) > 0:
                while depth > 0 and indentation <= function_indents[depth - 1]:
                    depth -= 1
                function_name = ""
                if text.startswith("def "):
                    function_name = _native_definition_name(text, "def ")
                elif text.startswith("async def "):
                    function_name = _native_definition_name(text, "async def ")
                if _native_is_identifier(function_name):
                    _native_set_global_kind(runtime, function_name, PORTAPY_VALUE_CALLABLE)
                    _native_set_callable_return_kind(
                        runtime,
                        function_name,
                        PORTAPY_VALUE_NONE,
                    )
                    if depth < len(function_names):
                        function_names[depth] = function_name
                        function_indents[depth] = indentation
                    else:
                        function_names.append(function_name)
                        function_indents.append(indentation)
                    depth += 1
                elif text.startswith("class ") and indentation == 0:
                    class_name = _native_definition_name(text, "class ")
                    if _native_is_identifier(class_name):
                        _native_set_global_kind(runtime, class_name, PORTAPY_VALUE_CALLABLE)
                        _native_set_callable_return_kind(
                            runtime,
                            class_name,
                            PORTAPY_VALUE_OBJECT,
                        )
                elif depth > 0 and (text == "return" or text.startswith("return ")):
                    expression = text[6:].strip()
                    if len(expression) == 0:
                        return_kind = PORTAPY_VALUE_NONE
                    else:
                        return_kind = _native_expression_kind(runtime, expression)
                    _native_merge_callable_return_kind(
                        runtime,
                        function_names[depth - 1],
                        return_kind,
                    )
            line = ""
        index += 1


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
                return _native_callable_return_kind(runtime, callee)
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
            "_native_callable_key",
            "_native_callable_return_kind",
            "_native_record_callable_return_kinds",
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

    source_scanner = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_native_record_source_kinds"
        ),
        None,
    )
    if source_scanner is None:
        raise RuntimeError("native source-kind scanner is missing")
    scanner_call = ast.Expr(
        value=ast.Call(
            func=ast.Name(id="_native_record_callable_return_kinds", ctx=ast.Load()),
            args=[
                ast.Name(id="runtime", ctx=ast.Load()),
                ast.Name(id="source", ctx=ast.Load()),
            ],
            keywords=[],
        )
    )
    source_scanner.body.insert(0, scanner_call)

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
        "_native_callable_key",
        "_native_set_callable_return_kind",
        "_native_callable_return_kind",
        "_native_merge_callable_return_kind",
        "_native_definition_name",
        "_native_record_callable_return_kinds",
        "_native_has_top_level_comparison",
        "_native_top_level_bool_rhs",
        "_native_expression_kind",
        "_native_record_source_kinds",
    }
    missing = sorted(required - functions.keys())
    if missing:
        raise RuntimeError(
            "native expression-kind normalization lost helpers: "
            + ", ".join(missing)
        )
    expression_text = ast.unparse(functions["_native_expression_kind"])
    if "_native_has_top_level_comparison(text)" not in expression_text:
        raise RuntimeError("native comparison kind inference was not installed")
    if "_native_top_level_bool_rhs(text)" not in expression_text:
        raise RuntimeError("native boolean-operand kind inference was not installed")
    if "_native_callable_return_kind(runtime, callee)" not in expression_text:
        raise RuntimeError("native callable return-kind inference was not installed")
    scanner_text = ast.unparse(functions["_native_record_source_kinds"])
    if scanner_text.count("_native_record_callable_return_kinds(runtime, source)") != 1:
        raise RuntimeError("native callable return scanner was not installed")
    print("NORMALIZED NATIVE EXPRESSION VALUE KINDS", len(replacement))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
