from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_expressions as api


def _eval(runtime: int, expression: str) -> int:
    value = api._portapy_eval_span_impl(runtime, expression, len(expression))
    assert value != 0, expression
    return value


def _bool(runtime: int, expression: str) -> bool:
    value = _eval(runtime, expression)
    assert base._portapy_value_get_kind_impl(runtime, value) == base.PORTAPY_VALUE_BOOL
    result = base._portapy_value_as_bool_impl(runtime, value) != 0
    assert base._portapy_value_release_impl(runtime, value) == base.PORTAPY_OK
    return result


def _data(runtime: int, value: int) -> bytes:
    size = base._portapy_value_get_size_impl(runtime, value)
    assert base._portapy_last_status_impl() == base.PORTAPY_OK
    return bytes(base._portapy_value_get_byte_impl(runtime, value, index) for index in range(size))


def test_native_comparisons_cover_numeric_text_bytes_and_identity() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = 'name = "Somnia"\nalias = name\nother = "PortaPy"\npayload = b"abc"\n'
    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK

    assert _bool(runtime, "40 + 2 == 42")
    assert _bool(runtime, "True == 1")
    assert _bool(runtime, '"abc" < "abd"')
    assert _bool(runtime, 'b"abc" <= b"abc"')
    assert _bool(runtime, "name == alias")
    assert _bool(runtime, "name is alias")
    assert _bool(runtime, "name is not other")
    assert _bool(runtime, "None is None")
    assert not _bool(runtime, "False != 0")


def test_and_or_return_operands_and_not_returns_bool() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = 'empty = ""\nname = "Somnia"\nzero = 0\nanswer = 42\n'
    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK

    value = _eval(runtime, "empty or name")
    assert base._portapy_value_get_kind_impl(runtime, value) == base.PORTAPY_VALUE_STRING
    assert _data(runtime, value) == b"Somnia"
    assert base._portapy_value_release_impl(runtime, value) == base.PORTAPY_OK

    value = _eval(runtime, "name and answer")
    assert base._portapy_value_get_kind_impl(runtime, value) == base.PORTAPY_VALUE_INT
    assert base._portapy_value_as_i64_impl(runtime, value) == 42
    assert base._portapy_value_release_impl(runtime, value) == base.PORTAPY_OK

    value = _eval(runtime, "zero and name")
    assert base._portapy_value_get_kind_impl(runtime, value) == base.PORTAPY_VALUE_INT
    assert base._portapy_value_as_i64_impl(runtime, value) == 0
    assert base._portapy_value_release_impl(runtime, value) == base.PORTAPY_OK

    assert _bool(runtime, "not empty")
    assert _bool(runtime, "not (answer < 40)")
    assert _bool(runtime, "answer > 40 and name == \"Somnia\"")
    assert _bool(runtime, "zero or answer == 42")


def test_boolean_assignments_persist_typed_results() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = (
        'name = "Somnia"\n'
        'correct = name == "Somnia"\n'
        'selected = "" or name\n'
        'guarded = name and 42\n'
    )
    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK

    correct = api._portapy_get_global_span_impl(runtime, "correct", len("correct"))
    assert base._portapy_value_as_bool_impl(runtime, correct) == 1

    selected = api._portapy_get_global_span_impl(runtime, "selected", len("selected"))
    assert _data(runtime, selected) == b"Somnia"

    guarded = api._portapy_get_global_span_impl(runtime, "guarded", len("guarded"))
    assert base._portapy_value_as_i64_impl(runtime, guarded) == 42


def test_invalid_ordering_reports_type_error() -> None:
    runtime = api._portapy_runtime_create_impl()
    expression = '"text" < 4'
    assert api._portapy_eval_span_impl(runtime, expression, len(expression)) == 0
    assert base._portapy_error_status_impl(runtime) == base.PORTAPY_TYPE_ERROR
    assert base._portapy_error_type_size_impl(runtime) == len("TypeError")
