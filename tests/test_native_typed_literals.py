from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_typed as api


def _data(runtime: int, value: int) -> bytes:
    size = base._portapy_value_get_size_impl(runtime, value)
    assert base._portapy_last_status_impl() == base.PORTAPY_OK
    return bytes(base._portapy_value_get_byte_impl(runtime, value, index) for index in range(size))


def _global(runtime: int, name: str) -> int:
    value = api._portapy_get_global_span_impl(runtime, name, len(name))
    assert value != 0
    return value


def test_typed_assignment_block_and_global_aliases() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = (
        "nothing = None\n"
        "flag = True\n"
        "disabled = False\n"
        'name = "Somnia"\n'
        'payload = b"\\x00\\xffA"\n'
        "alias = name\n"
        "answer = 40 + 2\n"
    )

    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK

    nothing = _global(runtime, "nothing")
    assert base._portapy_value_get_kind_impl(runtime, nothing) == base.PORTAPY_VALUE_NONE

    flag = _global(runtime, "flag")
    assert base._portapy_value_get_kind_impl(runtime, flag) == base.PORTAPY_VALUE_BOOL
    assert base._portapy_value_as_bool_impl(runtime, flag) == 1

    disabled = _global(runtime, "disabled")
    assert base._portapy_value_as_bool_impl(runtime, disabled) == 0

    name = _global(runtime, "name")
    assert base._portapy_value_get_kind_impl(runtime, name) == base.PORTAPY_VALUE_STRING
    assert _data(runtime, name) == b"Somnia"

    payload = _global(runtime, "payload")
    assert base._portapy_value_get_kind_impl(runtime, payload) == base.PORTAPY_VALUE_BYTES
    assert _data(runtime, payload) == b"\x00\xffA"

    alias = _global(runtime, "alias")
    assert base._portapy_value_get_kind_impl(runtime, alias) == base.PORTAPY_VALUE_STRING
    assert _data(runtime, alias) == b"Somnia"

    answer = _global(runtime, "answer")
    assert base._portapy_value_as_i64_impl(runtime, answer) == 42


def test_typed_eval_returns_native_value_handles() -> None:
    runtime = api._portapy_runtime_create_impl()

    value = api._portapy_eval_span_impl(runtime, '"hello\\nworld"', len('"hello\\nworld"'))
    assert base._portapy_value_get_kind_impl(runtime, value) == base.PORTAPY_VALUE_STRING
    assert _data(runtime, value) == b"hello\nworld"

    value = api._portapy_eval_span_impl(runtime, "False", len("False"))
    assert base._portapy_value_get_kind_impl(runtime, value) == base.PORTAPY_VALUE_BOOL
    assert base._portapy_value_as_bool_impl(runtime, value) == 0

    value = api._portapy_eval_span_impl(runtime, "6 * 7", len("6 * 7"))
    assert base._portapy_value_get_kind_impl(runtime, value) == base.PORTAPY_VALUE_INT
    assert base._portapy_value_as_i64_impl(runtime, value) == 42


def test_semicolons_and_comments_inside_literals_are_not_statement_boundaries() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = 'text = "a;b#c"; other = b"x;y#z" # trailing comment\n'

    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
    assert _data(runtime, _global(runtime, "text")) == b"a;b#c"
    assert _data(runtime, _global(runtime, "other")) == b"x;y#z"


def test_invalid_literal_reports_syntax_error() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = 'broken = "unterminated'

    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_COMPILE_ERROR
    assert base._portapy_error_status_impl(runtime) == base.PORTAPY_COMPILE_ERROR
    assert base._portapy_error_line_impl(runtime) == 1
