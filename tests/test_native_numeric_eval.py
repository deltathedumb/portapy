from __future__ import annotations

from portapy import native_api as api


def _evaluate(runtime: int, source: str) -> int:
    handle = api._portapy_eval_span_impl(runtime, source, len(source))
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
        assert api._portapy_eval_span_impl(runtime, source, len(source)) == 0
        assert api._portapy_last_status_impl() == api.PORTAPY_COMPILE_ERROR


def test_explicit_length_rejects_embedded_nul_tail() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = "1\x00+2"
    assert api._portapy_eval_span_impl(runtime, source, len(source)) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_COMPILE_ERROR


def test_division_by_zero_is_runtime_error() -> None:
    runtime = api._portapy_runtime_create_impl()
    source = "5 // (3 - 3)"
    assert api._portapy_eval_span_impl(runtime, source, len(source)) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_RUNTIME_ERROR
    source = "5 % 0"
    assert api._portapy_eval_span_impl(runtime, source, len(source)) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_RUNTIME_ERROR


def test_invalid_runtime_is_rejected() -> None:
    source = "1 + 1"
    assert api._portapy_eval_span_impl(0, source, len(source)) == 0
    assert api._portapy_last_status_impl() == api.PORTAPY_INVALID_HANDLE
