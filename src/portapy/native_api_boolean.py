"""Boolean and comparison expression entry for PortaPy's native runtime.

The parser and value semantics in this module are Python source compiled by
asmpython. C and generated assembly remain ABI boundaries only.
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
    PORTAPY_VALUE_FLOAT,
    PORTAPY_VALUE_INT,
    PORTAPY_VALUE_NONE,
    PORTAPY_VALUE_STRING,
    _append_value,
    _bind_global,
    _byte_data,
    _clear_runtime_error,
    _fail,
    _parse_identifier_bounds,
    _runtime_error_line,
    _runtime_is_valid,
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
from .native_api_typed import _parse_typed_expression, _record_typed_failure


_CMP_EQ = 1
_CMP_NE = 2
_CMP_LT = 3
_CMP_LE = 4
_CMP_GT = 5
_CMP_GE = 6
_CMP_IS = 7
_CMP_IS_NOT = 8


def _identifier_char(char: str) -> bool:
    return char.isalnum() or char == "_"


def _trim_range(source: str, start: int, end: int) -> list[int]:
    while start < end and source[start].isspace():
        start += 1
    while end > start and source[end - 1].isspace():
        end -= 1
    return [start, end]


def _word_at(source: str, start: int, end: int, word: str) -> bool:
    word_end = start + len(word)
    if word_end > end or source[start:word_end] != word:
        return False
    if start > 0 and _identifier_char(source[start - 1]):
        return False
    if word_end < end and _identifier_char(source[word_end]):
        return False
    return True


def _find_word_operator(source: str, start: int, end: int, word: str) -> int:
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
        if depth == 0 and _word_at(source, position, end, word):
            return position
        position += 1
    return -1


def _strip_outer_parentheses(source: str, start: int, end: int) -> list[int]:
    bounds = _trim_range(source, start, end)
    start = bounds[0]
    end = bounds[1]
    changed = 0
    while end - start >= 2 and source[start] == "(" and source[end - 1] == ")":
        quote = ""
        escaped = False
        depth = 0
        position = start
        closes_at_end = False
        while position < end:
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
                if depth == 0:
                    closes_at_end = position == end - 1
                    break
            position += 1
        if not closes_at_end:
            break
        start += 1
        end -= 1
        bounds = _trim_range(source, start, end)
        start = bounds[0]
        end = bounds[1]
        changed = 1
    return [start, end, changed]


def _find_comparison(source: str, start: int, end: int) -> list[int]:
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
        if depth != 0:
            position += 1
            continue
        if char == "=" and position + 1 < end and source[position + 1] == "=":
            return [position, position + 2, _CMP_EQ]
        if char == "!" and position + 1 < end and source[position + 1] == "=":
            return [position, position + 2, _CMP_NE]
        if char == "<":
            if position + 1 < end and source[position + 1] == "=":
                return [position, position + 2, _CMP_LE]
            return [position, position + 1, _CMP_LT]
        if char == ">":
            if position + 1 < end and source[position + 1] == "=":
                return [position, position + 2, _CMP_GE]
            return [position, position + 1, _CMP_GT]
        if _word_at(source, position, end, "is"):
            after_is = _skip_space(source, end, position + 2)
            if _word_at(source, after_is, end, "not"):
                return [position, after_is + 3, _CMP_IS_NOT]
            return [position, position + 2, _CMP_IS]
        position += 1
    return [-1, -1, 0]


def _parse_typed_complete(runtime: int, source: str, start: int, end: int) -> list[int]:
    bounds = _trim_range(source, start, end)
    start = bounds[0]
    end = bounds[1]
    parsed = _parse_typed_expression(runtime, source, end, start)
    if parsed[2] != PORTAPY_OK:
        return parsed
    final = _skip_space(source, end, parsed[1])
    if final != end:
        _value_refs[parsed[0]] -= 1
        return [0, final, PORTAPY_COMPILE_ERROR]
    return [parsed[0], end, PORTAPY_OK]


def _truthy(runtime: int, value: int) -> list[int]:
    if not _value_is_valid(runtime, value):
        return [0, PORTAPY_INVALID_HANDLE]
    kind = _value_kind[value]
    if kind == PORTAPY_VALUE_NONE:
        return [0, PORTAPY_OK]
    if kind == PORTAPY_VALUE_BOOL or kind == PORTAPY_VALUE_INT:
        return [1 if _value_i64[value] != 0 else 0, PORTAPY_OK]
    if kind == PORTAPY_VALUE_FLOAT:
        bits = _value_i64[value]
        if bits == 0 or bits == -9223372036854775808:
            return [0, PORTAPY_OK]
        return [1, PORTAPY_OK]
    if kind == PORTAPY_VALUE_STRING or kind == PORTAPY_VALUE_BYTES:
        return [1 if _value_data_size[value] != 0 else 0, PORTAPY_OK]
    return [1, PORTAPY_OK]


def _compare_data(left: int, right: int) -> int:
    left_size = _value_data_size[left]
    right_size = _value_data_size[right]
    limit = left_size
    if right_size < limit:
        limit = right_size
    left_start = _value_data_start[left]
    right_start = _value_data_start[right]
    index = 0
    while index < limit:
        left_byte = _byte_data[left_start + index]
        right_byte = _byte_data[right_start + index]
        if left_byte < right_byte:
            return -1
        if left_byte > right_byte:
            return 1
        index += 1
    if left_size < right_size:
        return -1
    if left_size > right_size:
        return 1
    return 0


def _identity_equal(left: int, right: int) -> bool:
    if left == right:
        return True
    left_kind = _value_kind[left]
    right_kind = _value_kind[right]
    if left_kind != right_kind:
        return False
    if left_kind == PORTAPY_VALUE_NONE:
        return True
    if left_kind == PORTAPY_VALUE_BOOL:
        return _value_i64[left] == _value_i64[right]
    return False


def _value_equal(left: int, right: int) -> bool:
    if left == right:
        return True
    left_kind = _value_kind[left]
    right_kind = _value_kind[right]
    if (left_kind == PORTAPY_VALUE_BOOL or left_kind == PORTAPY_VALUE_INT) and (
        right_kind == PORTAPY_VALUE_BOOL or right_kind == PORTAPY_VALUE_INT
    ):
        return _value_i64[left] == _value_i64[right]
    if left_kind != right_kind:
        return False
    if left_kind == PORTAPY_VALUE_NONE:
        return True
    if left_kind == PORTAPY_VALUE_FLOAT:
        left_bits = _value_i64[left]
        right_bits = _value_i64[right]
        if (left_bits == 0 or left_bits == -9223372036854775808) and (
            right_bits == 0 or right_bits == -9223372036854775808
        ):
            return True
        return left_bits == right_bits
    if left_kind == PORTAPY_VALUE_STRING or left_kind == PORTAPY_VALUE_BYTES:
        return _compare_data(left, right) == 0
    return False


def _ordered_compare(left: int, right: int) -> list[int]:
    left_kind = _value_kind[left]
    right_kind = _value_kind[right]
    if (left_kind == PORTAPY_VALUE_BOOL or left_kind == PORTAPY_VALUE_INT) and (
        right_kind == PORTAPY_VALUE_BOOL or right_kind == PORTAPY_VALUE_INT
    ):
        left_value = _value_i64[left]
        right_value = _value_i64[right]
        if left_value < right_value:
            return [-1, PORTAPY_OK]
        if left_value > right_value:
            return [1, PORTAPY_OK]
        return [0, PORTAPY_OK]
    if left_kind == right_kind and (
        left_kind == PORTAPY_VALUE_STRING or left_kind == PORTAPY_VALUE_BYTES
    ):
        return [_compare_data(left, right), PORTAPY_OK]
    return [0, PORTAPY_TYPE_ERROR]


def _comparison_result(runtime: int, left: int, right: int, operator: int) -> list[int]:
    result = False
    status = PORTAPY_OK
    if operator == _CMP_EQ:
        result = _value_equal(left, right)
    elif operator == _CMP_NE:
        result = not _value_equal(left, right)
    elif operator == _CMP_IS or operator == _CMP_IS_NOT:
        result = _identity_equal(left, right)
        if operator == _CMP_IS_NOT:
            result = not result
    else:
        ordered = _ordered_compare(left, right)
        status = ordered[1]
        if status == PORTAPY_OK:
            relation = ordered[0]
            if operator == _CMP_LT:
                result = relation < 0
            elif operator == _CMP_LE:
                result = relation <= 0
            elif operator == _CMP_GT:
                result = relation > 0
            elif operator == _CMP_GE:
                result = relation >= 0
    _value_refs[left] -= 1
    _value_refs[right] -= 1
    if status != PORTAPY_OK:
        return [0, 0, status]
    value = _append_value(runtime, PORTAPY_VALUE_BOOL, 1 if result else 0)
    return [value, 0, _portapy_last_status_impl()]


def _parse_comparison(runtime: int, source: str, start: int, end: int) -> list[int]:
    comparison = _find_comparison(source, start, end)
    if comparison[0] < 0:
        return _parse_typed_complete(runtime, source, start, end)
    left = _parse_typed_complete(runtime, source, start, comparison[0])
    if left[2] != PORTAPY_OK:
        return left
    right = _parse_typed_complete(runtime, source, comparison[1], end)
    if right[2] != PORTAPY_OK:
        _value_refs[left[0]] -= 1
        return right
    return _comparison_result(runtime, left[0], right[0], comparison[2])


def _parse_not(runtime: int, source: str, start: int, end: int) -> list[int]:
    outer = _strip_outer_parentheses(source, start, end)
    start = outer[0]
    end = outer[1]
    if outer[2] != 0:
        return _parse_or(runtime, source, start, end)
    if _word_at(source, start, end, "not"):
        operand = _parse_not(runtime, source, start + 3, end)
        if operand[2] != PORTAPY_OK:
            return operand
        truth = _truthy(runtime, operand[0])
        _value_refs[operand[0]] -= 1
        if truth[1] != PORTAPY_OK:
            return [0, start, truth[1]]
        value = _append_value(runtime, PORTAPY_VALUE_BOOL, 0 if truth[0] else 1)
        return [value, end, _portapy_last_status_impl()]
    return _parse_comparison(runtime, source, start, end)


def _parse_and(runtime: int, source: str, start: int, end: int) -> list[int]:
    operator = _find_word_operator(source, start, end, "and")
    if operator < 0:
        return _parse_not(runtime, source, start, end)
    left = _parse_not(runtime, source, start, operator)
    if left[2] != PORTAPY_OK:
        return left
    truth = _truthy(runtime, left[0])
    if truth[1] != PORTAPY_OK:
        _value_refs[left[0]] -= 1
        return [0, operator, truth[1]]
    if truth[0] == 0:
        return [left[0], end, PORTAPY_OK]
    _value_refs[left[0]] -= 1
    return _parse_and(runtime, source, operator + 3, end)


def _parse_or(runtime: int, source: str, start: int, end: int) -> list[int]:
    operator = _find_word_operator(source, start, end, "or")
    if operator < 0:
        return _parse_and(runtime, source, start, end)
    left = _parse_and(runtime, source, start, operator)
    if left[2] != PORTAPY_OK:
        return left
    truth = _truthy(runtime, left[0])
    if truth[1] != PORTAPY_OK:
        _value_refs[left[0]] -= 1
        return [0, operator, truth[1]]
    if truth[0] != 0:
        return [left[0], end, PORTAPY_OK]
    _value_refs[left[0]] -= 1
    return _parse_or(runtime, source, operator + 2, end)


def _parse_boolean_expression(runtime: int, source: str, start: int, end: int) -> list[int]:
    outer = _strip_outer_parentheses(source, start, end)
    return _parse_or(runtime, source, outer[0], outer[1])


def _record_expression_failure(runtime: int, status: int, position: int) -> int:
    if status == PORTAPY_TYPE_ERROR:
        return _fail(runtime, status, "TypeError", "values are not orderable", 1, position + 1)
    return _record_typed_failure(runtime, status, position)


def _exec_expression_assignment(runtime: int, source: str, source_size: int) -> int:
    bounds = _parse_identifier_bounds(source, source_size, 0)
    if bounds[2] != PORTAPY_OK:
        return _record_expression_failure(runtime, bounds[2], bounds[1])
    name = source[bounds[0]:bounds[1]]
    position = _skip_space(source, source_size, bounds[1])
    if position >= source_size or source[position] != "=":
        return _record_expression_failure(runtime, PORTAPY_COMPILE_ERROR, position)
    parsed = _parse_boolean_expression(runtime, source, position + 1, source_size)
    if parsed[2] != PORTAPY_OK:
        return _record_expression_failure(runtime, parsed[2], parsed[1])
    return _bind_global(runtime, name, parsed[0])


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
            elif char == ";" or char == "\n" or char == "#":
                break
            position += 1
        end = position
        bounds = _trim_statement_bounds(source, start, end)
        if bounds[0] < bounds[1]:
            statement = source[bounds[0]:bounds[1]]
            status = _exec_expression_assignment(runtime, statement, len(statement))
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
