"""Exercise the full Runtime through native ABI implementation functions."""
from __future__ import annotations

from .native_full_reference_entry import (
    _portapy_exec_span_impl,
    _portapy_get_global_span_impl,
    _portapy_runtime_create_impl,
    _portapy_runtime_destroy_impl,
    _portapy_value_as_i64_impl,
)


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_probe() -> int:
    runtime = _portapy_runtime_create_impl()
    source = """def outer():
    value = 40
    def inner():
        return value + 2
    return inner()

class Box:
    def __init__(self, value):
        self.value = value

answer = Box(outer()).value
"""
    status = _portapy_exec_span_impl(runtime, source, len(source))
    if status != 0:
        return -1
    handle = _portapy_get_global_span_impl(runtime, "answer", 6)
    if handle == 0:
        return -2
    answer = _portapy_value_as_i64_impl(runtime, handle)
    _portapy_runtime_destroy_impl(runtime)
    return answer
