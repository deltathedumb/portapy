"""Stack-safe native function rewrite entry with recursive control flow."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_function_safe import rewrite_generated_function as _rewrite
from tools.rewrite_generated_parser import _replace_function


_FUNCTION_FLOW_CONSTANTS = '''_FUNCTION_FLOW_NORMAL = 0
_FUNCTION_FLOW_BREAK = 1
_FUNCTION_FLOW_CONTINUE = 2
_FUNCTION_FLOW_RETURN = 3
'''


def _parse_call_or_expression() -> str:
    return '''def _push_call_argument(value: int) -> None:
    top = _call_argument_top[0]
    if top < len(_call_argument_values):
        _call_argument_values[top] = value
    else:
        _call_argument_values.append(value)
    _call_argument_top[0] = top + 1


def _parse_call_or_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    call = _direct_call_bounds(source, start, end)
    if call[3] == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    function_slot = _find_function_slot(runtime, call[0])
    if function_slot == 0:
        return _expr_parse_boolean_expression(runtime, source, start, end)
    arguments = _argument_spans(source, int(call[1]), int(call[2]))
    if arguments[0] != PORTAPY_OK:
        return [0, arguments[1], arguments[0]]
    argument_start = _call_argument_top[0]
    index = 2
    while index < len(arguments):
        parsed = _parse_call_or_expression(runtime, source, arguments[index], arguments[index + 1])
        if parsed[2] != PORTAPY_OK:
            release = argument_start
            while release < _call_argument_top[0]:
                _scalar_release(runtime, _call_argument_values[release])
                release += 1
            _call_argument_top[0] = argument_start
            return parsed
        _push_call_argument(parsed[0])
        index += 2
    argument_count = _call_argument_top[0] - argument_start
    result = _invoke_function(runtime, function_slot, argument_start, argument_count, start)
    _call_argument_top[0] = argument_start
    return result'''


def _execute_function_body() -> str:
    return '''def _function_next_content_position(source: str, source_size: int, position: int) -> int:
    while position < source_size:
        info = _ctrl_line_info(source, source_size, position)
        if info[6] != PORTAPY_OK:
            return position
        if info[4] < info[5]:
            return position
        position = info[2]
    return source_size


def _function_child_indent(source: str, source_size: int, position: int, parent_indent: int) -> int:
    content_position = _function_next_content_position(source, source_size, position)
    if content_position >= source_size:
        return -1
    info = _ctrl_line_info(source, source_size, content_position)
    if info[6] != PORTAPY_OK or info[3] <= parent_indent:
        return -1
    return info[3]


def _function_skip_block(source: str, source_size: int, position: int, indent: int) -> int:
    while position < source_size:
        info = _ctrl_line_info(source, source_size, position)
        if info[4] >= info[5]:
            position = info[2]
            continue
        if info[3] < indent:
            return position
        position = info[2]
    return source_size


def _function_header_condition(source: str, start: int, end: int, keyword_size: int) -> list[int]:
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


def _function_actual_line(slot: int, source: str, position: int) -> int:
    return _function_definition_line[slot] + _line_number(source, position)


def _function_syntax_error(runtime: int, slot: int, source: str, position: int, message: str) -> int:
    return _fail(
        runtime,
        PORTAPY_COMPILE_ERROR,
        "SyntaxError",
        message,
        _function_actual_line(slot, source, position),
        1,
    )


def _function_evaluate_condition(
    runtime: int,
    slot: int,
    source: str,
    start: int,
    end: int,
) -> list[int]:
    parsed = _parse_call_or_expression(runtime, source, start, end)
    if parsed[2] != PORTAPY_OK:
        _runtime_error_line[runtime] = _function_actual_line(slot, source, start)
        return [0, _expr_record_expression_failure(runtime, parsed[2], parsed[1])]
    truth = _expr_truthy(runtime, parsed[0])
    _scalar_release(runtime, parsed[0])
    if truth[1] != PORTAPY_OK:
        return [0, truth[1]]
    return [truth[0], PORTAPY_OK]


def _execute_function_simple_range(
    runtime: int,
    slot: int,
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
            bounds = _trim(source, segment_start, position)
            left = bounds[0]
            right = bounds[1]
            if left < right:
                statement = source[left:right]
                actual_line = _function_actual_line(slot, source, left)
                if statement == "pass":
                    pass
                elif statement == "break":
                    if loop_depth <= 0:
                        return [
                            _function_syntax_error(
                                runtime,
                                slot,
                                source,
                                left,
                                "loop control outside a loop",
                            ),
                            _FUNCTION_FLOW_NORMAL,
                            0,
                        ]
                    return [PORTAPY_OK, _FUNCTION_FLOW_BREAK, 0]
                elif statement == "continue":
                    if loop_depth <= 0:
                        return [
                            _function_syntax_error(
                                runtime,
                                slot,
                                source,
                                left,
                                "loop control outside a loop",
                            ),
                            _FUNCTION_FLOW_NORMAL,
                            0,
                        ]
                    return [PORTAPY_OK, _FUNCTION_FLOW_CONTINUE, 0]
                elif _word_at(statement, 0, len(statement), "return"):
                    expression_start = _skip_space(statement, len(statement), 6)
                    if expression_start >= len(statement):
                        value = _append_value(runtime, PORTAPY_VALUE_NONE, 0)
                        return [PORTAPY_OK, _FUNCTION_FLOW_RETURN, value]
                    parsed = _parse_call_or_expression(
                        runtime,
                        statement,
                        expression_start,
                        len(statement),
                    )
                    if parsed[2] != PORTAPY_OK:
                        _runtime_error_line[runtime] = actual_line
                        return [
                            _expr_record_expression_failure(runtime, parsed[2], parsed[1]),
                            _FUNCTION_FLOW_NORMAL,
                            0,
                        ]
                    return [PORTAPY_OK, _FUNCTION_FLOW_RETURN, parsed[0]]
                elif (
                    _word_at(statement, 0, len(statement), "for")
                    or _word_at(statement, 0, len(statement), "try")
                    or _word_at(statement, 0, len(statement), "with")
                    or _word_at(statement, 0, len(statement), "match")
                    or _word_at(statement, 0, len(statement), "def")
                    or _word_at(statement, 0, len(statement), "class")
                ):
                    return [
                        _function_syntax_error(
                            runtime,
                            slot,
                            source,
                            left,
                            "unsupported compound statement inside native function",
                        ),
                        _FUNCTION_FLOW_NORMAL,
                        0,
                    ]
                else:
                    status = _execute_function_statement(runtime, statement, actual_line)
                    if status != PORTAPY_OK:
                        return [status, _FUNCTION_FLOW_NORMAL, 0]
            segment_start = position + 1
        position += 1
    return [PORTAPY_OK, _FUNCTION_FLOW_NORMAL, 0]


def _execute_function_block(
    runtime: int,
    slot: int,
    source: str,
    source_size: int,
    position: int,
    indent: int,
    loop_depth: int,
) -> list[int]:
    while position < source_size:
        info = _ctrl_line_info(source, source_size, position)
        if info[6] != PORTAPY_OK:
            return [
                position,
                _function_syntax_error(
                    runtime,
                    slot,
                    source,
                    info[4],
                    "tabs are not supported for indentation",
                ),
                _FUNCTION_FLOW_NORMAL,
                0,
            ]
        if info[4] >= info[5]:
            position = info[2]
            continue
        if info[3] < indent:
            return [position, PORTAPY_OK, _FUNCTION_FLOW_NORMAL, 0]
        if info[3] > indent:
            return [
                position,
                _function_syntax_error(
                    runtime,
                    slot,
                    source,
                    info[4],
                    "unexpected indent",
                ),
                _FUNCTION_FLOW_NORMAL,
                0,
            ]

        start = info[4]
        end = info[5]
        next_position = info[2]

        if _word_at(source, start, end, "if"):
            condition_bounds = _function_header_condition(source, start, end, 2)
            if condition_bounds[0] < 0:
                return [
                    position,
                    _function_syntax_error(runtime, slot, source, start, "invalid if statement"),
                    _FUNCTION_FLOW_NORMAL,
                    0,
                ]
            child_indent = _function_child_indent(source, source_size, next_position, indent)
            if child_indent < 0:
                return [
                    position,
                    _function_syntax_error(runtime, slot, source, end, "expected an indented block"),
                    _FUNCTION_FLOW_NORMAL,
                    0,
                ]
            condition = _function_evaluate_condition(
                runtime,
                slot,
                source,
                condition_bounds[0],
                condition_bounds[1],
            )
            if condition[1] != PORTAPY_OK:
                return [position, condition[1], _FUNCTION_FLOW_NORMAL, 0]
            block_end = _function_skip_block(source, source_size, next_position, child_indent)
            flow = _FUNCTION_FLOW_NORMAL
            value = 0
            if condition[0] != 0:
                executed = _execute_function_block(
                    runtime,
                    slot,
                    source,
                    source_size,
                    next_position,
                    child_indent,
                    loop_depth,
                )
                if executed[1] != PORTAPY_OK:
                    return executed
                flow = executed[2]
                value = executed[3]
                block_end = executed[0]

            else_position = _function_next_content_position(source, source_size, block_end)
            if else_position < source_size:
                else_info = _ctrl_line_info(source, source_size, else_position)
                if else_info[3] == indent and source[else_info[4]:else_info[5]] == "else:":
                    else_indent = _function_child_indent(source, source_size, else_info[2], indent)
                    if else_indent < 0:
                        return [
                            else_position,
                            _function_syntax_error(
                                runtime,
                                slot,
                                source,
                                else_info[5],
                                "expected an indented block",
                            ),
                            _FUNCTION_FLOW_NORMAL,
                            0,
                        ]
                    else_end = _function_skip_block(source, source_size, else_info[2], else_indent)
                    if condition[0] == 0:
                        executed = _execute_function_block(
                            runtime,
                            slot,
                            source,
                            source_size,
                            else_info[2],
                            else_indent,
                            loop_depth,
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

        if _word_at(source, start, end, "while"):
            condition_bounds = _function_header_condition(source, start, end, 5)
            if condition_bounds[0] < 0:
                return [
                    position,
                    _function_syntax_error(runtime, slot, source, start, "invalid while statement"),
                    _FUNCTION_FLOW_NORMAL,
                    0,
                ]
            child_indent = _function_child_indent(source, source_size, next_position, indent)
            if child_indent < 0:
                return [
                    position,
                    _function_syntax_error(runtime, slot, source, end, "expected an indented block"),
                    _FUNCTION_FLOW_NORMAL,
                    0,
                ]
            block_end = _function_skip_block(source, source_size, next_position, child_indent)
            while True:
                condition = _function_evaluate_condition(
                    runtime,
                    slot,
                    source,
                    condition_bounds[0],
                    condition_bounds[1],
                )
                if condition[1] != PORTAPY_OK:
                    return [position, condition[1], _FUNCTION_FLOW_NORMAL, 0]
                if condition[0] == 0:
                    break
                executed = _execute_function_block(
                    runtime,
                    slot,
                    source,
                    source_size,
                    next_position,
                    child_indent,
                    loop_depth + 1,
                )
                if executed[1] != PORTAPY_OK:
                    return executed
                if executed[2] == _FUNCTION_FLOW_RETURN:
                    return [block_end, PORTAPY_OK, _FUNCTION_FLOW_RETURN, executed[3]]
                if executed[2] == _FUNCTION_FLOW_BREAK:
                    break
            position = block_end
            continue

        if source[start:end] == "else:":
            return [
                position,
                _function_syntax_error(runtime, slot, source, start, "unexpected else"),
                _FUNCTION_FLOW_NORMAL,
                0,
            ]

        simple = _execute_function_simple_range(
            runtime,
            slot,
            source,
            start,
            end,
            loop_depth,
        )
        if simple[0] != PORTAPY_OK:
            return [position, simple[0], _FUNCTION_FLOW_NORMAL, 0]
        if simple[1] != _FUNCTION_FLOW_NORMAL:
            return [next_position, PORTAPY_OK, simple[1], simple[2]]
        position = next_position

    return [source_size, PORTAPY_OK, _FUNCTION_FLOW_NORMAL, 0]


def _execute_function_body(runtime: int, slot: int) -> list[int]:
    body = _function_body[slot]
    executed = _execute_function_block(runtime, slot, body, len(body), 0, 0, 0)
    if executed[1] != PORTAPY_OK:
        return [0, executed[1]]
    if executed[2] == _FUNCTION_FLOW_RETURN:
        return [executed[3], PORTAPY_OK]
    value = _append_value(runtime, PORTAPY_VALUE_NONE, 0)
    return [value, PORTAPY_OK]'''


def rewrite_generated_function(path: Path) -> Path:
    _rewrite(path)
    source = path.read_text(encoding="utf-8")
    marker = "_call_argument_values: list[int] = [0]\n"
    if marker not in source:
        raise ValueError("generated function entry is missing call argument storage")
    source = source.replace(
        marker,
        marker + "_call_argument_top: list[int] = [1]\n",
        1,
    )
    expression_import = "    _expr_record_expression_failure,\n)"
    if expression_import not in source:
        raise ValueError("generated function entry has an unexpected expression import")
    source = source.replace(
        expression_import,
        "    _expr_record_expression_failure,\n    _expr_truthy,\n)",
        1,
    )
    constant_marker = "_MAX_CALL_DEPTH = 128\n"
    if constant_marker not in source:
        raise ValueError("generated function entry is missing call-depth configuration")
    source = source.replace(
        constant_marker,
        constant_marker + _FUNCTION_FLOW_CONSTANTS,
        1,
    )
    source = _replace_function(
        source,
        "_parse_call_or_expression",
        _parse_call_or_expression(),
    )
    source = _replace_function(
        source,
        "_execute_function_body",
        _execute_function_body(),
    )
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function"]
