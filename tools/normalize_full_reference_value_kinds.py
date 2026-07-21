"""Install native-safe kind bookkeeping for source-created values.

The compiled VM intentionally keeps raw values for execution speed. At the public
opaque-handle boundary, however, values need an explicit ``ValueKind`` because raw
zero can mean ``None``, ``False``, or integer zero and native pointers cannot be
safely inspected as arbitrary Python objects. This pass records kinds from source
syntax and from already-tagged host handles, then applies them when globals or eval
results cross the ABI boundary.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_KIND_HELPERS = r'''
_native_global_kinds: dict[str, int] = {}


def _native_kind_key(runtime: int, name: str) -> str:
    return str(runtime) + ":" + name


def _native_global_kind(runtime: int, name: str) -> int:
    return _native_global_kinds.get(
        _native_kind_key(runtime, name),
        PORTAPY_VALUE_INT,
    )


def _native_set_global_kind(runtime: int, name: str, kind: int) -> None:
    _native_global_kinds[_native_kind_key(runtime, name)] = kind


def _native_kind_member(kind: int) -> object:
    if kind == PORTAPY_VALUE_NONE:
        return ValueKind.NONE
    if kind == PORTAPY_VALUE_BOOL:
        return ValueKind.BOOL
    if kind == PORTAPY_VALUE_INT:
        return ValueKind.INT
    if kind == PORTAPY_VALUE_FLOAT:
        return ValueKind.FLOAT
    if kind == PORTAPY_VALUE_STRING:
        return ValueKind.STRING
    if kind == PORTAPY_VALUE_BYTES:
        return ValueKind.BYTES
    if kind == PORTAPY_VALUE_CALLABLE:
        return ValueKind.CALLABLE
    if kind == PORTAPY_VALUE_TUPLE:
        return ValueKind.TUPLE
    if kind == PORTAPY_VALUE_DICT:
        return ValueKind.DICT
    if kind == PORTAPY_VALUE_LIST:
        return ValueKind.LIST
    return ValueKind.OBJECT


def _native_set_handle_kind(instance: Runtime, handle: int, kind: int) -> bool:
    slot = instance._values.get(str(handle))
    if slot is None:
        return False
    slot.kind = _native_kind_member(kind)
    return True


def _native_is_identifier(text: str) -> bool:
    if len(text) == 0:
        return False
    first = text[0]
    if not first.isalpha() and first != "_":
        return False
    index = 1
    while index < len(text):
        char = text[index]
        if not char.isalnum() and char != "_":
            return False
        index += 1
    return True


def _native_is_number(text: str) -> bool:
    if len(text) == 0:
        return False
    found_digit = False
    index = 0
    while index < len(text):
        char = text[index]
        if char.isdigit():
            found_digit = True
        elif char != "+" and char != "-" and char != "." and char != "_" and char != "e" and char != "E":
            return False
        index += 1
    return found_digit


def _native_has_top_level_comma(text: str) -> bool:
    depth = 0
    quote = ""
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if quote != "":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "'" or char == '"':
            quote = char
        elif char == "(" or char == "[" or char == "{":
            depth += 1
        elif char == ")" or char == "]" or char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            return True
        index += 1
    return False


def _native_expression_has_kind(runtime: int, text: str, kind: int) -> bool:
    token = ""
    index = 0
    while index <= len(text):
        char = text[index] if index < len(text) else " "
        if char.isalnum() or char == "_":
            token += char
        else:
            if _native_is_identifier(token):
                if _native_global_kind(runtime, token) == kind:
                    return True
            token = ""
        index += 1
    return False


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
    if (
        "==" in text
        or "!=" in text
        or "<=" in text
        or ">=" in text
        or " is " in text
        or " in " in text
        or " and " in text
        or " or " in text
        or lower.startswith("not ")
    ):
        return PORTAPY_VALUE_BOOL
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


def _native_assignment_at(statement: str) -> int:
    depth = 0
    quote = ""
    escaped = False
    index = 0
    while index < len(statement):
        char = statement[index]
        if quote != "":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "'" or char == '"':
            quote = char
        elif char == "(" or char == "[" or char == "{":
            depth += 1
        elif char == ")" or char == "]" or char == "}":
            depth -= 1
        elif char == "=" and depth == 0:
            before = statement[index - 1] if index > 0 else ""
            after = statement[index + 1] if index + 1 < len(statement) else ""
            if before != "=" and before != "!" and before != "<" and before != ">" and after != "=":
                return index
        index += 1
    return -1


def _native_record_statement_kind(runtime: int, statement: str) -> None:
    text = statement.strip()
    if len(text) == 0:
        return
    if text.startswith("def ") or text.startswith("async def "):
        start = 4 if text.startswith("def ") else 10
        end = text.find("(", start)
        if end > start:
            name = text[start:end].strip()
            if _native_is_identifier(name):
                _native_set_global_kind(runtime, name, PORTAPY_VALUE_CALLABLE)
        return
    if text.startswith("class "):
        start = 6
        end = text.find("(", start)
        colon = text.find(":", start)
        if end < 0 or (colon >= 0 and colon < end):
            end = colon
        if end < 0:
            end = len(text)
        name = text[start:end].strip()
        if _native_is_identifier(name):
            _native_set_global_kind(runtime, name, PORTAPY_VALUE_CALLABLE)
        return
    equals = _native_assignment_at(text)
    if equals < 0:
        return
    name = text[0:equals].strip()
    if not _native_is_identifier(name):
        return
    kind = _native_expression_kind(runtime, text[equals + 1:])
    _native_set_global_kind(runtime, name, kind)


def _native_record_source_kinds(runtime: int, source: str) -> None:
    statement = ""
    quote = ""
    escaped = False
    comment = False
    depth = 0
    indentation = 0
    line_start = True
    index = 0
    while index <= len(source):
        char = source[index] if index < len(source) else "\n"
        if comment:
            if char == "\n":
                comment = False
            else:
                index += 1
                continue
        if quote != "":
            statement += char
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "'" or char == '"':
            quote = char
            statement += char
            line_start = False
        elif char == "#":
            comment = True
        elif char == "(" or char == "[" or char == "{":
            depth += 1
            statement += char
            line_start = False
        elif char == ")" or char == "]" or char == "}":
            depth -= 1
            statement += char
        elif (char == ";" or char == "\n") and depth == 0:
            if indentation == 0:
                _native_record_statement_kind(runtime, statement)
            statement = ""
            indentation = 0
            line_start = True
        else:
            if line_start and (char == " " or char == "\t"):
                indentation += 1
            else:
                line_start = False
            statement += char
        index += 1
'''

_EXEC_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    return _set_status(Status.INVALID_HANDLE)
if source_size < 0:
    return _set_status(Status.INVALID_ARGUMENT)
source_text = source[0:source_size]
status = instance.exec_utf8(source_text)
_native_record_source_kinds(runtime, source_text)
if status is Status.RUNTIME_ERROR:
    line, column = _native_error_location(source_text)
    instance._capture_native(
        status,
        "RuntimeError",
        "PortaPy source execution failed",
        line,
        column,
    )
elif status is Status.COMPILE_ERROR:
    line, column = _native_error_location(source_text)
    instance._capture_native(
        status,
        "SyntaxError",
        "PortaPy source compilation failed",
        line,
        column,
    )
return _set_status(status)
'''

_EVAL_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
if source_size < 0:
    _set_status(Status.INVALID_ARGUMENT)
    return 0
source_text = source[0:source_size]
status, value = instance.eval_utf8(source_text)
if status is Status.OK:
    _native_set_handle_kind(
        instance,
        value,
        _native_expression_kind(runtime, source_text),
    )
if status is Status.RUNTIME_ERROR:
    line, column = _native_error_location(source_text)
    instance._capture_native(
        status,
        "RuntimeError",
        "PortaPy source evaluation failed",
        line,
        column,
    )
elif status is Status.COMPILE_ERROR:
    line, column = _native_error_location(source_text)
    instance._capture_native(
        status,
        "SyntaxError",
        "PortaPy source compilation failed",
        line,
        column,
    )
_set_status(status)
return value
'''

_GET_GLOBAL_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
if name_size <= 0 or name_size > len(name):
    _set_status(Status.INVALID_ARGUMENT)
    return 0
name_text = name[0:name_size]
status, value = instance.get_global(name_text)
if status is Status.OK:
    _native_set_handle_kind(
        instance,
        value,
        _native_global_kind(runtime, name_text),
    )
_set_status(status)
return value
'''

_SET_GLOBAL_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    return _set_status(Status.INVALID_HANDLE)
if name_size <= 0 or name_size > len(name):
    return _set_status(Status.INVALID_ARGUMENT)
status, unboxed = instance.unbox(value)
if status is not Status.OK:
    return _set_status(status)
kind_status, kind = instance.value_kind(value)
if kind_status is not Status.OK:
    return _set_status(kind_status)
name_text = name[0:name_size]
status = instance.set_global(name_text, unboxed)
if status is Status.OK:
    _native_set_global_kind(runtime, name_text, _native_value_kind_code(kind))
return _set_status(status)
'''

_REPLACEMENTS = {
    "_portapy_exec_span_impl": _EXEC_SOURCE,
    "_portapy_eval_span_impl": _EVAL_SOURCE,
    "_portapy_get_global_span_impl": _GET_GLOBAL_SOURCE,
    "_portapy_set_global_span_impl": _SET_GLOBAL_SOURCE,
}


class _Rewrite(ast.NodeTransformer):
    def __init__(self) -> None:
        self.replaced: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        replacement = _REPLACEMENTS.get(node.name)
        if replacement is None:
            return self.generic_visit(node)
        node.body = ast.parse(replacement).body
        self.replaced.add(node.name)
        return node


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"))
    if any(
        isinstance(node, ast.FunctionDef) and node.name == "_native_expression_kind"
        for node in module.body
    ):
        raise RuntimeError("native value-kind helpers are already installed")
    rewriter = _Rewrite()
    module = rewriter.visit(module)
    missing = sorted(set(_REPLACEMENTS) - rewriter.replaced)
    if missing:
        raise RuntimeError(f"native value-kind functions missing: {missing}")
    module.body.extend(ast.parse(_KIND_HELPERS).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    text = ast.unparse(verified)
    required = (
        "_native_record_source_kinds(runtime, source_text)",
        "_native_expression_kind(runtime, source_text)",
        "_native_global_kind(runtime, name_text)",
        "_native_value_kind_code(kind)",
        "slot.kind = _native_kind_member(kind)",
    )
    absent = [marker for marker in required if marker not in text]
    if absent:
        raise RuntimeError(f"native value-kind validation failed: {absent}")
    print("NORMALIZED NATIVE SOURCE VALUE KINDS", len(_REPLACEMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
