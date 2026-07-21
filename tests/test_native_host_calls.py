from __future__ import annotations

from portapy import native_api as base
from portapy import native_api_host_calls as calls


def _runtime() -> int:
    runtime = calls._portapy_runtime_create_impl()
    assert runtime != 0
    return runtime


def _install_sum_dispatch():
    original = calls._portapy_host_dispatch_impl

    def dispatch(runtime: int, callable_id: int) -> int:
        assert callable_id == 9001
        count = calls._portapy_host_pending_arg_count_impl(runtime)
        assert calls._portapy_last_status_impl() == base.PORTAPY_OK
        total = 0
        for index in range(count):
            argument = calls._portapy_host_pending_arg_impl(runtime, index)
            assert argument != 0
            total += calls._portapy_value_as_i64_impl(runtime, argument)
            assert calls._portapy_last_status_impl() == base.PORTAPY_OK
        result = calls._portapy_value_from_i64_impl(runtime, total)
        assert result != 0
        return calls._portapy_host_dispatch_complete_impl(
            runtime,
            base.PORTAPY_OK,
            result,
        )

    calls._portapy_host_dispatch_impl = dispatch
    return original


def _callable(runtime: int, callable_id: int = 9001) -> int:
    value = calls._portapy_value_from_host_callable_impl(runtime, callable_id)
    assert value != 0
    assert calls._portapy_value_get_host_callable_id_impl(runtime, value) == callable_id
    return value


def test_dotted_host_callable_executes_synchronously() -> None:
    runtime = _runtime()
    module = calls._portapy_value_from_host_object_impl(runtime, 100)
    add = _callable(runtime)
    assert (
        calls._portapy_host_set_attr_span_impl(
            runtime,
            module,
            "add",
            len("add"),
            add,
        )
        == base.PORTAPY_OK
    )
    assert (
        calls._portapy_set_global_span_impl(
            runtime,
            "math",
            len("math"),
            module,
        )
        == base.PORTAPY_OK
    )

    original = _install_sum_dispatch()
    try:
        source = "answer = math.add(20, 22)\n"
        assert calls._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
        answer = calls._portapy_get_global_span_impl(runtime, "answer", len("answer"))
        assert calls._portapy_value_as_i64_impl(runtime, answer) == 42
    finally:
        calls._portapy_host_dispatch_impl = original


def test_flattened_host_callable_and_nested_calls() -> None:
    runtime = _runtime()
    add = _callable(runtime)
    assert (
        calls._portapy_set_global_span_impl(runtime, "add", len("add"), add)
        == base.PORTAPY_OK
    )

    original = _install_sum_dispatch()
    try:
        expression = "add(20, add(1, 21))"
        result = calls._portapy_eval_span_impl(runtime, expression, len(expression))
        assert result != 0
        assert calls._portapy_value_as_i64_impl(runtime, result) == 42
    finally:
        calls._portapy_host_dispatch_impl = original


def test_host_callback_failure_becomes_structured_error() -> None:
    runtime = _runtime()
    add = _callable(runtime)
    assert (
        calls._portapy_set_global_span_impl(runtime, "add", len("add"), add)
        == base.PORTAPY_OK
    )
    original = calls._portapy_host_dispatch_impl

    def fail(runtime: int, callable_id: int) -> int:
        assert callable_id == 9001
        return calls._portapy_host_dispatch_complete_impl(
            runtime,
            base.PORTAPY_TYPE_ERROR,
            0,
        )

    calls._portapy_host_dispatch_impl = fail
    try:
        result = calls._portapy_eval_span_impl(runtime, "add(1)", len("add(1)"))
        assert result == 0
        assert calls._portapy_last_status_impl() == base.PORTAPY_TYPE_ERROR
        assert calls._portapy_error_type_size_impl(runtime) == len("HostCallError")
    finally:
        calls._portapy_host_dispatch_impl = original


def test_non_host_call_source_still_uses_native_functions() -> None:
    runtime = _runtime()
    source = (
        "def add(left, right):\n"
        "    return left + right\n"
        "answer = add(20, 22)\n"
    )
    assert calls._portapy_exec_span_impl(runtime, source, len(source)) == base.PORTAPY_OK
    answer = calls._portapy_eval_span_impl(runtime, "answer", len("answer"))
    assert calls._portapy_value_as_i64_impl(runtime, answer) == 42
