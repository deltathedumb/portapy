from __future__ import annotations

from portapy import native_full_runtime_entry as entry
from portapy import native_vm_bridge as bridge
from portapy.native_api import PORTAPY_OK, _portapy_value_as_i64_impl


def test_final_native_entry_binds_execution_to_full_vm_bridge() -> None:
    assert entry._portapy_runtime_create_impl is bridge._portapy_runtime_create_impl
    assert entry._portapy_runtime_destroy_impl is bridge._portapy_runtime_destroy_impl
    assert entry._portapy_exec_span_impl is bridge._portapy_exec_span_impl
    assert entry._portapy_eval_span_impl is bridge._portapy_eval_span_impl


def test_final_native_entry_executes_and_evaluates_statefully() -> None:
    runtime = entry._portapy_runtime_create_impl()
    source = (
        "class Value:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "instance = Value(40)\n"
    )
    assert entry._portapy_exec_span_impl(runtime, source, len(source)) == PORTAPY_OK
    expression = "instance.value + 2"
    result = entry._portapy_eval_span_impl(runtime, expression, len(expression))
    assert _portapy_value_as_i64_impl(runtime, result) == 42
    assert entry._portapy_runtime_destroy_impl(runtime) == PORTAPY_OK
