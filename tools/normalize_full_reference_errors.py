"""Install native-safe structured error reporting in the full ABI entry."""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")

_LOCATION_HELPER = '''
def _native_error_location(source: str) -> tuple[int, int]:
    line = 1
    column = 1
    index = 0
    size = len(source)
    while index < size:
        char = source[index]
        if char == "\\n":
            line += 1
            column = 1
            index += 1
            continue
        operator_size = 0
        if char == "%":
            operator_size = 1
        elif char == "/":
            operator_size = 1
            if index + 1 < size and source[index + 1] == "/":
                operator_size = 2
        if operator_size:
            lookahead = index + operator_size
            while lookahead < size and (
                source[lookahead] == " " or source[lookahead] == "\\t"
            ):
                lookahead += 1
            if lookahead < size and source[lookahead] == "0":
                return line, column
        index += 1
        column += 1
    return 1, 1
'''

_EXEC_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    return _set_status(Status.INVALID_HANDLE)
if source_size < 0:
    return _set_status(Status.INVALID_ARGUMENT)
source_text = source[0:source_size]
status = instance.exec_utf8(source_text)
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

_VALIDATE_UTF8_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    return _set_status(Status.INVALID_HANDLE)
status, raw = instance.unbox(value)
if status is not Status.OK:
    return _set_status(status)
try:
    raw.decode("utf-8")
except UnicodeDecodeError:
    status = instance._capture_native(
        Status.TYPE_ERROR,
        "UnicodeDecodeError",
        "invalid UTF-8",
        0,
        1,
    )
    return _set_status(status)
return _set_status(Status.OK)
'''

_ERROR_LINE_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
if instance.last_error() is None:
    _set_status(Status.NOT_FOUND)
    return 0
_set_status(Status.OK)
return instance._error_line
'''

_ERROR_COLUMN_SOURCE = '''
instance = _runtime(runtime)
if instance is None:
    _set_status(Status.INVALID_HANDLE)
    return 0
if instance.last_error() is None:
    _set_status(Status.NOT_FOUND)
    return 0
_set_status(Status.OK)
return instance._error_column
'''

_REPLACEMENTS = {
    "_portapy_exec_span_impl": _EXEC_SOURCE,
    "_portapy_eval_span_impl": _EVAL_SOURCE,
    "_portapy_value_validate_utf8_impl": _VALIDATE_UTF8_SOURCE,
    "_portapy_error_line_impl": _ERROR_LINE_SOURCE,
    "_portapy_error_column_impl": _ERROR_COLUMN_SOURCE,
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
        isinstance(node, ast.FunctionDef) and node.name == "_native_error_location"
        for node in module.body
    ):
        raise RuntimeError("native error helpers are already installed")

    rewriter = _Rewrite()
    module = rewriter.visit(module)
    missing = sorted(set(_REPLACEMENTS) - rewriter.replaced)
    if missing:
        raise RuntimeError(f"native structured error functions missing: {missing}")
    module.body.extend(ast.parse(_LOCATION_HELPER).body)
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source)
    text = ast.unparse(verified)
    required = (
        "UnicodeDecodeError",
        "instance._error_line",
        "instance._error_column",
        "_native_error_location(source_text)",
        "instance._capture_native(",
    )
    absent = [marker for marker in required if marker not in text]
    if absent:
        raise RuntimeError(f"native structured error validation failed: {absent}")
    print("NORMALIZED NATIVE STRUCTURED ERRORS", len(_REPLACEMENTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
