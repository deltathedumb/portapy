from __future__ import annotations

import importlib
from pathlib import Path
import sys

import portapy
import pytest

from tools.audit_standalone_generated_entry import generate


_GENERATED_NAMES = (
    "portapy._audit_scalar_linux",
    "portapy._audit_expression_linux",
    "portapy._audit_control_linux",
    "portapy._audit_function_linux",
    "portapy._audit_host_linux",
    "portapy._audit_entry_linux",
)


@pytest.fixture
def generated_runtime(tmp_path: Path):
    generate("linux", tmp_path)
    package_path = str(tmp_path)
    portapy.__path__.append(package_path)
    importlib.invalidate_caches()
    try:
        module = importlib.import_module("portapy._audit_entry_linux")
        yield module
    finally:
        for name in _GENERATED_NAMES:
            sys.modules.pop(name, None)
        if package_path in portapy.__path__:
            portapy.__path__.remove(package_path)
        importlib.invalidate_caches()


def evaluate_i64(module, runtime: int, expression: str) -> int:
    handle = module._portapy_eval_span_impl(runtime, expression, len(expression))
    assert handle != 0
    assert module._portapy_last_status_impl() == module.PORTAPY_OK
    value = module._portapy_value_as_i64_impl(runtime, handle)
    assert module._portapy_last_status_impl() == module.PORTAPY_OK
    assert module._portapy_value_release_impl(runtime, handle) == module.PORTAPY_OK
    return value


def test_generated_runtime_executes_persistent_full_vm_state(generated_runtime) -> None:
    module = generated_runtime
    runtime = module._portapy_runtime_create_impl()
    assert runtime != 0
    source = (
        "class Counter:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "    def step(self):\n"
        "        self.value += 1\n"
        "        return self.value\n"
        "def make_offset(offset):\n"
        "    def apply(value):\n"
        "        return value + offset\n"
        "    return apply\n"
        "counter = Counter(40)\n"
        "offset = make_offset(1)\n"
        "values = [offset(value) for value in [19, 20, 21] if value >= 20]\n"
        "answer = counter.step() + values[0] - 20\n"
    )
    assert module._portapy_exec_span_impl(runtime, source, len(source)) == module.PORTAPY_OK
    assert evaluate_i64(module, runtime, "answer") == 42
    followup = "answer = counter.step()\n"
    assert module._portapy_exec_span_impl(runtime, followup, len(followup)) == module.PORTAPY_OK
    assert evaluate_i64(module, runtime, "answer") == 42
    assert module._portapy_runtime_destroy_impl(runtime) == module.PORTAPY_OK


def test_generated_runtime_round_trips_public_containers(generated_runtime) -> None:
    module = generated_runtime
    runtime = module._portapy_runtime_create_impl()
    source = (
        "items = [20, 21]\n"
        "mapping = {'left': items[0], 'right': items[1]}\n"
        "pair = (mapping['left'], mapping['right'])\n"
        "answer = pair[0] + pair[1] + 1\n"
    )
    assert module._portapy_exec_span_impl(runtime, source, len(source)) == module.PORTAPY_OK
    assert evaluate_i64(module, runtime, "answer") == 42
    handle = module._portapy_get_global_span_impl(runtime, "items", 5)
    assert handle != 0
    assert module._portapy_value_get_kind_impl(runtime, handle) == module.PORTAPY_VALUE_LIST
    assert module._portapy_value_release_impl(runtime, handle) == module.PORTAPY_OK
    assert module._portapy_runtime_destroy_impl(runtime) == module.PORTAPY_OK


def test_generated_runtime_dispatches_existing_host_callback_protocol(generated_runtime) -> None:
    module = generated_runtime
    runtime = module._portapy_runtime_create_impl()
    callable_handle = module._portapy_value_from_host_callable_impl(runtime, 77)
    assert callable_handle != 0
    assert module._bind_global(runtime, "host_offset", callable_handle) == module.PORTAPY_OK

    def dispatch(active_runtime: int, callable_id: int) -> int:
        assert active_runtime == runtime
        assert callable_id == 77
        assert module._portapy_host_pending_arg_count_impl(runtime) == 1
        argument = module._portapy_host_pending_arg_impl(runtime, 0)
        value = module._portapy_value_as_i64_impl(runtime, argument)
        result = module._portapy_value_from_i64_impl(runtime, value + 2)
        return module._portapy_host_dispatch_complete_impl(
            runtime,
            module.PORTAPY_OK,
            result,
        )

    module._portapy_host_dispatch_impl = dispatch
    source = "answer = host_offset(40)\n"
    assert module._portapy_exec_span_impl(runtime, source, len(source)) == module.PORTAPY_OK
    assert evaluate_i64(module, runtime, "answer") == 42
    assert module._portapy_runtime_destroy_impl(runtime) == module.PORTAPY_OK


def test_generated_runtime_publishes_portable_traceback_frames(generated_runtime) -> None:
    module = generated_runtime
    runtime = module._portapy_runtime_create_impl()
    source = (
        "def inner():\n"
        "    return missing_name\n"
        "def outer():\n"
        "    return inner()\n"
        "outer()\n"
    )
    status = module._portapy_exec_span_impl(runtime, source, len(source))
    assert status == module.PORTAPY_RUNTIME_ERROR
    assert module._portapy_traceback_count_impl(runtime) == 3
    assert module._portapy_traceback_function_size_impl(runtime, 0) == len("<module>")
    assert module._portapy_traceback_function_size_impl(runtime, 1) == len("outer")
    assert module._portapy_traceback_function_size_impl(runtime, 2) == len("inner")
    assert module._portapy_runtime_destroy_impl(runtime) == module.PORTAPY_OK
