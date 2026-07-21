"""Function-local ``if``/``while`` execution for PortaPy's native runtime.

This module is a small semantic overlay on ``native_api_functions``. Hosted
Python installs it directly; native builds splice the shared section below into
the generated namespaced function entry so no module-object mutation crosses
the asmpython boundary.
"""
from __future__ import annotations

from . import native_api_functions as _functions
from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_OK,
    PORTAPY_VALUE_NONE,
)
from .native_api_expressions import _truthy


# BEGIN SHARED FUNCTION CONTROL
_FUNCTION_FLOW_NORMAL = 0
_FUNCTION_FLOW_BREAK = 1
_FUNCTION_FLOW_CONTINUE = 2
_FUNCTION_FLOW_RETURN = 3


def _next_function_content_position(source: str, source_size: int, position: int) -> int:
    while position < source_size:
        info = _functions._line_info(source, source_size, position)
        if info[6] != PORTAPY_OK:
            return position
        if info[4] < info[5]:
            return position
        position = info[2]
    return source_size


def _function_child_indent(
    source: str,
    source_size: int,
    position: int,
    parent_indent: int,
) -> int:
    content_position = _next_function_content_position(source, source_size, position)
    if content_position >= source_size:
        return -1
    info = _functions._line_info(source, source_size, content_position)
    if info[6] != PORTAPY_OK or info[3] <= parent_indent:
        return -1
    return info[3]


def _skip_function_block(
    source: str,
    source_size: int,
    position: int,
    indent: int,
) -> int:
    while position < source_size:
        info = _functions._line_info(source, source_size, position)
        if info[4] >= info[5]:
            position = info[2]
            continue
        if info[3] < indent:
            return position
        position = info[2]
    return source_size


def _function_header_condition(
    source: str,
    start: int,
    end: int,
    keyword_size: int,
) -> list[int]:
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


def _function_source_line(source: str, position: int, base_line: int) -> int:
    return base_line + _functions._line_number(source, position) - 1


def _function_syntax_error(
    runtime: int,
    source: str,
    position: int,
    base_line: int,
    message: str,
) -> int:
    column = 1
    scan = position - 1
    while scan >= 0 and source[scan] != "\n":
        column += 1
        scan -= 1
    return _functions._fail(
        runtime,
        PORTAPY_COMPILE_ERROR,
        "SyntaxError",
        message,
        _function_source_line(source, position, base_line),
        column,
    )


def _evaluate_function_condition(
    runtime: int,
    source: str,
    start: int,
    end: int,
    base_line: int,
) -> list[int]:
    parsed = _functions._parse_call_or_expression(runtime, source, start, end)
    if parsed[2] != PORTAPY_OK:
        status = _functions._record_expression_failure(runtime, parsed[2], parsed[1])
        _functions._runtime_error_line[runtime] = _function_source_line(
            source,
            parsed[1],
            base_line,
        )
        return [0, status]
    truth = _truthy(runtime, parsed[0])
    _functions._release(runtime, parsed[0])
    if truth[1] != PORTAPY_OK:
        _functions._runtime_error_line[runtime] = _function_source_line(
            source,
            start,
            base_line,
        )
        return [0, truth[1]]
    return [truth[0], PORTAPY_OK]


def _execute_function_simple_range(
    runtime: int,
    source: str,
    start: int,
    end: int,
    loop_depth: int,
    base_line: int,
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
                line = _function_source_line(source, left, base_line)
                if statement == "pass":
                    pass
                elif statement == "break":
                    if loop_depth <= 0:
                        status = _function_syntax_error(
                            runtime,
                            source,
                            left,
                            base_line,
                            "break outside a loop",
                        )
                        return [status, _FUNCTION_FLOW_NORMAL, 0]
                    return [PORTAPY_OK, _FUNCTION_FLOW_BREAK, 0]
                elif statement == "continue":
                    if loop_depth <= 0:
                        status = _function_syntax_error(
                            runtime,
                            source,
                            left,
                            base_line,
                            "continue outside a loop",
                        )
                        return [status, _FUNCTION_FLOW_NORMAL, 0]
                    return [PORTAPY_OK, _FUNCTION_FLOW_CONTINUE, 0]
                elif _functions._word_at(statement, 0, len(statement), "return"):
                    expression_start = _functions._skip_space(statement, len(statement), 6)
                    if expression_start >= len(statement):
                        value = _functions._append_value(runtime, PORTAPY_VALUE_NONE, 0)
                        if value == 0:
                            return [
                                _functions._last_status_value(),
                                _FUNCTION_FLOW_NORMAL,
                                0,
                            ]
                        return [PORTAPY_OK, _FUNCTION_FLOW_RETURN, value]
                    parsed = _functions._parse_call_or_expression(
                        runtime,
                        statement,
                        expression_start,
                        len(statement),
                    )
                    if parsed[2] != PORTAPY_OK:
                        status = _functions._record_expression_failure(
                            runtime,
                            parsed[2],
                            parsed[1],
                        )
                        _functions._runtime_error_line[runtime] = line
                        return [status, _FUNCTION_FLOW_NORMAL, 0]
                    return [PORTAPY_OK, _FUNCTION_FLOW_RETURN, parsed[0]]
                else:
                    status = _functions._execute_function_statement(
                        runtime,
                        statement,
                        line,
                    )
                    if status != PORTAPY_OK:
                        return [status, _FUNCTION_FLOW_NORMAL, 0]
            segment_start = position + 1
        position += 1
    return [PORTAPY_OK, _FUNCTION_FLOW_NORMAL, 0]


def _execute_function_block(
    runtime: int,
    source: str,
    source_size: int,
    position: int,
    indent: int,
    loop_depth: int,
    base_line: int,
) -> list[int]:
    while position < source_size:
        info = _functions._line_info(source, source_size, position)
        if info[6] != PORTAPY_OK:
            status = _function_syntax_error(
                runtime,
                source,
                info[4],
                base_line,
                "tabs are not supported for indentation",
            )
            return [position, status, _FUNCTION_FLOW_NORMAL, 0]
        if info[4] >= info[5]:
            position = info[2]
            continue
        if info[3] < indent:
            return [position, PORTAPY_OK, _FUNCTION_FLOW_NORMAL, 0]
        if info[3] > indent:
            status = _function_syntax_error(
                runtime,
                source,
                info[4],
                base_line,
                "unexpected indent",
            )
            return [position, status, _FUNCTION_FLOW_NORMAL, 0]

        start = info[4]
        end = info[5]
        next_position = info[2]

        if _functions._word_at(source, start, end, "if"):
            condition_bounds = _function_header_condition(source, start, end, 2)
            if condition_bounds[0] < 0:
                status = _function_syntax_error(
                    runtime,
                    source,
                    start,
                    base_line,
                    "invalid if statement",
                )
                return [position, status, _FUNCTION_FLOW_NORMAL, 0]
            child_indent = _function_child_indent(
                source,
                source_size,
                next_position,
                indent,
            )
            if child_indent < 0:
                status = _function_syntax_error(
                    runtime,
                    source,
                    end,
                    base_line,
                    "expected an indented block",
                )
                return [position, status, _FUNCTION_FLOW_NORMAL, 0]
            condition = _evaluate_function_condition(
                runtime,
                source,
                condition_bounds[0],
                condition_bounds[1],
                base_line,
            )
            if condition[1] != PORTAPY_OK:
                return [position, condition[1], _FUNCTION_FLOW_NORMAL, 0]
            block_end = _skip_function_block(
                source,
                source_size,
                next_position,
                child_indent,
            )
            flow = _FUNCTION_FLOW_NORMAL
            value = 0
            if condition[0] != 0:
                executed = _execute_function_block(
                    runtime,
                    source,
                    source_size,
                    next_position,
                    child_indent,
                    loop_depth,
                    base_line,
                )
                if executed[1] != PORTAPY_OK:
                    return executed
                flow = executed[2]
                value = executed[3]
                block_end = executed[0]

            else_position = _next_function_content_position(
                source,
                source_size,
                block_end,
            )
            if else_position < source_size:
                else_info = _functions._line_info(
                    source,
                    source_size,
                    else_position,
                )
                if (
                    else_info[3] == indent
                    and source[else_info[4]:else_info[5]] == "else:"
                ):
                    else_indent = _function_child_indent(
                        source,
                        source_size,
                        else_info[2],
                        indent,
                    )
                    if else_indent < 0:
                        status = _function_syntax_error(
                            runtime,
                            source,
                            else_info[5],
                            base_line,
                            "expected an indented block",
                        )
                        return [else_position, status, _FUNCTION_FLOW_NORMAL, 0]
                    else_end = _skip_function_block(
                        source,
                        source_size,
                        else_info[2],
                        else_indent,
                    )
                    if condition[0] == 0:
                        executed = _execute_function_block(
                            runtime,
                            source,
                            source_size,
                            else_info[2],
                            else_indent,
                            loop_depth,
                            base_line,
                        )
                        if executed[1] != PORTAPY_OK:
                            return executed
                        flow = executed[2]
                        value = executed[3]
                        else_end = executed[0]
                    block_end = else_end
            if flow != _FUNCTION_FLOW_NORMAL:
                return [block_end, PORTAPY_OK, flow, value]
            position = block_end
            continue

        if _functions._word_at(source, start, end, "while"):
            condition_bounds = _function_header_condition(source, start, end, 5)
            if condition_bounds[0] < 0:
                status = _function_syntax_error(
                    runtime,
                    source,
                    start,
                    base_line,
                    "invalid while statement",
                )
                return [position, status, _FUNCTION_FLOW_NORMAL, 0]
            child_indent = _function_child_indent(
                source,
                source_size,
                next_position,
                indent,
            )
            if child_indent < 0:
                status = _function_syntax_error(
                    runtime,
                    source,
                    end,
                    base_line,
                    "expected an indented block",
                )
                return [position, status, _FUNCTION_FLOW_NORMAL, 0]
            block_end = _skip_function_block(
                source,
                source_size,
                next_position,
                child_indent,
            )
            while True:
                condition = _evaluate_function_condition(
                    runtime,
                    source,
                    condition_bounds[0],
                    condition_bounds[1],
                    base_line,
                )
                if condition[1] != PORTAPY_OK:
                    return [position, condition[1], _FUNCTION_FLOW_NORMAL, 0]
                if condition[0] == 0:
                    break
                executed = _execute_function_block(
                    runtime,
                    source,
                    source_size,
                    next_position,
                    child_indent,
                    loop_depth + 1,
                    base_line,
                )
                if executed[1] != PORTAPY_OK:
                    return executed
                if executed[2] == _FUNCTION_FLOW_RETURN:
                    return [block_end, PORTAPY_OK, executed[2], executed[3]]
                if executed[2] == _FUNCTION_FLOW_BREAK:
                    break
            position = block_end
            continue

        if source[start:end] == "else:":
            status = _function_syntax_error(
                runtime,
                source,
                start,
                base_line,
                "unexpected else",
            )
            return [position, status, _FUNCTION_FLOW_NORMAL, 0]

        if (
            _functions._word_at(source, start, end, "for")
            or _functions._word_at(source, start, end, "try")
            or _functions._word_at(source, start, end, "with")
            or _functions._word_at(source, start, end, "match")
            or _functions._word_at(source, start, end, "def")
            or _functions._word_at(source, start, end, "class")
        ):
            status = _function_syntax_error(
                runtime,
                source,
                start,
                base_line,
                "this compound statement is not implemented inside native functions",
            )
            return [position, status, _FUNCTION_FLOW_NORMAL, 0]

        simple = _execute_function_simple_range(
            runtime,
            source,
            start,
            end,
            loop_depth,
            base_line,
        )
        if simple[0] != PORTAPY_OK:
            return [position, simple[0], _FUNCTION_FLOW_NORMAL, 0]
        if simple[1] != _FUNCTION_FLOW_NORMAL:
            return [next_position, PORTAPY_OK, simple[1], simple[2]]
        position = next_position

    return [source_size, PORTAPY_OK, _FUNCTION_FLOW_NORMAL, 0]


def _execute_function_body(runtime: int, slot: int) -> list[int]:
    body = _functions._function_body[slot]
    base_line = _functions._function_definition_line[slot] + 1
    executed = _execute_function_block(
        runtime,
        body,
        len(body),
        0,
        0,
        0,
        base_line,
    )
    if executed[1] != PORTAPY_OK:
        return [0, executed[1]]
    if executed[2] == _FUNCTION_FLOW_RETURN:
        return [executed[3], PORTAPY_OK]
    if executed[2] == _FUNCTION_FLOW_BREAK:
        status = _function_syntax_error(
            runtime,
            body,
            executed[0],
            base_line,
            "break outside a loop",
        )
        return [0, status]
    if executed[2] == _FUNCTION_FLOW_CONTINUE:
        status = _function_syntax_error(
            runtime,
            body,
            executed[0],
            base_line,
            "continue outside a loop",
        )
        return [0, status]
    value = _functions._append_value(runtime, PORTAPY_VALUE_NONE, 0)
    if value == 0:
        return [0, _functions._last_status_value()]
    return [value, PORTAPY_OK]
# END SHARED FUNCTION CONTROL


def install() -> None:
    """Install compound function-body execution into the hosted runtime."""
    _functions._execute_function_body = _execute_function_body


install()


__all__ = ["install"]
