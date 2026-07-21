"""Inject host-registered import statements into the native source entry.

This rewrite adds Python-authored interpreter semantics to the ephemeral source
compiled by asmpython. It does not load modules. Native hosts remain responsible
for adding module objects to the environment before executed source imports them.
"""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


def _helpers() -> str:
    return '''_IMPORT_NOT_STATEMENT = -100


def _import_identifier_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def _import_word_at(source: str, start: int, end: int, word: str) -> bool:
    word_end = start + len(word)
    if word_end > end or source[start:word_end] != word:
        return False
    if start > 0 and _import_identifier_char(source[start - 1]):
        return False
    if word_end < end and _import_identifier_char(source[word_end]):
        return False
    return True


def _import_path_end(source: str, start: int, end: int) -> list[int]:
    position = _skip_space(source, end, start)
    first = _parse_identifier_bounds(source, end, position)
    if first[2] != PORTAPY_OK:
        return [position, PORTAPY_COMPILE_ERROR]
    position = first[1]
    while True:
        position = _skip_space(source, end, position)
        if position >= end:
            return [position, PORTAPY_OK]
        if source[position] != ".":
            return [position, PORTAPY_COMPILE_ERROR]
        position = _skip_space(source, end, position + 1)
        part = _parse_identifier_bounds(source, end, position)
        if part[2] != PORTAPY_OK:
            return [position, PORTAPY_COMPILE_ERROR]
        position = part[1]


def _import_alias(source: str, start: int, end: int) -> list[int]:
    start = _skip_space(source, end, start)
    position = start
    while position < end:
        if _import_word_at(source, position, end, "as"):
            left_end = position
            while left_end > start and source[left_end - 1].isspace():
                left_end -= 1
            alias_start = _skip_space(source, end, position + 2)
            alias = _parse_identifier_bounds(source, end, alias_start)
            if alias[2] != PORTAPY_OK or _skip_space(source, end, alias[1]) != end:
                return [start, left_end, 0, 0, PORTAPY_COMPILE_ERROR]
            return [start, left_end, alias[0], alias[1], PORTAPY_OK]
        position += 1
    return [start, end, 0, 0, PORTAPY_OK]


def _resolve_import_module(runtime: int, source: str, start: int, end: int, line: int) -> list[int]:
    path = _import_path_end(source, start, end)
    if path[1] != PORTAPY_OK or path[0] != end:
        _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid import module name", line, 1)
        return [0, PORTAPY_COMPILE_ERROR]
    position = start
    has_dot = False
    while position < end:
        if source[position] == ".":
            has_dot = True
            break
        position += 1
    if has_dot:
        resolved = _host_resolve_host_path(runtime, source, start, end)
    else:
        bounds = _parse_identifier_bounds(source, end, start)
        resolved = _scalar_retain_global(runtime, source[bounds[0]:bounds[1]], bounds[1])
    if resolved[2] != PORTAPY_OK:
        module_name = source[start:end]
        _fail(runtime, PORTAPY_NOT_FOUND, "ModuleNotFoundError", "No module named '" + module_name + "'", line, 1)
        return [0, PORTAPY_NOT_FOUND]
    return [resolved[0], PORTAPY_OK]


def _execute_plain_import_item(runtime: int, source: str, start: int, end: int, line: int) -> int:
    alias = _import_alias(source, start, end)
    if alias[4] != PORTAPY_OK:
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid import alias", line, 1)
    resolved = _resolve_import_module(runtime, source, alias[0], alias[1], line)
    if resolved[1] != PORTAPY_OK:
        return resolved[1]
    if alias[2] != 0:
        name = source[alias[2]:alias[3]]
        return _bind_global(runtime, name, resolved[0])
    root = _parse_identifier_bounds(source, alias[1], alias[0])
    root_name = source[root[0]:root[1]]
    if root[1] < alias[1]:
        _scalar_release(runtime, resolved[0])
        retained = _scalar_retain_global(runtime, root_name, root[1])
        if retained[2] != PORTAPY_OK:
            return _fail(runtime, PORTAPY_NOT_FOUND, "ModuleNotFoundError", "No module named '" + root_name + "'", line, 1)
        return _bind_global(runtime, root_name, retained[0])
    return _bind_global(runtime, root_name, resolved[0])


def _execute_from_import_item(runtime: int, owner: int, source: str, start: int, end: int, line: int) -> int:
    alias = _import_alias(source, start, end)
    if alias[4] != PORTAPY_OK:
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid from-import alias", line, 1)
    if alias[1] - alias[0] == 1 and source[alias[0]] == "*":
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "ImportError", "star import is unavailable; use host add_all()", line, 1)
    member = _parse_identifier_bounds(source, alias[1], alias[0])
    if member[2] != PORTAPY_OK or _skip_space(source, alias[1], member[1]) != alias[1]:
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid imported name", line, 1)
    member_name = source[member[0]:member[1]]
    value = _host_portapy_host_get_attr_span_impl(runtime, owner, member_name, len(member_name))
    if value == 0:
        return _fail(runtime, PORTAPY_NOT_FOUND, "ImportError", "cannot import name '" + member_name + "'", line, 1)
    binding_name = member_name
    if alias[2] != 0:
        binding_name = source[alias[2]:alias[3]]
    return _bind_global(runtime, binding_name, value)


def _execute_import_items(runtime: int, source: str, start: int, end: int, line: int, owner: int) -> int:
    item_start = start
    position = start
    while position <= end:
        split = position == end
        if not split and source[position] == ",":
            split = True
        if split:
            left = item_start
            right = position
            while left < right and source[left].isspace():
                left += 1
            while right > left and source[right - 1].isspace():
                right -= 1
            if left >= right:
                return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "empty import item", line, 1)
            if owner == 0:
                status = _execute_plain_import_item(runtime, source, left, right, line)
            else:
                status = _execute_from_import_item(runtime, owner, source, left, right, line)
            if status != PORTAPY_OK:
                return status
            item_start = position + 1
        position += 1
    return _set_status(PORTAPY_OK)


def _execute_import_statement(runtime: int, statement: str, line: int) -> int:
    bounds = _trim(statement, 0, len(statement))
    start = bounds[0]
    end = bounds[1]
    if _import_word_at(statement, start, end, "import"):
        items_start = _skip_space(statement, end, start + 6)
        if items_start >= end:
            return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "expected module name after import", line, 1)
        return _execute_import_items(runtime, statement, items_start, end, line, 0)
    if not _import_word_at(statement, start, end, "from"):
        return _IMPORT_NOT_STATEMENT
    module_start = _skip_space(statement, end, start + 4)
    position = module_start
    import_at = -1
    while position < end:
        if _import_word_at(statement, position, end, "import"):
            import_at = position
            break
        position += 1
    if import_at < 0:
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "expected import in from statement", line, 1)
    module_end = import_at
    while module_end > module_start and statement[module_end - 1].isspace():
        module_end -= 1
    resolved = _resolve_import_module(runtime, statement, module_start, module_end, line)
    if resolved[1] != PORTAPY_OK:
        return resolved[1]
    items_start = _skip_space(statement, end, import_at + 6)
    if items_start >= end:
        _scalar_release(runtime, resolved[0])
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "expected imported name", line, 1)
    status = _execute_import_items(runtime, statement, items_start, end, line, resolved[0])
    _scalar_release(runtime, resolved[0])
    return status


def _source_has_import_statement(source: str, source_size: int) -> bool:
    position = 0
    while position < source_size:
        end = position
        while end < source_size and source[end] != "\\n":
            end += 1
        bounds = _trim(source, position, end)
        if bounds[0] < bounds[1]:
            if _import_word_at(source, bounds[0], bounds[1], "import") or _import_word_at(source, bounds[0], bounds[1], "from"):
                return True
        position = end + 1
    return False


def _source_has_content(source: str) -> bool:
    position = 0
    while position < len(source):
        if not source[position].isspace():
            return True
        position += 1
    return False


def _exec_source_with_imports(runtime: int, source: str, source_size: int) -> int:
    remaining = ""
    position = 0
    line = 1
    while position < source_size:
        end = position
        while end < source_size and source[end] != "\\n":
            end += 1
        statement = source[position:end]
        status = _execute_import_statement(runtime, statement, line)
        if status == _IMPORT_NOT_STATEMENT:
            remaining += statement
        elif status != PORTAPY_OK:
            return status
        if end < source_size:
            remaining += "\\n"
            line += 1
        position = end + 1
    if not _source_has_content(remaining):
        return _set_status(PORTAPY_OK)
    remaining_size = len(remaining)
    if _source_has_definition_or_compound(remaining, remaining_size):
        return _host_portapy_exec_span_impl(runtime, remaining, remaining_size)
    if _source_has_host_call(remaining, remaining_size):
        return _exec_host_call_source(runtime, remaining, remaining_size)
    return _host_portapy_exec_span_impl(runtime, remaining, remaining_size)'''


def _exec_entry() -> str:
    return '''def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
    if _source_has_import_statement(source, source_size):
        return _exec_source_with_imports(runtime, source, source_size)
    if _source_has_definition_or_compound(source, source_size):
        return _host_portapy_exec_span_impl(runtime, source, source_size)
    if not _source_has_host_call(source, source_size):
        return _host_portapy_exec_span_impl(runtime, source, source_size)
    return _exec_host_call_source(runtime, source, source_size)'''


def rewrite_generated_imports(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    source = _replace_function(source, "_portapy_exec_span_impl", _exec_entry())
    source = source.rstrip() + "\n\n" + _helpers().rstrip() + "\n"
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_imports"]
