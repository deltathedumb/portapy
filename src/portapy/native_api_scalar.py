"""General scalar-expression native source entry for PortaPy.

This layer extends the typed-literal entry with Python-owned operator precedence,
comparisons, unary operators, and string/bytes sequence operations. Native
assembly remains an ABI adapter and contains no interpreter semantics.
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
    PORTAPY_VALUE_BOOL,
    PORTAPY_VALUE_BYTES,
    PORTAPY_VALUE_INT,
    PORTAPY_VALUE_NONE,
    PORTAPY_VALUE_STRING,
    _append_data_value,
    _append_value,
    _bind_global,
    _byte_data,
    _clear_runtime_error,
    _fail,
    _last_status,
    _parse_identifier_bounds,
    _parse_number,
    _runtime_error_line,
    _runtime_error_status,
    _runtime_is_valid,
    _set_data_byte,
    _set_status,
    _skip_space,
    _trim_statement_bounds,
    _value_data_size,
    _value_data_start,
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
from .native_api_typed import _parse_data_literal, _retain_global


def _release(runtime: int, value: int) -> None:
    if _value_is_valid(runtime, value):
        _value_refs[value] -= 1


def _keyword_at(source: str, source_size: int, position: int, keyword: str) -> bool:
    position = _skip_space(source, source_size, position)
    end = position + len(keyword)
    if end > source_size or source[position:end] != keyword:
        return False
    if end < source_size:
        after = source[end]
        if after.isalnum() or after == "_":
            return False
    return True


def _truthy(runtime: int, value: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, PORTAPY_INVALID_HANDLE]
    kind = _value_kind[value]
    if kind == PORTAPY_VALUE_NONE:
        return [0, PORTAPY_OK]
    if kind == PORTAPY_VALUE_BOOL or kind == PORTAPY_VALUE_INT:
        return [1 if _value_i64[value] != 0 else 0, PORTAPY_OK]
    if kind == PORTAPY_VALUE_STRING or kind == PORTAPY_VALUE_BYTES:
        return [1 if _value_data_size[value] != 0 else 0, PORTAPY_OK]
    return [1, PORTAPY_OK]


def _numeric(runtime: int, value: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, PORTAPY_INVALID_HANDLE]
    kind = _value_kind[value]
    if kind != PORTAPY_VALUE_INT and kind != PORTAPY_VALUE_BOOL:
        return [0, PORTAPY_TYPE_ERROR]
    return [_value_i64[value], PORTAPY_OK]


def _copy_sequence(runtime: int, kind: int, first: int, second: int, repeats: int) -> int:
    first_size = _value_data_size[first]
    second_size = 0
    if second != 0:
        second_size = _value_data_size[second]
    total = (first_size + second_size) * repeats
    result = _append_data_value(runtime, kind, total)
    if result == 0:
        return 0
    destination = 0
    repeat = 0
    while repeat < repeats:
        index = 0
        first_start = _value_data_start[first]
        while index < first_size:
            _set_data_byte(runtime, result, destination, _byte_data[first_start + index])
            destination += 1
            index += 1
        if second != 0:
            index = 0
            second_start = _value_data_start[second]
            while index < second_size:
                _set_data_byte(runtime, result, destination, _byte_data[second_start + index])
                destination += 1
                index += 1
        repeat += 1
    return result


def _data_order(first: int, second: int) -> int:
    first_size = _value_data_size[first]
    second_size = _value_data_size[second]
    first_start = _value_data_start[first]
    second_start = _value_data_start[second]
    common = first_size
    if second_size < common:
        common = second_size
    index = 0
    while index < common:
        left = _byte_data[first_start + index]
        right = _byte_data[second_start + index]
        if left < right:
            return -1
        if left > right:
            return 1
        index += 1
    if first_size < second_size:
        return -1
    if first_size > second_size:
        return 1
    return 0


def _power(base: int, exponent: int) -> int:
    result = 1
    factor = base
    remaining = exponent
    while remaining > 0:
        if remaining % 2 == 1:
            result *= factor
        remaining //= 2
        if remaining > 0:
            factor *= factor
    return result


def _binary(runtime: int, left: int, right: int, operator: str, position: int) -> list[int]:
    left_kind = _value_kind[left]
    right_kind = _value_kind[right]
    result = 0

    if operator == "+" and left_kind == right_kind and (
        left_kind == PORTAPY_VALUE_STRING or left_kind == PORTAPY_VALUE_BYTES
    ):
        result = _copy_sequence(runtime, left_kind, left, right, 1)
    elif operator == "*" and (
        left_kind == PORTAPY_VALUE_STRING or left_kind == PORTAPY_VALUE_BYTES
    ) and (right_kind == PORTAPY_VALUE_INT or right_kind == PORTAPY_VALUE_BOOL):
        count = _value_i64[right]
        if count < 0:
            count = 0
        result = _copy_sequence(runtime, left_kind, left, 0, count)
    elif operator == "*" and (
        right_kind == PORTAPY_VALUE_STRING or right_kind == PORTAPY_VALUE_BYTES
    ) and (left_kind == PORTAPY_VALUE_INT or left_kind == PORTAPY_VALUE_BOOL):
        count = _value_i64[left]
        if count < 0:
            count = 0
        result = _copy_sequence(runtime, right_kind, right, 0, count)
    else:
        left_number = _numeric(runtime, left)
        right_number = _numeric(runtime, right)
        if left_number[1] != PORTAPY_OK or right_number[1] != PORTAPY_OK:
            _release(runtime, left)
            _release(runtime, right)
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "unsupported operand types", 1, position + 1)
            return [0, position, PORTAPY_TYPE_ERROR]
        first = left_number[0]
        second = right_number[0]
        if operator == "+":
            result = _append_value(runtime, PORTAPY_VALUE_INT, first + second)
        elif operator == "-":
            result = _append_value(runtime, PORTAPY_VALUE_INT, first - second)
        elif operator == "*":
            result = _append_value(runtime, PORTAPY_VALUE_INT, first * second)
        elif operator == "//":
            if second == 0:
                _release(runtime, left)
                _release(runtime, right)
                _fail(runtime, PORTAPY_RUNTIME_ERROR, "ZeroDivisionError", "integer division by zero", 1, position + 1)
                return [0, position, PORTAPY_RUNTIME_ERROR]
            result = _append_value(runtime, PORTAPY_VALUE_INT, first // second)
        elif operator == "%":
            if second == 0:
                _release(runtime, left)
                _release(runtime, right)
                _fail(runtime, PORTAPY_RUNTIME_ERROR, "ZeroDivisionError", "integer modulo by zero", 1, position + 1)
                return [0, position, PORTAPY_RUNTIME_ERROR]
            result = _append_value(runtime, PORTAPY_VALUE_INT, first % second)
        elif operator == "**":
            if second < 0:
                _release(runtime, left)
                _release(runtime, right)
                _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "negative integer powers require float support", 1, position + 1)
                return [0, position, PORTAPY_TYPE_ERROR]
            result = _append_value(runtime, PORTAPY_VALUE_INT, _power(first, second))
        elif operator == "<<" or operator == ">>":
            if second < 0:
                _release(runtime, left)
                _release(runtime, right)
                _fail(runtime, PORTAPY_RUNTIME_ERROR, "ValueError", "negative shift count", 1, position + 1)
                return [0, position, PORTAPY_RUNTIME_ERROR]
            if operator == "<<":
                result = _append_value(runtime, PORTAPY_VALUE_INT, first << second)
            else:
                result = _append_value(runtime, PORTAPY_VALUE_INT, first >> second)
        elif operator == "&":
            result = _append_value(runtime, PORTAPY_VALUE_INT, first & second)
        elif operator == "^":
            result = _append_value(runtime, PORTAPY_VALUE_INT, first ^ second)
        elif operator == "|":
            result = _append_value(runtime, PORTAPY_VALUE_INT, first | second)
        else:
            _release(runtime, left)
            _release(runtime, right)
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "true division is unavailable until native float expressions land", 1, position + 1)
            return [0, position, PORTAPY_TYPE_ERROR]

    _release(runtime, left)
    _release(runtime, right)
    if result == 0:
        return [0, position, _last_status[0]]
    return [result, position, PORTAPY_OK]


def _equal(left: int, right: int) -> bool:
    left_kind = _value_kind[left]
    right_kind = _value_kind[right]
    if (left_kind == PORTAPY_VALUE_INT or left_kind == PORTAPY_VALUE_BOOL) and (
        right_kind == PORTAPY_VALUE_INT or right_kind == PORTAPY_VALUE_BOOL
    ):
        return _value_i64[left] == _value_i64[right]
    if left_kind != right_kind:
        return False
    if left_kind == PORTAPY_VALUE_NONE:
        return True
    if left_kind == PORTAPY_VALUE_STRING or left_kind == PORTAPY_VALUE_BYTES:
        return _data_order(left, right) == 0
    return left == right


def _compare(runtime: int, left: int, right: int, operator: str, position: int) -> list[int]:
    left_kind = _value_kind[left]
    right_kind = _value_kind[right]
    result = False
    if operator == "==":
        result = _equal(left, right)
    elif operator == "!=":
        result = not _equal(left, right)
    elif operator == "is" or operator == "is not":
        identical = left == right
        if left_kind == PORTAPY_VALUE_NONE and right_kind == PORTAPY_VALUE_NONE:
            identical = True
        elif left_kind == PORTAPY_VALUE_BOOL and right_kind == PORTAPY_VALUE_BOOL:
            identical = _value_i64[left] == _value_i64[right]
        result = identical
        if operator == "is not":
            result = not result
    elif (left_kind == PORTAPY_VALUE_INT or left_kind == PORTAPY_VALUE_BOOL) and (
        right_kind == PORTAPY_VALUE_INT or right_kind == PORTAPY_VALUE_BOOL
    ):
        first = _value_i64[left]
        second = _value_i64[right]
        if operator == "<":
            result = first < second
        elif operator == "<=":
            result = first <= second
        elif operator == ">":
            result = first > second
        else:
            result = first >= second
    elif left_kind == right_kind and (
        left_kind == PORTAPY_VALUE_STRING or left_kind == PORTAPY_VALUE_BYTES
    ):
        ordering = _data_order(left, right)
        if operator == "<":
            result = ordering < 0
        elif operator == "<=":
            result = ordering <= 0
        elif operator == ">":
            result = ordering > 0
        else:
            result = ordering >= 0
    else:
        _release(runtime, left)
        _release(runtime, right)
        _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "values are not orderable", 1, position + 1)
        return [0, position, PORTAPY_TYPE_ERROR]
    _release(runtime, left)
    _release(runtime, right)
    value = _append_value(runtime, PORTAPY_VALUE_BOOL, 1 if result else 0)
    return [value, position, _last_status[0]]


def _parse_atom(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    position = _skip_space(source, source_size, position)
    if position >= source_size:
        return [0, position, PORTAPY_COMPILE_ERROR]
    char = source[position]
    if char == "'" or char == '"':
        return _parse_data_literal(runtime, source, source_size, position)
    if (char == "b" or char == "B") and position + 1 < source_size and (
        source[position + 1] == "'" or source[position + 1] == '"'
    ):
        return _parse_data_literal(runtime, source, source_size, position)
    if char == "(":
        parsed = _parse_comparison(runtime, source, source_size, position + 1)
        if parsed[2] != PORTAPY_OK:
            return parsed
        end = _skip_space(source, source_size, parsed[1])
        if end >= source_size or source[end] != ")":
            _release(runtime, parsed[0])
            return [0, end, PORTAPY_COMPILE_ERROR]
        parsed[1] = end + 1
        return parsed
    if char.isdigit():
        parsed = _parse_number(source, source_size, position)
        if parsed[2] != PORTAPY_OK:
            return [0, parsed[1], parsed[2]]
        value = _append_value(runtime, PORTAPY_VALUE_INT, parsed[0])
        return [value, parsed[1], _last_status[0]]
    if char.isalpha() or char == "_":
        bounds = _parse_identifier_bounds(source, source_size, position)
        if bounds[2] != PORTAPY_OK:
            return [0, bounds[1], bounds[2]]
        name = source[bounds[0]:bounds[1]]
        if name == "None":
            value = _append_value(runtime, PORTAPY_VALUE_NONE, 0)
            return [value, bounds[1], _last_status[0]]
        if name == "True" or name == "False":
            value = _append_value(runtime, PORTAPY_VALUE_BOOL, 1 if name == "True" else 0)
            return [value, bounds[1], _last_status[0]]
        return _retain_global(runtime, name, bounds[1])
    return [0, position, PORTAPY_COMPILE_ERROR]


def _parse_power(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    left = _parse_atom(runtime, source, source_size, position)
    if left[2] != PORTAPY_OK:
        return left
    operator_at = _skip_space(source, source_size, left[1])
    if operator_at + 1 < source_size and source[operator_at:operator_at + 2] == "**":
        right = _parse_unary(runtime, source, source_size, operator_at + 2)
        if right[2] != PORTAPY_OK:
            _release(runtime, left[0])
            return right
        result = _binary(runtime, left[0], right[0], "**", operator_at)
        result[1] = right[1]
        return result
    return left


def _parse_unary(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    position = _skip_space(source, source_size, position)
    if _keyword_at(source, source_size, position, "not"):
        operand = _parse_unary(runtime, source, source_size, position + 3)
        if operand[2] != PORTAPY_OK:
            return operand
        truth = _truthy(runtime, operand[0])
        _release(runtime, operand[0])
        if truth[1] != PORTAPY_OK:
            return [0, position, truth[1]]
        value = _append_value(runtime, PORTAPY_VALUE_BOOL, 0 if truth[0] else 1)
        return [value, operand[1], _last_status[0]]
    if position < source_size and source[position] in "+-~":
        operator = source[position]
        operand = _parse_unary(runtime, source, source_size, position + 1)
        if operand[2] != PORTAPY_OK:
            return operand
        numeric = _numeric(runtime, operand[0])
        _release(runtime, operand[0])
        if numeric[1] != PORTAPY_OK:
            _fail(runtime, PORTAPY_TYPE_ERROR, "TypeError", "bad operand type for unary operator", 1, position + 1)
            return [0, position, PORTAPY_TYPE_ERROR]
        value = numeric[0]
        if operator == "-":
            value = -value
        elif operator == "~":
            value = ~value
        result = _append_value(runtime, PORTAPY_VALUE_INT, value)
        return [result, operand[1], _last_status[0]]
    return _parse_power(runtime, source, source_size, position)


def _parse_left(runtime: int, source: str, source_size: int, position: int, lower, operators: tuple[str, ...]) -> list[int]:
    left = lower(runtime, source, source_size, position)
    if left[2] != PORTAPY_OK:
        return left
    while True:
        operator_at = _skip_space(source, source_size, left[1])
        selected = ""
        for operator in operators:
            if source[operator_at:operator_at + len(operator)] == operator:
                selected = operator
                break
        if not selected:
            return left
        right = lower(runtime, source, source_size, operator_at + len(selected))
        if right[2] != PORTAPY_OK:
            _release(runtime, left[0])
            return right
        result = _binary(runtime, left[0], right[0], selected, operator_at)
        result[1] = right[1]
        if result[2] != PORTAPY_OK:
            return result
        left = result


def _parse_multiply(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    return _parse_left(runtime, source, source_size, position, _parse_unary, ("//", "*", "%", "/"))


def _parse_add(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    return _parse_left(runtime, source, source_size, position, _parse_multiply, ("+", "-"))


def _parse_shift(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    return _parse_left(runtime, source, source_size, position, _parse_add, ("<<", ">>"))


def _parse_bitand(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    return _parse_left(runtime, source, source_size, position, _parse_shift, ("&",))


def _parse_bitxor(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    return _parse_left(runtime, source, source_size, position, _parse_bitand, ("^",))


def _parse_bitor(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    return _parse_left(runtime, source, source_size, position, _parse_bitxor, ("|",))


def _comparison_operator(source: str, source_size: int, position: int) -> list[object]:
    position = _skip_space(source, source_size, position)
    for operator in ("==", "!=", "<=", ">="):
        if source[position:position + 2] == operator:
            return [operator, position + 2]
    if _keyword_at(source, source_size, position, "is"):
        after = _skip_space(source, source_size, position + 2)
        if _keyword_at(source, source_size, after, "not"):
            return ["is not", after + 3]
        return ["is", position + 2]
    if position < source_size and source[position] in "<>":
        return [source[position], position + 1]
    return ["", position]


def _parse_comparison(runtime: int, source: str, source_size: int, position: int) -> list[int]:
    left = _parse_bitor(runtime, source, source_size, position)
    if left[2] != PORTAPY_OK:
        return left
    operator = _comparison_operator(source, source_size, left[1])
    if not operator[0]:
        return left
    right = _parse_bitor(runtime, source, source_size, int(operator[1]))
    if right[2] != PORTAPY_OK:
        _release(runtime, left[0])
        return right
    result = _compare(runtime, left[0], right[0], str(operator[0]), int(operator[1]))
    result[1] = right[1]
    return result


def _record_failure(runtime: int, status: int, position: int) -> int:
    if _runtime_is_valid(runtime) and _runtime_error_status[runtime] != PORTAPY_OK:
        return _set_status(status)
    if status == PORTAPY_NOT_FOUND:
        return _fail(runtime, status, "NameError", "name is not defined", 1, position + 1)
    if status == PORTAPY_TYPE_ERROR:
        return _fail(runtime, status, "TypeError", "invalid scalar expression", 1, position + 1)
    if status == PORTAPY_RUNTIME_ERROR:
        return _fail(runtime, status, "RuntimeError", "scalar expression failed", 1, position + 1)
    return _fail(runtime, PORTAPY_COMPILE_ERROR, "SyntaxError", "invalid PortaPy expression", 1, position + 1)


def _find_assignment(source: str, source_size: int) -> list[object]:
    quote = ""
    escaped = False
    depth = 0
    position = 0
    while position < source_size:
        char = source[position]
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
            depth -= 1
        elif depth == 0 and char == "=":
            before = source[position - 1] if position > 0 else ""
            after = source[position + 1] if position + 1 < source_size else ""
            if before not in "=!<>" and after != "=":
                operator = "="
                start = position
                if before in "+-*%&|^" or (before == "/" and position > 1 and source[position - 2] == "/"):
                    if before == "/":
                        operator = "//="
                        start = position - 2
                    else:
                        operator = before + "="
                        start = position - 1
                return [operator, start, position + 1]
        position += 1
    return ["", source_size, source_size]


def _exec_statement(runtime: int, source: str, source_size: int) -> int:
    bounds = _trim_statement_bounds(source, 0, source_size)
    source = source[bounds[0]:bounds[1]]
    source_size = len(source)
    if source_size == 0 or source == "pass":
        return _set_status(PORTAPY_OK)
    assignment = _find_assignment(source, source_size)
    if assignment[0]:
        left_text = source[0:int(assignment[1])]
        left_bounds = _parse_identifier_bounds(left_text, len(left_text), 0)
        if left_bounds[2] != PORTAPY_OK or _skip_space(left_text, len(left_text), left_bounds[1]) != len(left_text):
            return _record_failure(runtime, PORTAPY_COMPILE_ERROR, left_bounds[1])
        name = left_text[left_bounds[0]:left_bounds[1]]
        right = _parse_comparison(runtime, source, source_size, int(assignment[2]))
        if right[2] != PORTAPY_OK:
            return _record_failure(runtime, right[2], right[1])
        end = _skip_space(source, source_size, right[1])
        if end != source_size:
            _release(runtime, right[0])
            return _record_failure(runtime, PORTAPY_COMPILE_ERROR, end)
        if assignment[0] != "=":
            current = _retain_global(runtime, name, 0)
            if current[2] != PORTAPY_OK:
                _release(runtime, right[0])
                return _record_failure(runtime, current[2], 0)
            operator = str(assignment[0])[:-1]
            combined = _binary(runtime, current[0], right[0], operator, int(assignment[1]))
            if combined[2] != PORTAPY_OK:
                return _record_failure(runtime, combined[2], combined[1])
            right = combined
        return _bind_global(runtime, name, right[0])
    value = _parse_comparison(runtime, source, source_size, 0)
    if value[2] != PORTAPY_OK:
        return _record_failure(runtime, value[2], value[1])
    end = _skip_space(source, source_size, value[1])
    if end != source_size:
        _release(runtime, value[0])
        return _record_failure(runtime, PORTAPY_COMPILE_ERROR, end)
    _release(runtime, value[0])
    return _set_status(PORTAPY_OK)


def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        _set_status(PORTAPY_INVALID_HANDLE)
        return 0
    _clear_runtime_error(runtime)
    if source_size < 0:
        _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
        return 0
    parsed = _parse_comparison(runtime, source, source_size, 0)
    if parsed[2] != PORTAPY_OK:
        _record_failure(runtime, parsed[2], parsed[1])
        return 0
    end = _skip_space(source, source_size, parsed[1])
    if end != source_size:
        _release(runtime, parsed[0])
        _record_failure(runtime, PORTAPY_COMPILE_ERROR, end)
        return 0
    return parsed[0]


def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:
    if not _runtime_is_valid(runtime):
        return _set_status(PORTAPY_INVALID_HANDLE)
    _clear_runtime_error(runtime)
    if source_size < 0:
        return _fail(runtime, PORTAPY_INVALID_ARGUMENT, "ValueError", "source size cannot be negative")
    position = 0
    line = 1
    while position < source_size:
        while position < source_size:
            char = source[position]
            if char != ";" and not char.isspace():
                break
            if char == "\n":
                line += 1
            position += 1
        if position >= source_size:
            return _set_status(PORTAPY_OK)
        start = position
        statement_line = line
        quote = ""
        escaped = False
        depth = 0
        while position < source_size:
            char = source[position]
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
                depth -= 1
            elif depth == 0 and (char == ";" or char == "\n" or char == "#"):
                break
            position += 1
        statement = source[start:position]
        status = _exec_statement(runtime, statement, len(statement))
        if status != PORTAPY_OK:
            _runtime_error_line[runtime] = statement_line
            return status
        if position < source_size and source[position] == "#":
            while position < source_size and source[position] != "\n":
                position += 1
        if position < source_size:
            if source[position] == "\n":
                line += 1
            position += 1
    return _set_status(PORTAPY_OK)
