"""Add native traceback-frame capture to generated function execution."""
from __future__ import annotations

from pathlib import Path


_STATE_MARKER = "_MAX_CALL_DEPTH = 128\n"
_EXECUTION_BLOCK = '''    _call_depth[runtime] += 1
    executed = _execute_function_body(runtime, slot)
    _call_depth[runtime] -= 1
    _restore_bindings(runtime, saved_names, saved_existed, saved_values)
    _call_bound_top[0] = bound_start
    if executed[1] != PORTAPY_OK:
        return [0, position, executed[1]]'''
_EXECUTION_WITH_TRACEBACK = '''    _call_depth[runtime] += 1
    executed = _execute_function_body(runtime, slot)
    _call_depth[runtime] -= 1
    _restore_bindings(runtime, saved_names, saved_existed, saved_values)
    _call_bound_top[0] = bound_start
    if executed[1] != PORTAPY_OK:
        _portapy_traceback_add_function_impl(runtime, slot)
        return [0, position, executed[1]]'''


def _state_and_api() -> str:
    return '''_traceback_runtime: list[int] = [0]
_traceback_line: list[int] = [0]
_traceback_column: list[int] = [0]
_traceback_function: list[str] = [""]
_traceback_source: list[str] = [""]


def _portapy_traceback_reset_impl(runtime: int) -> int:
    index = 1
    while index < len(_traceback_runtime):
        if _traceback_runtime[index] == runtime:
            _traceback_runtime[index] = 0
            _traceback_line[index] = 0
            _traceback_column[index] = 0
            _traceback_function[index] = ""
            _traceback_source[index] = ""
        index += 1
    return _set_status(PORTAPY_OK)


def _portapy_traceback_add_impl(
    runtime: int,
    line: int,
    column: int,
    function_name: str,
    source_line: str,
) -> int:
    _traceback_runtime.append(runtime)
    _traceback_line.append(line)
    _traceback_column.append(column)
    _traceback_function.append(function_name)
    _traceback_source.append(source_line)
    return _set_status(PORTAPY_OK)


def _traceback_body_line(slot: int, absolute_line: int) -> str:
    wanted = absolute_line - _function_definition_line[slot] - 1
    if wanted < 0:
        return ""
    body = _function_body[slot]
    current = 0
    start = 0
    position = 0
    while position <= len(body):
        if position == len(body) or body[position] == "\\n":
            if current == wanted:
                bounds = _trim(body, start, position)
                return body[bounds[0]:bounds[1]]
            current += 1
            start = position + 1
        position += 1
    return ""


def _portapy_traceback_add_function_impl(runtime: int, slot: int) -> int:
    line = _runtime_error_line[runtime]
    column = _runtime_error_column[runtime]
    source_line = _traceback_body_line(slot, line)
    if source_line == "":
        line = _function_definition_line[slot]
        column = 1
        source_line = "def " + _function_name[slot] + "(" + _function_parameters[slot] + "):"
    return _portapy_traceback_add_impl(
        runtime,
        line,
        column,
        _function_name[slot],
        source_line,
    )


def _portapy_traceback_count_impl(runtime: int) -> int:
    count = 0
    index = 1
    while index < len(_traceback_runtime):
        if _traceback_runtime[index] == runtime:
            count += 1
        index += 1
    _set_status(PORTAPY_OK)
    return count


def _traceback_slot(runtime: int, wanted: int) -> int:
    count = _portapy_traceback_count_impl(runtime)
    if wanted < 0 or wanted >= count:
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    current = 0
    index = len(_traceback_runtime) - 1
    while index > 0:
        if _traceback_runtime[index] == runtime:
            if current == wanted:
                _set_status(PORTAPY_OK)
                return index
            current += 1
        index -= 1
    _set_status(PORTAPY_NOT_FOUND)
    return 0


def _portapy_traceback_line_impl(runtime: int, wanted: int) -> int:
    slot = _traceback_slot(runtime, wanted)
    if slot == 0:
        return 0
    return _traceback_line[slot]


def _portapy_traceback_column_impl(runtime: int, wanted: int) -> int:
    slot = _traceback_slot(runtime, wanted)
    if slot == 0:
        return 0
    return _traceback_column[slot]


def _portapy_traceback_function_size_impl(runtime: int, wanted: int) -> int:
    slot = _traceback_slot(runtime, wanted)
    if slot == 0:
        return 0
    return len(_traceback_function[slot].encode("utf-8"))


def _portapy_traceback_function_byte_impl(runtime: int, wanted: int, byte_index: int) -> int:
    slot = _traceback_slot(runtime, wanted)
    if slot == 0:
        return 0
    data = _traceback_function[slot].encode("utf-8")
    if byte_index < 0 or byte_index >= len(data):
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    _set_status(PORTAPY_OK)
    return data[byte_index]


def _portapy_traceback_source_size_impl(runtime: int, wanted: int) -> int:
    slot = _traceback_slot(runtime, wanted)
    if slot == 0:
        return 0
    return len(_traceback_source[slot].encode("utf-8"))


def _portapy_traceback_source_byte_impl(runtime: int, wanted: int, byte_index: int) -> int:
    slot = _traceback_slot(runtime, wanted)
    if slot == 0:
        return 0
    data = _traceback_source[slot].encode("utf-8")
    if byte_index < 0 or byte_index >= len(data):
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    _set_status(PORTAPY_OK)
    return data[byte_index]'''


def rewrite_generated_traceback(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    if _STATE_MARKER not in source:
        raise ValueError("generated function source is missing call-depth state")
    source = source.replace(
        _STATE_MARKER,
        _STATE_MARKER + _state_and_api().rstrip() + "\n",
        1,
    )
    if _EXECUTION_BLOCK not in source:
        raise ValueError("generated function invocation has an unexpected unwind block")
    source = source.replace(_EXECUTION_BLOCK, _EXECUTION_WITH_TRACEBACK, 1)
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_traceback"]
