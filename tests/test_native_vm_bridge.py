from __future__ import annotations

import portapy.native_api_host_calls as host_calls
from portapy.native_api import (
    PORTAPY_OK,
    _portapy_error_status_impl,
    _portapy_get_global_span_impl,
    _portapy_value_as_i64_impl,
    _portapy_value_from_i64_impl,
)
from portapy.native_api_host import (
    _portapy_host_set_attr_span_impl,
    _portapy_set_global_span_impl,
    _portapy_value_from_host_object_impl,
)
from portapy.native_api_host_calls import _portapy_value_from_host_callable_impl
from portapy.native_vm_bridge import (
    _portapy_eval_span_impl,
    _portapy_exec_span_impl,
    _portapy_runtime_create_impl,
    _portapy_runtime_destroy_impl,
)


def execute(runtime: int, source: str) -> int:
    return _portapy_exec_span_impl(runtime, source, len(source))


def evaluate_i64(runtime: int, source: str) -> int:
    handle = _portapy_eval_span_impl(runtime, source, len(source))
    assert handle != 0
    return _portapy_value_as_i64_impl(runtime, handle)


def test_bridge_executes_full_syntax_and_preserves_vm_state() -> None:
    runtime = _portapy_runtime_create_impl()
    assert execute(
        runtime,
        "class Counter:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "    def step(self):\n"
        "        self.value += 1\n"
        "        return self.value\n"
        "counter = Counter(40)\n",
    ) == PORTAPY_OK
    assert execute(runtime, "first = counter.step()\nsecond = counter.step()\n") == PORTAPY_OK
    assert evaluate_i64(runtime, "first + second - 41") == 42
    assert _portapy_runtime_destroy_impl(runtime) == PORTAPY_OK


def test_bridge_imports_existing_native_scalar_globals() -> None:
    runtime = _portapy_runtime_create_impl()
    value = _portapy_value_from_i64_impl(runtime, 40)
    assert _portapy_set_global_span_impl(runtime, "offset", 6, value) == PORTAPY_OK
    assert execute(runtime, "answer = offset + 2\n") == PORTAPY_OK
    answer = _portapy_get_global_span_impl(runtime, "answer", 6)
    assert _portapy_value_as_i64_impl(runtime, answer) == 42
    assert _portapy_runtime_destroy_impl(runtime) == PORTAPY_OK


def test_bridge_exposes_registered_host_object_attributes() -> None:
    runtime = _portapy_runtime_create_impl()
    module = _portapy_value_from_host_object_impl(runtime, 1001)
    value = _portapy_value_from_i64_impl(runtime, 40)
    assert _portapy_host_set_attr_span_impl(runtime, module, "value", 5, value) == PORTAPY_OK
    assert _portapy_set_global_span_impl(runtime, "module", 6, module) == PORTAPY_OK
    assert execute(runtime, "answer = module.value + 2\n") == PORTAPY_OK
    assert evaluate_i64(runtime, "answer") == 42
    assert _portapy_runtime_destroy_impl(runtime) == PORTAPY_OK


def test_bridge_dispatches_registered_host_callable(monkeypatch) -> None:
    runtime = _portapy_runtime_create_impl()

    def dispatch(active_runtime: int, callable_id: int) -> int:
        assert active_runtime == runtime
        assert callable_id == 77
        assert host_calls._portapy_host_pending_arg_count_impl(runtime) == 1
        argument = host_calls._portapy_host_pending_arg_impl(runtime, 0)
        value = _portapy_value_as_i64_impl(runtime, argument)
        return _portapy_value_from_i64_impl(runtime, value + 2)

    monkeypatch.setattr(host_calls, "_portapy_host_dispatch_impl", dispatch)
    callable_value = _portapy_value_from_host_callable_impl(runtime, 77)
    assert _portapy_set_global_span_impl(
        runtime,
        "host_offset",
        len("host_offset"),
        callable_value,
    ) == PORTAPY_OK
    assert execute(runtime, "answer = host_offset(40)\n") == PORTAPY_OK
    assert evaluate_i64(runtime, "answer") == 42
    assert _portapy_runtime_destroy_impl(runtime) == PORTAPY_OK


def test_bridge_reports_compile_and_runtime_errors() -> None:
    runtime = _portapy_runtime_create_impl()
    assert execute(runtime, "if:\n") != PORTAPY_OK
    assert _portapy_error_status_impl(runtime) != PORTAPY_OK
    assert execute(runtime, "answer = 1 // 0\n") != PORTAPY_OK
    assert _portapy_error_status_impl(runtime) != PORTAPY_OK
    assert _portapy_runtime_destroy_impl(runtime) == PORTAPY_OK
