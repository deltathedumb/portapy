from __future__ import annotations
from .native_full_reference_entry import (
    PORTAPY_OK,
    PORTAPY_VALUE_INT,
    _portapy_dict_begin_impl,
    _portapy_dict_get_item_span_impl,
    _portapy_dict_set_span_impl,
    _portapy_list_begin_impl,
    _portapy_list_finish_impl,
    _portapy_list_get_size_impl,
    _portapy_list_initialize_item_impl,
    _portapy_tuple_begin_impl,
    _portapy_tuple_finish_impl,
    _portapy_tuple_get_size_impl,
    _portapy_tuple_set_item_impl,
    _portapy_exec_span_impl,
    _portapy_get_global_span_impl,
    _portapy_runtime_create_impl,
    _portapy_runtime_destroy_impl,
    _portapy_set_global_span_impl,
    _portapy_value_as_i64_impl,
    _portapy_value_from_i64_impl,
    _portapy_value_get_kind_impl,
    _runtime,
)
from .reference_api import Status


class _ProbeModule:
    def __init__(self) -> None:
        self.value = 42


def _probe_import(name: str) -> object:
    return _ProbeModule()


def portapy_abi_version() -> int:
    return 1


def portapy_full_core_parse_probe() -> int:
    runtime = _portapy_runtime_create_impl()
    source = "answer = 1\n"
    status = _portapy_exec_span_impl(runtime, source, len(source))
    _portapy_runtime_destroy_impl(runtime)
    if status != PORTAPY_OK:
        return -1
    return 1


def portapy_full_core_probe() -> int:
    runtime = _portapy_runtime_create_impl()
    instance = _runtime(runtime)
    if instance is None:
        return -6
    if instance.set_global("__pyinbin_import__", _probe_import) is not Status.OK:
        return -7
    forty = _portapy_value_from_i64_impl(runtime, 40)
    two = _portapy_value_from_i64_impl(runtime, 2)
    values = _portapy_list_begin_impl(runtime, 2)
    _portapy_list_initialize_item_impl(runtime, values, 0, forty)
    _portapy_list_initialize_item_impl(runtime, values, 1, two)
    _portapy_list_finish_impl(runtime, values)
    _portapy_set_global_span_impl(runtime, "values", 6, values)
    source = """def total(items):
    answer = 0
    for item in items:
        answer += item
    return answer
def outer(base):
    def inner(value):
        return base + value
    return inner
class Box:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
fn = outer(base=19)
box = Box(value=fn(value=total(items=values) - 19))
import probe
def fail():
    return 1 // 0
try:
    fail()
except Exception as exc:
    traced = exc.__traceback__ is not None
answer = box.get() + probe.value - 42 if traced else -1
"""
    status = _portapy_exec_span_impl(runtime, source, len(source))
    if status != PORTAPY_OK:
        print("FULL CORE PROBE ERROR", instance.last_error())
        return -1
    handle = _portapy_get_global_span_impl(runtime, "answer", 6)
    if _portapy_value_get_kind_impl(runtime, handle) != PORTAPY_VALUE_INT:
        return -2
    answer = _portapy_value_as_i64_impl(runtime, handle)
    if _portapy_list_get_size_impl(runtime, values) != 2:
        return -3
    pair = _portapy_tuple_begin_impl(runtime, 2)
    _portapy_tuple_set_item_impl(runtime, pair, 0, forty)
    _portapy_tuple_set_item_impl(runtime, pair, 1, two)
    _portapy_tuple_finish_impl(runtime, pair)
    if _portapy_tuple_get_size_impl(runtime, pair) != 2:
        return -4
    mapping = _portapy_dict_begin_impl(runtime)
    _portapy_dict_set_span_impl(runtime, mapping, "answer", 6, handle)
    mapped = _portapy_dict_get_item_span_impl(runtime, mapping, "answer", 6)
    if _portapy_value_as_i64_impl(runtime, mapped) != 42:
        return -5
    _portapy_runtime_destroy_impl(runtime)
    return answer
