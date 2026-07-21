from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_expressions as api


def _eval(runtime: int, source: str) -> int:
    value = api._portapy_eval_span_impl(runtime, source, len(source))
    assert value != 0, source
    return value


def _integer(runtime: int, source: str) -> int:
    return base._portapy_value_as_i64_impl(runtime, _eval(runtime, source))


def _boolean(runtime: int, source: str) -> int:
    return base._portapy_value_as_bool_impl(runtime, _eval(runtime, source))


def _data(runtime: int, value: int) -> bytes:
    size = base._portapy_value_get_size_impl(runtime, value)
    return bytes(base._portapy_value_get_byte_impl(runtime, value, index) for index in range(size))


def _global(runtime: int, name: str) -> int:
    value = api._portapy_get_global_span_impl(runtime, name, len(name))
    assert value != 0
    return value


def test_operator_precedence_and_unary_values() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _integer(runtime, "2 + 3 * 4") == 14
    assert _integer(runtime, "(2 + 3) * 4") == 20
    assert _integer(runtime, "-2 ** 3") == -8
    assert _integer(runtime, "2 ** 3 ** 2") == 512
    assert _integer(runtime, "~1 & 7") == 6
    assert _integer(runtime, "1 << 4 | 3") == 19
    assert _boolean(runtime, "not 0") == 1


def test_comparisons_cover_numbers_text_and_identity() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _boolean(runtime, "3 * 4 == 12") == 1
    assert _boolean(runtime, '"alpha" < "beta"') == 1
    assert _boolean(runtime, 'b"x" != b"y"') == 1
    assert _boolean(runtime, "None is None") == 1
    assert _boolean(runtime, "True is not False") == 1


def test_text_and_bytes_concatenation_and_repetition() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _data(runtime, _eval(runtime, '"Som" + "nia"')) == b"Somnia"
    assert _data(runtime, _eval(runtime, '3 * "ab"')) == b"ababab"
    assert _data(runtime, _eval(runtime, 'b"A" * 3 + b"B"')) == b"AAAB"


def test_execution_supports_expression_pass_and_augmented_assignment() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = (
        "counter = 5\n"
        "counter *= 3\n"
        "counter += 2\n"
        'name = "Som" + "nia"\n'
        "counter == 17\n"
        "pass\n"
    )
    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
    assert base._portapy_value_as_i64_impl(runtime, _global(runtime, "counter")) == 17
    assert _data(runtime, _global(runtime, "name")) == b"Somnia"


def test_invalid_operations_keep_structured_errors() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = '"text" - "other"'
    assert api._portapy_eval_span_impl(runtime, source, len(source)) == 0
    assert base._portapy_error_status_impl(runtime) == base.PORTAPY_TYPE_ERROR

    source = "4 // 0"
    assert api._portapy_eval_span_impl(runtime, source, len(source)) == 0
    assert base._portapy_error_status_impl(runtime) == base.PORTAPY_RUNTIME_ERROR
