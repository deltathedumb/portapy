from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_control as api


def _global(runtime: int, name: str) -> int:
    value = api._portapy_get_global_span_impl(runtime, name, len(name))
    assert value != 0, name
    return value


def _data(runtime: int, value: int) -> bytes:
    size = base._portapy_value_get_size_impl(runtime, value)
    assert base._portapy_last_status_impl() == base.PORTAPY_OK
    return bytes(base._portapy_value_get_byte_impl(runtime, value, index) for index in range(size))


def test_if_else_and_nested_blocks_execute_by_indentation() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = (
        'name = "Somnia"\n'
        'result = "unset"\n'
        'if name == "Somnia":\n'
        '    result = "matched"\n'
        '    if 2 < 3:\n'
        '        nested = True\n'
        'else:\n'
        '    result = "wrong"\n'
    )

    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
    assert _data(runtime, _global(runtime, "result")) == b"matched"
    assert base._portapy_value_as_bool_impl(runtime, _global(runtime, "nested")) == 1


def test_false_if_runs_else_and_pass_is_valid() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = (
        'value = 0\n'
        'if value:\n'
        '    pass\n'
        '    chosen = "if"\n'
        'else:\n'
        '    chosen = "else"\n'
    )

    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
    assert _data(runtime, _global(runtime, "chosen")) == b"else"


def test_while_break_and_continue_update_globals() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = (
        'count = 0\n'
        'total = 0\n'
        'while count < 6:\n'
        '    count = count + 1\n'
        '    if count == 2:\n'
        '        continue\n'
        '    if count == 5:\n'
        '        break\n'
        '    total = total + count\n'
        'finished = count == 5 and total == 8\n'
    )

    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
    assert base._portapy_value_as_i64_impl(runtime, _global(runtime, "count")) == 5
    assert base._portapy_value_as_i64_impl(runtime, _global(runtime, "total")) == 8
    assert base._portapy_value_as_bool_impl(runtime, _global(runtime, "finished")) == 1


def test_expression_statements_are_evaluated_and_released() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = 'answer = 42\nanswer == 42\n"unused"\n'
    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
    assert base._portapy_value_as_i64_impl(runtime, _global(runtime, "answer")) == 42


def test_invalid_indentation_and_loop_control_report_syntax_errors() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = 'value = 1\n  unexpected = 2\n'
    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_COMPILE_ERROR
    assert base._portapy_error_status_impl(runtime) == base.PORTAPY_COMPILE_ERROR
    assert base._portapy_error_line_impl(runtime) == 2

    runtime = api._portapy_runtime_create_impl()
    source = 'break\n'
    assert api._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_COMPILE_ERROR
    assert base._portapy_error_status_impl(runtime) == base.PORTAPY_COMPILE_ERROR
