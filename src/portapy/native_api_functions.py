"""Positional function definitions and calls for PortaPy's native runtime.

This layer deliberately starts with simple function bodies: assignments, bare
expressions, direct or nested calls, and ``return``. Existing if/while execution
continues to use ``native_api_control`` whenever a source unit does not contain
function syntax. All semantics remain Python source compiled by asmpython.
"""
from __future__ import annotations

from .native_api import (
    PORTAPY_COMPILE_ERROR,
    PORTAPY_INVALID_ARGUMENT,
    PORTAPY_INVALID_HANDLE,
    PORTAPY_NOT_FOUND,
    PORTAPY_OK,
    PORTAPY_RUNTIME_ERROR,
    PORTAPY_TYPE_ERROR,
    PORTAPY_VALUE_CALLABLE,
    PORTAPY_VALUE_NONE,
    _append_value,
    _bind_global,
    _clear_runtime_error,
    _fail,
    _find_global_slot,
    _global_name,
    _global_runtime,
    _global_value,
    _parse_identifier_bounds,
    _runtime_error_line,
    _runtime_is_valid,
    _set_status,
    _skip_space,
    _value_i64,
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
from .native_api_control import (
    _line_info,
    _portapy_exec_span_impl as _control_exec_span,
    _syntax_error,
)
from .native_api_expressions import (
    _parse_boolean_expression,
    _record_expression_failure,
)
from .native_api_scalar import (
    _binary,
    _find_assignment,
    _release,
    _retain_global,
)


_function_runtime: list[int] = [0]
_function_name: list[str] = [""]
_function_parameters: list[str] = [""]
_function_body: list[str] = [""]
_function_definition_line: list[int] = [0]
_call_depth: list[int] = [0]
_MAX_CALL_DEPTH = 128


def _ensure_runtime_state(runtime: int) -> None:
    while len(_call_depth) <= runtime:
        _call_depth.append(0)


def _line_number(source: str, position: int) -> int:
    line = 1
    index = 0
    while index < position:
        if source[index] == "\n":
            line += 1
        index += 1
    return line


def _trim(source: str, start: int, end: int) -> list[int]:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    return [start, end]


def _word_at(source: str, start: int, end: int, word: str) -> bool:
    word_end = start + len(word)
    if word_end > end or source[start:word_end] != word:
        return False
    if start > 0:
        before = source[start - 1]
        if before.isalnum() or before == "_":
            return False
    if word_end < end:
        after = source[word_end]
        if after.isalnum() or after == "_":
            return False
    return True


def _parameter_count(parameters: str) -> int:
    if parameters == "":
        return 0
    count = 1
    index = 0
    while index < len(parameters):
        if parameters[index] == ",":
            count += 1
        index += 1
    return count


def _parameter_at(parameters: str, wanted: int) -> str:
    start = 0
    current = 0
    index = 0
    while index <= len(parameters):
        if index == len(parameters) or parameters[index] == ",":
            if current == wanted:
                return parameters[start:index]
            current += 1
            start = index + 1
        index += 1
    return ""


def _parse_parameters(source: str, start: int, end: int) -> list[object]:
    encoded = ""
    count = 0
    position = start
    while True:
        position = _skip_space(source, end, position)
        if position >= end:
            return [encoded, count, PORTAPY_OK]
        bounds = _parse_identifier_bounds(source, end, position)
        if bounds[2] != PORTAPY_OK:
            return ["", bounds[1], PORTAPY_COMPILE_ERROR]
        name = source[bounds[0]:bounds[1]]
        check = 0
        while check < count:
            if _parameter_at(encoded, check) == name:
                return ["", bounds[0], PORTAPY_COMPILE_ERROR]
            check += 1
        if encoded != "":
            encoded += ","
        encoded += name
        count += 1
        position = _skip_space(source, end, bounds[1])
        if position >= end:
            return [encoded, count, PORTAPY_OK]
        if source[position] != ",":
            return ["", position, PORTAPY_COMPILE_ERROR]
        position += 1
        if _skip_space(source, end, position) >= end:
            return ["", position, PORTAPY_COMPILE_ERROR]


def _parse_definition_header(source: str, start: int, end: int) -> list[object]:
    if not _word_at(source, start, end, "def"):
        return ["", "", start, PORTAPY_COMPILE_ERROR]
    position = _skip_space(source, end, start + 3)
    bounds = _parse_identifier_bounds(source, end, position)
    if bounds[2] != PORTAPY_OK:
        return ["", "", bounds[1], PORTAPY_COMPILE_ERROR]
    name = source[bounds[0]:bounds[1]]
    position = _skip_space(source, end, bounds[1])
    if position >= end or source[position] != "(":
        return ["", "", position, PORTAPY_COMPILE_ERROR]
    parameter_start = position + 1
    position = parameter_start
    while position < end and source[position] != ")":
        position += 1
    if position >= end:
        return ["", "", position, PORTAPY_COMPILE_ERROR]
    parsed = _parse_parameters(source, parameter_start, position)
    if parsed[2] != PORTAPY_OK:
        return ["", "", parsed[1], parsed[2]]
    position = _skip_space(source, end, position + 1)
    if position >= end or source[position] != ":":
        return ["", "", position, PORTAPY_COMPILE_ERROR]
    position = _skip_space(source, end, position + 1)
    if position != end:
        return ["", "", position, PORTAPY_COMPILE_ERROR]
    return [name, parsed[0], end, PORTAPY_OK]


def _dedent_body(source: str, start: int, end: int, indent: int) -> str:
    result = ""
    position = start
    while position < end:
        line_end = position
        while line_end < end and source[line_end] != "\n":
            line_end += 1
        remove = 0
        while remove < indent and position + remove < line_end and source[position + remove] == " ":
            remove += 1
        result += source[position + remove:line_end]
        if line_end < end:
            result += "\n"
            line_end += 1
        position = line_end
    return result


def _find_function_slot(runtime: int, name: str) -> int:
    index = 1
    while index < len(_function_runtime):
        if _function_runtime[index] == runtime and _function_name[index] == name:
            global_slot = _find_global_slot(runtime, name)
            if global_slot != 0:
                value = _global_value[global_slot]
                if _value_is_valid(runtime, value) and _value_kind[value] == PORTAPY_VALUE_CALLABLE:
                    if _value_i64[value] == index:
                        return index
        index += 1
    return 0


def _register_function(runtime: int, name: str, parameters: str, body: str, line: int) -> int:
    slot = 1
    while slot < len(_function_runtime):
        if _function_runtime[slot] == runtime and _function_name[slot] == name:
            _function_parameters[slot] = parameters
            _function_body[slot] = body
            _function_definition_line[slot] = line
            value = _append_value(runtime, PORTAPY_VALUE_CALLABLE, slot)
            if value == 0:
                return _last_status_value()
            return _bind_global(runtime, name, value)
        slot += 1
    _function_runtime.append(runtime)
    _function_name.append(name)
    _function_parameters.append(parameters)
    _function_body.append(body)
    _function_definition_line.append(line)
    slot = len(_function_runtime) - 1
    value = _append_value(runtime, PORTAPY_VALUE_CALLABLE, slot)
    if value == 0:
        return _last_status_value()
    return _bind_global(runtime, name, value)


def _last_status_value() -> int:
    from .native_api import _last_status

    return _last_status[0]


def _remove_global(runtime: int, name: str) -> None:
    slot = _find_global_slot(runtime, name)
    if slot == 0:
        return
    value = _global_value[slot]
    if _value_is_valid(runtime, value):
        _value_refs[value] -= 1
    _global_runtime[slot] = 0
    _global_name[slot] = ""
    _global_value[slot] = 0


def _save_binding(
    runtime: int,
    name: str,
    names: list[str],
    existed: list[int],
    values: list[int],
) -> None:
    index = 0
    while index < len(names):
        if names[index] == name:
            return
        index += 1
    names.append(name)
    slot = _find_global_slot(runtime, name)
    if slot == 0:
        existed.append(0)
        values.append(0)
        return
    value = _global_value[slot]
    if not _value_is_valid(runtime, value):
        existed.append(0)
        values.append(0)
        return
    _value_refs[value] += 1
    existed.append(1)
    values.append(value)


def _restore_bindings(runtime: int, names: list[str], existed: list[int], values: list[int]) -> None:
    index = len(names) - 1
    while index >= 0:
        if existed[index] != 0:
            _bind_global(runtime, names[index], values[index])
        else:
            _remove_global(runtime, names[index])
        index -= 1


def _argument_spans(source: str, start: int, end: int) -> list[object]:
    spans: list[int] = []
    bounds = _trim(source, start, end)
    start = bounds[0]
    end = bounds[1]
    if start >= end:
        return [spans, PORTAPY_OK, end]
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
                    return [spans, PORTAPY_COMPILE_ERROR, position]
                depth -= 1
            elif char == "," and depth == 0:
                split = True
        if split:
            item = _trim(source, item_start, position)
            if item[0] >= item[1]:
                return [spans, PORTAPY_COMPILE_ERROR, position]
            spans.append(item[0])
            spans.append(item[1])
            item_start = position + 1
        position += 1
    if quote != "" or depth != 0:
        return [spans, PORTAPY_COMPILE_ERROR, end]
    return [spans, PORTAPY_OK, end]


def _direct_call_bounds(source: str, start: int, end: int) -> list[object]:
    bounds = _trim(source, start, end)
    start = bounds[0]
    end = bounds[1]
    name_bounds = _parse_identifier_bounds(source, end, start)
    if name_bounds[2] != PORTAPY_OK:
        return ["", 0, 0, 0]
    position = _skip_space(source, end, name_bounds[1])
    if position >= end or source[position] != "(":
        return ["", 0, 0, 0]
    depth = 0
    quote = ""
    escaped = False
    scan = position
    close = -1
    while scan < end:
        char = source[scan]
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
            depth -= 1
            if depth == 0:
                close = scan
                break
        scan += 1
    if close < 0 or _skip_space(source, end, close + 1) != end:
        return ["", 0, 0, 0]
    return [source[name_bounds[0]:name_bounds[1]], position + 1, close, 1]


def _parse_call_or_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    call = _direct_call_bounds(source, start, end)
    if call[3] == 0:
        return _parse_boolean_expression(runtime, source, start, end)
    function_slot = _find_function_slot(runtime, str(call[0]))
    if function_slot == 0:
        return _parse_boolean_expression(runtime, source, start, end)
    arguments = _argument_spans(source, int(call[1]), int(call[2]))
    if arguments[1] != PORTAPY_OK:
        return [0, int(arguments[2]), int(arguments[1])]
    handles: list[int] = []
    spans = arguments[0]
    index = 0
    while index < len(spans):
        parsed = _parse_call_or_expression(runtime, source, spans[index], spans[index + 1])
        if parsed[2] != PORTAPY_OK:
            release = 0
            while release < len(handles):
                _release(runtime, handles[release])
                release += 1
            return parsed
        handles.append(parsed[0])
        index += 2
    return _invoke_function(runtime, function_slot, handles, start)


def _collect_local_names(body: str, parameters: str) -> list[str]:
    names: list[str] = []
    parameter_index = 0
    while parameter_index < _parameter_count(parameters):
        names.append(_parameter_at(parameters, parameter_index))
        parameter_index += 1
    position = 0
    body_size = len(body)
    while position < body_size:
        line_end = position
        while line_end < body_size and body[line_end] != "\n":
            line_end += 1
        bounds = _trim(body, position, line_end)
        if bounds[0] < bounds[1] and not _word_at(body, bounds[0], bounds[1], "return"):
            statement = body[bounds[0]:bounds[1]]
            assignment = _find_assignment(statement, len(statement))
            if assignment[0] != "":
                left = statement[0:int(assignment[1])]
                left_bounds = _parse_identifier_bounds(left, len(left), 0)
                if left_bounds[2] == PORTAPY_OK:
                    name = left[left_bounds[0]:left_bounds[1]]
                    found = False
                    index = 0
                    while index < len(names):
                        if names[index] == name:
                            found = True
                            break
                        index += 1
                    if not found:
                        names.append(name)
        position = line_end + 1
    return names


def _operator_from_assignment(assignment: str) -> str:
    if assignment == "+=":
        return "+"
    if assignment == "-=":
        return "-"
    if assignment == "*=":
        return "*"
    if assignment == "//=":
        return "//"
    if assignment == "%=":
        return "%"
    if assignment == "&=":
        return "&"
    if assignment == "^=":
        return "^"
    if assignment == "|=":
        return "|"
    return ""


def _execute_function_statement(runtime: int, statement: str, line: int) -> int:
    assignment = _find_assignment(statement, len(statement))
    if assignment[0] == "":
        parsed = _parse_call_or_expression(runtime, statement, 0, len(statement))
        if parsed[2] != PORTAPY_OK:
            _runtime_error_line[runtime] = line
            return _record_expression_failure(runtime, parsed[2], parsed[1])
        _release(runtime, parsed[0])
        return _set_status(PORTAPY_OK)
    left = statement[0:int(assignment[1])]
    bounds = _parse_identifier_bounds(left, len(left), 0)
    if bounds[2] != PORTAPY_OK or _skip_space(left, len(left), bounds[1]) != len(left):
        return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid assignment target", line, 1)
    name = left[bounds[0]:bounds[1]]
    parsed = _parse_call_or_expression(runtime, statement, int(assignment[2]), len(statement))
    if parsed[2] != PORTAPY_OK:
        _runtime_error_line[runtime] = line
        return _record_expression_failure(runtime, parsed[2], parsed[1])
    if assignment[0] != "=":
        current = _retain_global(runtime, name, 0)
        if current[2] != PORTAPY_OK:
            _release(runtime, parsed[0])
            return _record_expression_failure(runtime, current[2], 0)
        operator = _operator_from_assignment(str(assignment[0]))
        if operator == "":
            _release(runtime, current[0])
            _release(runtime, parsed[0])
            return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "unsupported augmented assignment", line, 1)
        combined = _binary(runtime, current[0], parsed[0], operator, int(assignment[1]))
        if combined[2] != PORTAPY_OK:
            return _record_expression_failure(runtime, combined[2], combined[1])
        parsed = combined
    return _bind_global(runtime, name, parsed[0])


def _execute_function_body(runtime: int, slot: int) -> list[int]:
    body = _function_body[slot]
    position = 0
    line = _function_definition_line[slot] + 1
    while position < len(body):
        line_end = position
        while line_end < len(body) and body[line_end] != "\n":
            line_end += 1
        bounds = _trim(body, position, line_end)
        if bounds[0] < bounds[1]:
            statement = body[bounds[0]:bounds[1]]
            if _word_at(statement, 0, len(statement), "return"):
                expression_start = _skip_space(statement, len(statement), 6)
                if expression_start >= len(statement):
                    value = _append_value(runtime, PORTAPY_VALUE_NONE, 0)
                    return [value, PORTAPY_OK]
                parsed = _parse_call_or_expression(runtime, statement, expression_start, len(statement))
                if parsed[2] != PORTAPY_OK:
                    _runtime_error_line[runtime] = line
                    return [0, _record_expression_failure(runtime, parsed[2], parsed[1])]
                return [parsed[0], PORTAPY_OK]
            if _word_at(statement, 0, len(statement), "if") or _word_at(statement, 0, len(statement), "while") or _word_at(statement, 0, len(statement), "for") or _word_at(statement, 0, len(statement), "try") or _word_at(statement, 0, len(statement), "with") or _word_at(statement, 0, len(statement), "match") or _word_at(statement, 0, len(statement), "def") or _word_at(statement, 0, len(statement), "class"):
                return [0, _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "compound statements inside native functions are not implemented yet", line, 1)]
            status = _execute_function_statement(runtime, statement, line)
            if status != PORTAPY_OK:
                return [0, status]
        position = line_end + 1
        line += 1
    value = _append_value(runtime, PORTAPY_VALUE_NONE, 0)
    return [value, PORTAPY_OK]


def _invoke_function(runtime: int, slot: int, arguments: list[int], position: int) -> list[int]:
    expected = _parameter_count(_function_parameters[slot])
    if len(arguments) != expected:
        index = 0
        while index < len(arguments):
            _release(runtime, arguments[index])
            index += 1
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "function argument count mismatch", _function_definition_line[slot], 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    _ensure_runtime_state(runtime)
    if _call_depth[runtime] >= _MAX_CALL_DEPTH:
        index = 0
        while index < len(arguments):
            _release(runtime, arguments[index])
            index += 1
        _fail(runtime, PORTAPY_RUNTIME_ERROR, "RecursionError", "maximum PortaPy call depth exceeded", _function_definition_line[slot], 1)
        return [0, position, PORTAPY_RUNTIME_ERROR]

    names = _collect_local_names(_function_body[slot], _function_parameters[slot])
    saved_names: list[str] = []
    saved_existed: list[int] = []
    saved_values: list[int] = []
    index = 0
    while index < len(names):
        _save_binding(runtime, names[index], saved_names, saved_existed, saved_values)
        index += 1

    index = 0
    while index < expected:
        parameter = _parameter_at(_function_parameters[slot], index)
        _bind_global(runtime, parameter, arguments[index])
        index += 1

    _call_depth[runtime] += 1
    executed = _execute_function_body(runtime, slot)
    _call_depth[runtime] -= 1
    _restore_bindings(runtime, saved_names, saved_existed, saved_values)
    if executed[1] != PORTAPY_OK:
        return [0, position, executed[1]]
    return [executed[0], position, PORTAPY_OK]


def _source_uses_functions(runtime: int, source: str) -> bool:
    position = 0
    while position < len(source):
        line_end = position
        while line_end < len(source) and source[line_end] != "\n":
            line_end += 1
        bounds = _trim(source, position, line_end)
        if bounds[0] < bounds[1]:
            if _word_at(source, bounds[0], bounds[1], "def"):
                return True
            call = _direct_call_bounds(source, bounds[0], bounds[1])
            if call[3] != 0 and _find_function_slot(runtime, str(call[0])) != 0:
                return True
            statement = source[bounds[0]:bounds[1]]
            assignment = _find_assignment(statement, len(statement))
            if assignment[0] != "":
                call = _direct_call_bounds(statement, int(assignment[2]), len(statement))
                if call[3] != 0 and _find_function_slot(runtime, str(call[0])) != 0:
                    return True
        position = line_end + 1
    return False


def _exec_function_source(runtime: int, source: str, source_size: int) -> int:
    position = 0
    while position < source_size:
        info = _line_info(source, source_size, position)
        if info[6] != PORTAPY_OK:
            return _syntax_error(runtime, source, info[4], "tabs are not supported for indentation")
        if info[4] >= info[5]:
            position = info[2]
            continue
        if info[3] != 0:
            return _syntax_error(runtime, source, info[4], "unexpected indent")
        start = info[4]
        end = info[5]
        if _word_at(source, start, end, "def"):
            header = _parse_definition_header(source, start, end)
            if header[3] != PORTAPY_OK:
                return _syntax_error(runtime, source, int(header[2]), "invalid function definition")
            child_position = info[2]
            if child_position >= source_size:
                return _syntax_error(runtime, source, end, "expected an indented function body")
            child = _line_info(source, source_size, child_position)
            if child[6] != PORTAPY_OK or child[3] <= 0:
                return _syntax_error(runtime, source, child[4], "expected an indented function body")
            child_indent = child[3]
            body_end = child_position
            while body_end < source_size:
                body_info = _line_info(source, source_size, body_end)
                if body_info[4] < body_info[5] and body_info[3] < child_indent:
                    break
                body_end = body_info[2]
            body = _dedent_body(source, child_position, body_end, child_indent)
            status = _register_function(
                runtime,
                str(header[0]),
                str(header[1]),
                body,
                _line_number(source, start),
            )
            if status != PORTAPY_OK:
                return status
            position = body_end
            continue
        statement = source[start:end]
        if _word_at(statement, 0, len(statement), "if") or _word_at(statement, 0, len(statement), "while") or _word_at(statement, 0, len(statement), "for") or _word_at(statement, 0, len(statement), "try") or _word_at(statement, 0, len(statement), "with") or _word_at(statement, 0, len(statement), "match") or statement == "else:":
            return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "compound statements cannot share a source unit with native function definitions yet", _line_number(source, start), 1)
        status = _execute_function_statement(runtime, statement, _line_number(source, start))
        if status != PORTAPY_OK:
            return status
        position = info[2]
    return _set_status(PORTAPY_OK)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        return 0
    parsed = _parse_call_or_expression(runtime, source, 0, source_size)
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
    if not _source_uses_functions(runtime, source):
        return _control_exec_span(runtime, source, source_size)
    return _exec_function_source(runtime, source, source_size)
