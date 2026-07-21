from __future__ import annotations

import builtins

from portapy.core.portable_frontend import compile_portable_source
from portapy.core.vm import VirtualMachine


def run_source(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__builtins__": builtins.__dict__}
    VirtualMachine().run(compile_portable_source(source), namespace)
    return namespace


def test_property_setter_staticmethod_and_classmethod_execute() -> None:
    namespace = run_source(
        "class Box:\n"
        "    def __init__(self, value):\n"
        "        self._value = value\n"
        "    @property\n"
        "    def value(self):\n"
        "        return self._value\n"
        "    @value.setter\n"
        "    def value(self, next_value):\n"
        "        self._value = next_value\n"
        "    @staticmethod\n"
        "    def combine(left, right):\n"
        "        return left + right\n"
        "    @classmethod\n"
        "    def make(cls, value):\n"
        "        return cls(value)\n"
        "box = Box.make(20)\n"
        "box.value = Box.combine(box.value, 22)\n"
        "answer = box.value\n"
    )
    assert namespace["answer"] == 42


def test_custom_data_descriptor_get_and_set_execute() -> None:
    namespace = run_source(
        "class OffsetDescriptor:\n"
        "    def __get__(self, instance, owner):\n"
        "        return instance._stored + 1\n"
        "    def __set__(self, instance, value):\n"
        "        instance._stored = value - 1\n"
        "class Holder:\n"
        "    value = OffsetDescriptor()\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "holder = Holder(42)\n"
        "answer = holder.value\n"
        "stored = holder._stored\n"
    )
    assert namespace["answer"] == 42
    assert namespace["stored"] == 41
