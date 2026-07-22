"""Runtime entrypoint for PortaPy's Python-authored virtual machine.

The implementation lives in :mod:`portapy.core.vm_impl`; this module owns the
small amount of top-level runtime setup shared by hosted and native callers.
"""
from __future__ import annotations

from .bytecode import CodeObject
from .vm_impl import (
    AsyncGeneratorObject,
    CoroutineObject,
    Frame,
    GeneratorObject,
    VMError,
    VirtualMachine as _VirtualMachine,
)


class VirtualMachine(_VirtualMachine):
    """VM entrypoint that mirrors Python's automatic builtin injection."""

    def _seed_builtins(self, namespace: dict[str, object]) -> None:
        namespace.setdefault("print", print)
        namespace.setdefault("len", len)
        namespace.setdefault("range", range)
        namespace.setdefault("str", str)
        namespace.setdefault("int", int)
        namespace.setdefault("float", float)
        namespace.setdefault("bool", bool)
        namespace.setdefault("list", list)
        namespace.setdefault("dict", dict)
        namespace.setdefault("tuple", tuple)
        namespace.setdefault("set", set)
        namespace.setdefault("bytes", bytes)
        namespace.setdefault("bytearray", bytearray)
        namespace.setdefault("object", object)
        namespace.setdefault("type", type)
        namespace.setdefault("slice", slice)
        namespace.setdefault("property", property)
        namespace.setdefault("classmethod", classmethod)
        namespace.setdefault("staticmethod", staticmethod)
        namespace.setdefault("abs", abs)
        namespace.setdefault("min", min)
        namespace.setdefault("max", max)
        namespace.setdefault("sum", sum)
        namespace.setdefault("sorted", sorted)
        namespace.setdefault("enumerate", enumerate)
        namespace.setdefault("zip", zip)
        namespace.setdefault("map", map)
        namespace.setdefault("filter", filter)
        namespace.setdefault("isinstance", isinstance)
        namespace.setdefault("issubclass", issubclass)
        namespace.setdefault("hasattr", hasattr)
        namespace.setdefault("getattr", getattr)
        namespace.setdefault("setattr", setattr)
        namespace.setdefault("delattr", delattr)
        namespace.setdefault("callable", callable)
        namespace.setdefault("iter", iter)
        namespace.setdefault("next", next)
        namespace.setdefault("reversed", reversed)
        namespace.setdefault("round", round)
        namespace.setdefault("pow", pow)
        namespace.setdefault("divmod", divmod)
        namespace.setdefault("all", all)
        namespace.setdefault("any", any)
        namespace.setdefault("repr", repr)
        namespace.setdefault("ascii", ascii)
        namespace.setdefault("format", format)
        namespace.setdefault("chr", chr)
        namespace.setdefault("ord", ord)
        namespace.setdefault("hash", hash)
        namespace.setdefault("id", id)
        namespace.setdefault("Exception", Exception)
        namespace.setdefault("BaseException", BaseException)
        namespace.setdefault("NameError", NameError)
        namespace.setdefault("TypeError", TypeError)
        namespace.setdefault("ValueError", ValueError)
        namespace.setdefault("RuntimeError", RuntimeError)
        namespace.setdefault("AttributeError", AttributeError)
        namespace.setdefault("KeyError", KeyError)
        namespace.setdefault("IndexError", IndexError)
        namespace.setdefault("StopIteration", StopIteration)
        namespace.setdefault("StopAsyncIteration", StopAsyncIteration)
        namespace.setdefault("ZeroDivisionError", ZeroDivisionError)
        namespace.setdefault("OverflowError", OverflowError)
        namespace.setdefault("ArithmeticError", ArithmeticError)
        namespace.setdefault("LookupError", LookupError)
        namespace.setdefault("UnboundLocalError", UnboundLocalError)
        namespace.setdefault("NotImplementedError", NotImplementedError)
        namespace.setdefault("OSError", OSError)
        namespace.setdefault("IOError", IOError)
        namespace.setdefault("ImportError", ImportError)
        namespace.setdefault("ModuleNotFoundError", ModuleNotFoundError)
        namespace.setdefault("AssertionError", AssertionError)
        namespace.setdefault("GeneratorExit", GeneratorExit)

    def run(self, code: CodeObject, globals_: dict[str, object] | None = None) -> object:
        namespace = globals_ if globals_ is not None else {}
        self._seed_builtins(namespace)
        return super().run(code, namespace)


__all__ = [
    "AsyncGeneratorObject",
    "CoroutineObject",
    "Frame",
    "GeneratorObject",
    "VMError",
    "VirtualMachine",
]
