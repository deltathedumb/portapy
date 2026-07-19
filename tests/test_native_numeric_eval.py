from __future__ import annotations

from portapy import native_api as api


def _evaluate(runtime: int, source: str) -> int:
    handle = api._portapy_eval_cstr_impl(runtime, source)
    if handle == 0:
        return 0
    return api._portapy_value_as_i64_impl(runtime, handle)


def test_integer_expression_precedence_and_parentheses() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _evaluate(runtime, "1 + 2 * 3") == 7
    assert _evaluate(runtime, "(1 + 2) * 3") == 9
    assert _evaluate(runtime, "20 // 3 + 20 % 3") == 8
    assert _evaluate(runtime, " -(-5 + 2) * +4 ") == 12
    assert api._portapy_last_status_impl() == api.PORTAPY_OK


def test_integer_division_matches_python_flooring() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert _evaluate(runtime, "-7 // 3") == -3
    assert _evaluate(runtime, "-7 % 3") == 2
    assert _evaluate(runtime, "7 // -3") == -3
    assert _evaluate(runtime, "7 % -3") == -2


def test_invalid_syntax_is_compile_error() -> None:
    runtime = api._portapy_runtime_create_impl()
    for source in ("", "1 +", "(1 + 2", "1 2", "1 / 2", "hello", "2 ** 3"):
        assert api._portapy_eval_cstr_impl(runtime, source) == 0
        assert api._portapy_last_status_impl() == api.PORTAPY_COMPILE_ERROR


def test_division_by_zero_is_runtime_error() -> None:
    runtime = api._portapy_runtime_create_impl()
    assert api._portapy_eval_cstr_impl(runtime, "5 // (3 - 3)") == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_RUNTIME_ERROR
    assert api._portapy_eval_cstr_impl(runtime, "5 % 0") == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_RUNTIME_ERROR


def test_invalid_runtime_is_rejected() -> None:
    assert api._portapy_eval_cstr_impl(0, "1 + 1") == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_HANDLE
