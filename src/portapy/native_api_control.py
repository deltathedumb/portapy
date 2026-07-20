"""Indented control-flow entry for PortaPy's native runtime.

The parser and execution rules are Python source compiled by asmpython. Native
C and generated assembly remain ABI and calling-convention boundaries only.
"""
from __future__ import annotations

from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_INVALID_ARGUMENT,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_OK,
    _bind_global,
    _clear_runtime_error,
    _fail,
    _parse_identifier_bounds,
    _runtime_error_column,
    _runtime_error_line,
    _runtime_is_valid,
    _set_status,
    _skip_space,
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
from .native_api_expressions import (
    _parse_boolean_expression,
    _record_expression_failure,
    _truthy,
    _word_at,
)


_FLOW_NORMAL = 0
_FLOW_BREAK = 1
_FLOW_CONTINUE = 2


def _line_number(source: str, position: int) -> int:
    line = 1
    index = 0
    while index < position:
        if source[index] == "\n":
            line += 1
        index += 1
    return line


def _syntax_error(runtime: int, source: str, position: int, message: str) -> int:
    line = _line_number(source, position)
    column = 1
    scan = position - 1
    while scan >= 0 and source[scan] != "\n":
        column += 1
        scan -= 1
    return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", message, line, column)


def _line_info(source: str, source_size: int, position: int) -> list[int]:
    line_start = position
    line_end = position
    while line_end < source_size and source[line_end] != "\n":
        line_end += 1
    next_position = line_end
    if next_position < source_size:
        next_position += 1

    indent = 0
    content_start = line_start
    while content_start < line_end:
        char = source[content_start]
        if char == " ":
            indent += 1
            content_start += 1
            continue
        if char == "\t":
            return [line_start, line_end, next_position, indent, content_start, content_start, PORTAPY_COMPILE_ERROR]
        break

    quote = ""
    escaped = False
    depth = 0
    content_end = line_end
    scan = content_start
    while scan < line_end:
        char = source[scan]
        if quote:
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
            if depth > 0:
                depth -= 1
        elif char == "#" and depth == 0:
            content_end = scan
            break
        scan += 1
    while content_end > content_start and source[content_end - 1].isspace():
        content_end -= 1
    return [line_start, line_end, next_position, indent, content_start, content_end, PORTAPY_OK]


def _next_content_position(source: str, source_size: int, position: int) -> int:
    while position < source_size:
        info = _line_info(source, source_size, position)
        if info[6] != PORTAPY_OK:
            return position
        if info[4] < info[5]:
            return position
        position = info[2]
    return source_size


def _child_indent(source: str, source_size: int, position: int, parent_indent: int) -> int:
    content_position = _next_content_position(source, source_size, position)
    if content_position >= source_size:
        return -1
    info = _line_info(source, source_size, content_position)
    if info[6] != PORTAPY_OK or info[3] <= parent_indent:
        return -1
    return info[3]


def _skip_block(source: str, source_size: int, position: int, indent: int) -> int:
    while position < source_size:
        info = _line_info(source, source_size, position)
        if info[4] >= info[5]:
            position = info[2]
            continue
        if info[3] < indent:
            return position
        position = info[2]
    return source_size


def _find_assignment(source: str, start: int, end: int) -> int:
    quote = ""
    escaped = False
    depth = 0
    position = start
    while position < end:
        char = source[position]
        if quote:
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
            depth += 1
            position += 1
            continue
        if char == ")":
            if depth > 0:
                depth -= 1
            position += 1
            continue
        if char == "=" and depth == 0:
            previous = source[position - 1] if position > start else ""
            following = source[position + 1] if position + 1 < end else ""
            if previous != "=" and previous != "!" and previous != "<" and previous != ">" and following != "=":
                return position
        position += 1
    return -1


def _execute_assignment(runtime: int, source: str, start: int, end: int) -> int:
    assignment = _find_assignment(source, start, end)
    if assignment < 0:
        parsed = _parse_boolean_expression(runtime, source, start, end)
        if parsed[2] != PORTAPY_OK:
            return _record_expression_failure(runtime, parsed[2], parsed[1])
        _value_refs[parsed[0]] -= 1
        return _set_status(PORTAPY_OK)

    bounds = _parse_identifier_bounds(source, assignment, start)
    if bounds[2] != PORTAPY_OK:
        return _record_expression_failure(runtime, bounds[2], bounds[1])
    name_end = _skip_space(source, assignment, bounds[1])
    if name_end != assignment:
        return _syntax_error(runtime, source, name_end, "invalid assignment target")
    name = source[bounds[0]:bounds[1]]
    parsed = _parse_boolean_expression(runtime, source, assignment + 1, end)
    if parsed[2] != PORTAPY_OK:
        return _record_expression_failure(runtime, parsed[2], parsed[1])
    return _bind_global(runtime, name, parsed[0])


def _execute_simple_range(
    runtime: int,
    source: str,
    start: int,
    end: int,
    loop_depth: int,
) -> list[int]:
    segment_start = start
    quote = ""
    escaped = False
    depth = 0
    position = start
    while position <= end:
        at_end = position == end
        char = "" if at_end else source[position]
        split = at_end
        if not at_end:
            if quote:
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
                if depth > 0:
                    depth -= 1
            elif char == ";" and depth == 0:
                split = True
        if split:
            left = segment_start
            right = position
            while left < right and source[left].isspace():
                left += 1
            while right > left and source[right - 1].isspace():
                right -= 1
            if left < right:
                statement = source[left:right]
                if statement == "pass":
                    pass
                elif statement == "break":
                    if loop_depth <= 0:
                        return [PORTAPY_COMPILE_ERROR, _FLOW_NORMAL]
                    return [PORTAPY_OK, _FLOW_BREAK]
                elif statement == "continue":
                    if loop_depth <= 0:
                        return [PORTAPY_COMPILE_ERROR, _FLOW_NORMAL]
                    return [PORTAPY_OK, _FLOW_CONTINUE]
                else:
                    status = _execute_assignment(runtime, source, left, right)
                    if status != PORTAPY_OK:
                        return [status, _FLOW_NORMAL]
            segment_start = position + 1
        position += 1
    return [PORTAPY_OK, _FLOW_NORMAL]


def _header_condition(source: str, start: int, end: int, keyword_size: int) -> list[int]:
    if end <= start or source[end - 1] != ":":
        return [-1, -1]
    condition_start = start + keyword_size
    while condition_start < end - 1 and source[condition_start].isspace():
        condition_start += 1
    condition_end = end - 1
    while condition_end > condition_start and source[condition_end - 1].isspace():
        condition_end -= 1
    if condition_start >= condition_end:
        return [-1, -1]
    return [condition_start, condition_end]


def _evaluate_condition(runtime: int, source: str, start: int, end: int) -> list[int]:
    parsed = _parse_boolean_expression(runtime, source, start, end)
    if parsed[2] != PORTAPY_OK:
        return [0, _record_expression_failure(runtime, parsed[2], parsed[1])]
    truth = _truthy(runtime, parsed[0])
    _value_refs[parsed[0]] -= 1
    if truth[1] != PORTAPY_OK:
        return [0, truth[1]]
    return [truth[0], PORTAPY_OK]


def _execute_block(
    runtime: int,
    source: str,
    source_size: int,
    position: int,
    indent: int,
    loop_depth: int,
) -> list[int]:
    while position < source_size:
        info = _line_info(source, source_size, position)
        if info[6] != PORTAPY_OK:
            return [position, _syntax_error(runtime, source, info[4], "tabs are not supported for indentation"), _FLOW_NORMAL]
        if info[4] >= info[5]:
            position = info[2]
            continue
        if info[3] < indent:
            return [position, PORTAPY_OK, _FLOW_NORMAL]
        if info[3] > indent:
            return [position, _syntax_error(runtime, source, info[4], "unexpected indent"), _FLOW_NORMAL]

        start = info[4]
        end = info[5]
        next_position = info[2]

        if _word_at(source, start, end, "if"):
            condition_bounds = _header_condition(source, start, end, 2)
            if condition_bounds[0] < 0:
                return [position, _syntax_error(runtime, source, start, "invalid if statement"), _FLOW_NORMAL]
            child_indent = _child_indent(source, source_size, next_position, indent)
            if child_indent < 0:
                return [position, _syntax_error(runtime, source, end, "expected an indented block"), _FLOW_NORMAL]
            condition = _evaluate_condition(runtime, source, condition_bounds[0], condition_bounds[1])
            if condition[1] != PORTAPY_OK:
                _runtime_error_line[runtime] = _line_number(source, start)
                return [position, condition[1], _FLOW_NORMAL]
            block_end = _skip_block(source, source_size, next_position, child_indent)
            flow = _FLOW_NORMAL
            if condition[0] != 0:
                executed = _execute_block(runtime, source, source_size, next_position, child_indent, loop_depth)
                if executed[1] != PORTAPY_OK:
                    return executed
                flow = executed[2]
                block_end = executed[0]

            else_position = _next_content_position(source, source_size, block_end)
            if else_position < source_size:
                else_info = _line_info(source, source_size, else_position)
                if else_info[3] == indent and source[else_info[4]:else_info[5]] == "else:":
                    else_indent = _child_indent(source, source_size, else_info[2], indent)
                    if else_indent < 0:
                        return [else_position, _syntax_error(runtime, source, else_info[5], "expected an indented block"), _FLOW_NORMAL]
                    else_end = _skip_block(source, source_size, else_info[2], else_indent)
                    if condition[0] == 0:
                        executed = _execute_block(runtime, source, source_size, else_info[2], else_indent, loop_depth)
                        if executed[1] != PORTAPY_OK:
                            return executed
                        flow = executed[2]
                        else_end = executed[0]
                    block_end = else_end
            if flow != _FLOW_NORMAL:
                return [block_end, PORTAPY_OK, flow]
            position = block_end
            continue

        if _word_at(source, start, end, "while"):
            condition_bounds = _header_condition(source, start, end, 5)
            if condition_bounds[0] < 0:
                return [position, _syntax_error(runtime, source, start, "invalid while statement"), _FLOW_NORMAL]
            child_indent = _child_indent(source, source_size, next_position, indent)
            if child_indent < 0:
                return [position, _syntax_error(runtime, source, end, "expected an indented block"), _FLOW_NORMAL]
            block_end = _skip_block(source, source_size, next_position, child_indent)
            while True:
                condition = _evaluate_condition(runtime, source, condition_bounds[0], condition_bounds[1])
                if condition[1] != PORTAPY_OK:
                    _runtime_error_line[runtime] = _line_number(source, start)
                    return [position, condition[1], _FLOW_NORMAL]
                if condition[0] == 0:
                    break
                executed = _execute_block(runtime, source, source_size, next_position, child_indent, loop_depth + 1)
                if executed[1] != PORTAPY_OK:
                    return executed
                if executed[2] == _FLOW_BREAK:
                    break
            position = block_end
            continue

        if source[start:end] == "else:":
            return [position, _syntax_error(runtime, source, start, "unexpected else"), _FLOW_NORMAL]

        simple = _execute_simple_range(runtime, source, start, end, loop_depth)
        if simple[0] != PORTAPY_OK:
            if simple[0] == PORTAPY_COMPILE_ERROR:
                return [position, _syntax_error(runtime, source, start, "loop control outside a loop"), _FLOW_NORMAL]
            _runtime_error_line[runtime] = _line_number(source, start)
            return [position, simple[0], _FLOW_NORMAL]
        if simple[1] != _FLOW_NORMAL:
            return [next_position, PORTAPY_OK, simple[1]]
        position = next_position

    return [source_size, PORTAPY_OK, _FLOW_NORMAL]


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        return 0
    parsed = _parse_boolean_expression(runtime, source, 0, source_size)
    if parsed[2] != PORTAPY_OK:
        _record_expression_failure(runtime, parsed[2], parsed[1])
        return 0
    return parsed[0]


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
    executed = _execute_block(runtime, source, source_size, 0, 0, 0)
    if executed[1] != PORTAPY_OK:
        return executed[1]
    if executed[2] != _FLOW_NORMAL:
        return _syntax_error(runtime, source, executed[0], "loop control outside a loop")
    return _set_status(PORTAPY_OK)
