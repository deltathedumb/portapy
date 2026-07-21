"""Synchronous host-callable dispatch over PortaPy's opaque host bridge.

The native parser owns call recognition, argument evaluation, pending-call
lifetime, and result ownership. A tiny ABI shim invokes the host callback that
was registered for the runtime; the host receives borrowed argument handles and
returns one owned PortaPy value handle.
"""
from __future__ import annotations

from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_INTERRUPTED,
    PORTAPY_INVALID_ARGUMENT,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_NOT_FOUND,
    PORTAPY_OK,
    PORTAPY_RUNTIME_ERROR,
    PORTAPY_TYPE_ERROR,
    PORTAPY_VALUE_CALLABLE,
    _append_value,
    _bind_global,
    _clear_runtime_error,
    _fail,
    _parse_identifier_bounds,
    _runtime_error_line,
    _runtime_is_valid,
    _set_status,
    _skip_space,
    _value_is_valid,
    _value_kind,
    _value_refs,
    portapy_abi_version,
    _portapy_error_clear_impl,
    _portapy_error_column_impl,
    _portapy_error_line_impl,
    _portapy_error_message_byte_impl,
    _portapy_error_message_size_impl,
    _portapy_error_status_impl,
    _portapy_error_type_byte_impl,
    _portapy_error_type_size_impl,
    _portapy_get_global_span_impl,
    _portapy_last_status_impl,
    _portapy_runtime_create_impl,
    _portapy_runtime_destroy_impl,
    _portapy_value_as_bool_impl,
    _portapy_value_as_f64_bits_impl,
    _portapy_value_as_i64_impl,
    _portapy_value_from_bool_impl,
    _portapy_value_from_data_begin_impl,
    _portapy_value_from_f64_bits_impl,
    _portapy_value_from_i64_impl,
    _portapy_value_from_none_impl,
    _portapy_value_get_byte_impl,
    _portapy_value_get_kind_impl,
    _portapy_value_get_size_impl,
    _portapy_value_release_impl,
    _portapy_value_retain_impl,
    _portapy_value_set_data_byte_impl,
    _portapy_value_validate_utf8_impl,
)
from .native_api_host import (
    _dotted_path_bounds as _host_dotted_path_bounds,
    _parse_host_or_function_expression as _host_parse_expression,
    _portapy_host_get_attr_span_impl as _host_get_attr_span,
    _portapy_host_set_attr_span_impl as _host_set_attr_span,
    _portapy_set_global_span_impl as _host_set_global_span,
    _portapy_value_from_host_object_impl as _host_value_from_object,
    _portapy_value_get_host_id_impl as _host_value_get_id,
    _portapy_eval_span_impl as _host_eval_span,
    _portapy_exec_span_impl as _host_exec_span,
    _resolve_host_path as _host_resolve_path,
)
from .native_api_scalar import _find_assignment, _release, _retain_global


_host_callable_runtime: list[int] = [0]
_host_callable_value: list[int] = [0]
_host_callable_id: list[int] = [0]
_pending_runtime: list[int] = [0]
_pending_callable_id: list[int] = [0]
_pending_argument_start: list[int] = [0]
_pending_argument_count: list[int] = [0]
_pending_arguments: list[int] = [0]
_HOST_NOT_CALL = -1


def _trim(source: str, start: int, end: int) -> list[int]:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    return [start, end]


def _valid_direct_name(source: str, start: int, end: int) -> bool:
    bounds = _parse_identifier_bounds(source, end, start)
    return bounds[2] == PORTAPY_OK and _skip_space(source, end, bounds[1]) == end


def _host_call_bounds(source: str, start: int, end: int) -> list[int]:
    bounds = _trim(source, start, end)
    start = bounds[0]
    end = bounds[1]
    quote = ""
    escaped = False
    depth = 0
    open_at = -1
    close_at = -1
    position = start
    while position < end:
        char = source[position]
        if quote != "":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            position += 1
            continue
        if char == "'" or char == '"':
            quote = char
            position += 1
            continue
        if char == "(":
            if depth == 0 and open_at < 0:
                open_at = position
            depth += 1
        elif char == ")":
            if depth <= 0:
                return [0, 0, 0, 0, position, PORTAPY_COMPILE_ERROR]
            depth -= 1
            if depth == 0:
                close_at = position
        position += 1
    if quote != "" or depth != 0:
        return [0, 0, 0, 0, end, PORTAPY_COMPILE_ERROR]
    if open_at < 0 or close_at < 0:
        return [0, 0, 0, 0, start, _HOST_NOT_CALL]
    if _skip_space(source, end, close_at + 1) != end:
        return [0, 0, 0, 0, close_at + 1, _HOST_NOT_CALL]
    callee = _trim(source, start, open_at)
    if callee[0] >= callee[1]:
        return [0, 0, 0, 0, open_at, PORTAPY_COMPILE_ERROR]
    dotted = _host_dotted_path_bounds(source, callee[0], callee[1])
    if dotted[2] != PORTAPY_OK and not _valid_direct_name(source, callee[0], callee[1]):
        return [0, 0, 0, 0, callee[0], _HOST_NOT_CALL]
    return [callee[0], callee[1], open_at + 1, close_at, end, PORTAPY_OK]


def _argument_spans(source: str, start: int, end: int) -> list[int]:
    result: list[int] = [PORTAPY_OK, end]
    bounds = _trim(source, start, end)
    start = bounds[0]
    end = bounds[1]
    if start >= end:
        return result
    quote = ""
    escaped = False
    depth = 0
    position = start
    item_start = start
    while position <= end:
        at_end = position == end
        char = "" if at_end else source[position]
        split = at_end
        if not at_end:
            if quote != "":
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
            elif char == "'" or char == '"':
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                if depth <= 0:
                    return [PORTAPY_COMPILE_ERROR, position]
                depth -= 1
            elif char == "," and depth == 0:
                split = True
        if split:
            item = _trim(source, item_start, position)
            if item[0] >= item[1]:
                return [PORTAPY_COMPILE_ERROR, position]
            result.append(item[0])
            result.append(item[1])
            item_start = position + 1
        position += 1
    if quote != "" or depth != 0:
        return [PORTAPY_COMPILE_ERROR, end]
    return result


def _find_host_callable(runtime: int, value: int) -> int:
    if not _value_is_valid(runtime, value) or _value_kind[value] != PORTAPY_VALUE_CALLABLE:
        return 0
    index = 1
    while index < len(_host_callable_runtime):
        if _host_callable_runtime[index] == runtime and _host_callable_value[index] == value:
            return index
        index += 1
    return 0


def _host_callable_identifier(runtime: int, value: int) -> list[int]:
    slot = _find_host_callable(runtime, value)
    if slot == 0:
        return [0, PORTAPY_TYPE_ERROR]
    return [_host_callable_id[slot], PORTAPY_OK]


def _portapy_value_from_host_callable_impl(runtime: int, callable_id: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    value = _append_value(runtime, PORTAPY_VALUE_CALLABLE, callable_id)
    if value == 0:
        return 0
    _host_callable_runtime.append(runtime)
    _host_callable_value.append(value)
    _host_callable_id.append(callable_id)
    return value


def _portapy_value_get_host_callable_id_impl(runtime: int, value: int) -> int:
    resolved = _host_callable_identifier(runtime, value)
    if resolved[1] != PORTAPY_OK:
        _set_status(resolved[1])
        return 0
    _set_status(PORTAPY_OK)
    return resolved[0]


def _resolve_call_target(runtime: int, source: str, start: int, end: int) -> list[int]:
    dotted = _host_dotted_path_bounds(source, start, end)
    if dotted[2] == PORTAPY_OK:
        return _host_resolve_path(runtime, source, start, end)
    if not _valid_direct_name(source, start, end):
        return [0, start, PORTAPY_COMPILE_ERROR]
    bounds = _parse_identifier_bounds(source, end, start)
    return _retain_global(runtime, source[bounds[0]:bounds[1]], bounds[1])


def _begin_pending_call(runtime: int, callable_id: int, handles: list[int]) -> int:
    start = len(_pending_arguments)
    index = 0
    while index < len(handles):
        _pending_arguments.append(handles[index])
        index += 1
    _pending_runtime.append(runtime)
    _pending_callable_id.append(callable_id)
    _pending_argument_start.append(start)
    _pending_argument_count.append(len(handles))
    return len(_pending_runtime) - 1


def _find_pending_frame(runtime: int) -> int:
    index = len(_pending_runtime) - 1
    while index > 0:
        if _pending_runtime[index] == runtime:
            return index
        index -= 1
    return 0


def _clear_pending_frame(runtime: int, frame: int) -> None:
    if frame <= 0 or frame >= len(_pending_runtime):
        return
    start = _pending_argument_start[frame]
    count = _pending_argument_count[frame]
    index = 0
    while index < count:
        value = _pending_arguments[start + index]
        if _value_is_valid(runtime, value):
            _release(runtime, value)
        index += 1
    _pending_runtime[frame] = 0
    _pending_callable_id[frame] = 0
    _pending_argument_start[frame] = 0
    _pending_argument_count[frame] = 0


def _portapy_host_pending_arg_count_impl(runtime: int) -> int:
    frame = _find_pending_frame(runtime)
    if frame == 0:
        _set_status(PORTAPY_NOT_FOUND)
        return 0
    _set_status(PORTAPY_OK)
    return _pending_argument_count[frame]


def _portapy_host_pending_arg_impl(runtime: int, index: int) -> int:
    frame = _find_pending_frame(runtime)
    if frame == 0:
        _set_status(PORTAPY_NOT_FOUND)
        return 0
    if index < 0 or index >= _pending_argument_count[frame]:
        _set_status(PORTAPY_INVALID_ARGUMENT)
        return 0
    value = _pending_arguments[_pending_argument_start[frame] + index]
    if not _value_is_valid(runtime, value):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _set_status(PORTAPY_OK)
    return value


def _portapy_host_dispatch_complete_impl(runtime: int, status: int, result: int) -> int:
    frame = _find_pending_frame(runtime)
    if frame == 0:
        _set_status(PORTAPY_NOT_FOUND)
        return 0
    if status != PORTAPY_OK:
        _clear_pending_frame(runtime, frame)
        _fail(runtime, status, "HostCallError", "native host callable returned a failure status")
        return 0
    if not _value_is_valid(runtime, result):
        _clear_pending_frame(runtime, frame)
        _fail(runtime, PORTAPY_INVALID_HANDLE, "HostCallError", "native host callable returned an invalid value handle")
        return 0
    _clear_pending_frame(runtime, frame)
    _set_status(PORTAPY_OK)
    return result


def _portapy_host_dispatch_impl(runtime: int, callable_id: int) -> int:
    """Build-time patched callback boundary."""
    _fail(runtime, PORTAPY_INTERRUPTED, "HostDispatchUnavailable", "native host-call dispatch boundary was not installed")
    return 0


def _dispatch_host_call(runtime: int, callable_id: int, handles: list[int], position: int) -> list[int]:
    _begin_pending_call(runtime, callable_id, handles)
    result = _portapy_host_dispatch_impl(runtime, callable_id)
    if result == 0:
        status = _portapy_last_status_impl()
        frame = _find_pending_frame(runtime)
        if frame != 0:
            _clear_pending_frame(runtime, frame)
        if status == PORTAPY_OK:
            status = PORTAPY_RUNTIME_ERROR
        return [0, position, status]
    return [result, position, PORTAPY_OK]


def _parse_host_call_or_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    call = _host_call_bounds(source, start, end)
    if call[5] == _HOST_NOT_CALL:
        return _host_parse_expression(runtime, source, start, end)
    if call[5] != PORTAPY_OK:
        return [0, call[4], call[5]]
    target = _resolve_call_target(runtime, source, call[0], call[1])
    if target[2] != PORTAPY_OK:
        return _host_parse_expression(runtime, source, start, end)
    callable_id = _host_callable_identifier(runtime, target[0])
    if callable_id[1] != PORTAPY_OK:
        _release(runtime, target[0])
        dotted = _host_dotted_path_bounds(source, call[0], call[1])
        if dotted[2] == PORTAPY_OK:
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "host attribute is not callable")
            return [0, call[0], PORTAPY_TYPE_ERROR]
        return _host_parse_expression(runtime, source, start, end)
    _release(runtime, target[0])
    spans = _argument_spans(source, call[2], call[3])
    if spans[0] != PORTAPY_OK:
        return [0, spans[1], spans[0]]
    handles: list[int] = []
    index = 2
    while index < len(spans):
        parsed = _parse_host_call_or_expression(runtime, source, spans[index], spans[index + 1])
        if parsed[2] != PORTAPY_OK:
            release = 0
            while release < len(handles):
                _release(runtime, handles[release])
                release += 1
            return parsed
        handles.append(parsed[0])
        index += 2
    dispatched = _dispatch_host_call(runtime, callable_id[0], handles, call[4])
    dispatched[1] = call[4]
    return dispatched


def _source_has_definition_or_compound(source: str, source_size: int) -> bool:
    position = 0
    while position < source_size:
        end = position
        while end < source_size and source[end] != "\n":
            end += 1
        line = source[position:end]
        bounds = _trim(line, 0, len(line))
        if bounds[0] > 0 and bounds[0] < bounds[1]:
            return True
        if bounds[0] < bounds[1]:
            text = line[bounds[0]:bounds[1]]
            if text.startswith("def ") or text.startswith("if ") or text.startswith("while "):
                return True
            if text == "else:" or text.startswith("elif "):
                return True
        position = end + 1
    return False


def _source_has_host_call(source: str, source_size: int) -> bool:
    position = 0
    while position < source_size:
        end = position
        while end < source_size and source[end] != "\n" and source[end] != ";":
            end += 1
        statement = source[position:end]
        assignment = _find_assignment(statement, len(statement))
        expression_start = int(assignment[2]) if assignment[0] != "" else 0
        call = _host_call_bounds(statement, expression_start, len(statement))
        if call[5] == PORTAPY_OK:
            return True
        position = end + 1
    return False


def _execute_call_statement(runtime: int, statement: str, line: int) -> int:
    bounds = _trim(statement, 0, len(statement))
    statement = statement[bounds[0]:bounds[1]]
    if statement == "" or statement == "pass":
        return _set_status(PORTAPY_OK)
    assignment = _find_assignment(statement, len(statement))
    expression_start = int(assignment[2]) if assignment[0] != "" else 0
    parsed = _parse_host_call_or_expression(runtime, statement, expression_start, len(statement))
    if parsed[2] != PORTAPY_OK:
        _runtime_error_line[runtime] = line
        return _set_status(parsed[2])
    if assignment[0] == "":
        _release(runtime, parsed[0])
        return _set_status(PORTAPY_OK)
    if assignment[0] != "=":
        _release(runtime, parsed[0])
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "augmented assignment from a host call is not available", line, 1)
    left = statement[0:int(assignment[1])]
    bounds = _parse_identifier_bounds(left, len(left), 0)
    if bounds[2] != PORTAPY_OK or _skip_space(left, len(left), bounds[1]) != len(left):
        _release(runtime, parsed[0])
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid assignment target", line, 1)
    return _bind_global(runtime, left[bounds[0]:bounds[1]], parsed[0])


def _exec_host_call_source(runtime: int, source: str, source_size: int) -> int:
    position = 0
    line = 1
    while position < source_size:
        end = position
        while end < source_size and source[end] != "\n" and source[end] != ";":
            end += 1
        status = _execute_call_statement(runtime, source[position:end], line)
        if status != PORTAPY_OK:
            return status
        if end < source_size and source[end] == "\n":
            line += 1
        position = end + 1
    return _set_status(PORTAPY_OK)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        return 0
    call = _host_call_bounds(source, 0, source_size)
    if call[5] != PORTAPY_OK:
        return _host_eval_span(runtime, source, source_size)
    parsed = _parse_host_call_or_expression(runtime, source, 0, source_size)
    if parsed[2] != PORTAPY_OK:
        _set_status(parsed[2])
        return 0
    return parsed[0]


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
    if _source_has_definition_or_compound(source, source_size):
        return _host_exec_span(runtime, source, source_size)
    if not _source_has_host_call(source, source_size):
        return _host_exec_span(runtime, source, source_size)
    return _exec_host_call_source(runtime, source, source_size)


# Public host-object internal forwarders required by the C bridge.
def _portapy_value_from_host_object_impl(runtime: int, host_id: int) -> int:
    return _host_value_from_object(runtime, host_id)


def _portapy_value_get_host_id_impl(runtime: int, value: int) -> int:
    return _host_value_get_id(runtime, value)


def _portapy_set_global_span_impl(runtime: int, name: str, name_size: int, value: int) -> int:
    return _host_set_global_span(runtime, name, name_size, value)


def _portapy_host_set_attr_span_impl(runtime: int, owner: int, name: str, name_size: int, value: int) -> int:
    return _host_set_attr_span(runtime, owner, name, name_size, value)


def _portapy_host_get_attr_span_impl(runtime: int, owner: int, name: str, name_size: int) -> int:
    return _host_get_attr_span(runtime, owner, name, name_size)
