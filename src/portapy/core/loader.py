"""Controlled builtin namespace for standalone PortaPy execution.

Builtins are explicit values in each VM global namespace rather than an ambient
host lookup.  This keeps embedded runtimes deterministic and lets Somnia apply
its own import/filesystem policy at the runtime boundary.
"""
from __future__ import annotations

from .vm import VMError


def _builtin_print(*values: object) -> None:
    count = len(values)
    if count == 0:
        print()
    elif count == 1:
        print(values[0])
    elif count == 2:
        print(values[0], values[1])
    elif count == 3:
        print(values[0], values[1], values[2])
    else:
        print(values)


def _builtin_len(value: object) -> int:
    return len(value)


def _builtin_sum(values: object, start: object = 0) -> object:
    return sum(values, start)


def _builtin_range(*values: int) -> object:
    if len(values) == 1:
        return range(values[0])
    if len(values) == 2:
        return range(values[0], values[1])
    if len(values) == 3:
        return range(values[0], values[1], values[2])
    raise TypeError("range expected 1 to 3 arguments")


def _builtin_repr(value: object) -> str:
    return repr(value)


def _builtin_getattr(value: object, name: str, default: object = None) -> object:
    if default is None:
        return getattr(value, name)
    return getattr(value, name, default)


def _builtin_setattr(value: object, name: str, item: object) -> None:
    setattr(value, name, item)


def _builtin_hasattr(value: object, name: str) -> bool:
    return hasattr(value, name)


def _builtin_isinstance(value: object, expected: object) -> bool:
    try:
        return isinstance(value, expected)
    except TypeError:
        return False


def _builtin_issubclass(value: object, expected: object) -> bool:
    try:
        return issubclass(value, expected)
    except TypeError:
        return False


def _builtin_any(values: object) -> bool:
    return any(values)


def _builtin_all(values: object) -> bool:
    return all(values)


def _builtin_abs(value: object) -> object:
    return abs(value)


def _builtin_round(value: object, digits: int | None = None) -> object:
    if digits is None:
        return round(value)
    return round(value, digits)


def _builtin_pow(left: object, right: object, modulus: object = None) -> object:
    if modulus is None:
        return pow(left, right)
    return pow(left, right, modulus)


def _builtin_sorted(values: object) -> object:
    return sorted(values)


def _builtin_reversed(values: object) -> object:
    return reversed(values)


def _builtin_iter(value: object) -> object:
    return iter(value)


def _builtin_next(value: object, default: object = None) -> object:
    if default is None:
        return next(value)
    return next(value, default)


def _dynamic_eval(source: str, globals_: object = None, locals_: object = None) -> object:
    raise VMError("PortaPy eval marker must be handled by the VM")


def _dynamic_exec(source: str, globals_: object = None, locals_: object = None) -> None:
    raise VMError("PortaPy exec marker must be handled by the VM")


def _dynamic_compile(source: str, filename: str = "<string>", mode: str = "exec") -> object:
    raise VMError("PortaPy compile marker must be handled by the VM")


def _dynamic_globals() -> dict[str, object]:
    raise VMError("PortaPy globals marker must be handled by the VM")


def _dynamic_locals() -> dict[str, object]:
    raise VMError("PortaPy locals marker must be handled by the VM")


def _dynamic_dir(value: object = None) -> list[str]:
    raise VMError("PortaPy dir marker must be handled by the VM")


def _dynamic_super(*args: object, **kwargs: object) -> object:
    raise VMError("PortaPy super marker must be handled by the VM")


def _missing_import(name: str, *args: object, **kwargs: object) -> object:
    raise ModuleNotFoundError(name)


_dynamic_eval.__pyinbin_eval__ = True
_dynamic_exec.__pyinbin_exec__ = True
_dynamic_compile.__pyinbin_compile__ = True
_dynamic_globals.__pyinbin_globals__ = True
_dynamic_locals.__pyinbin_locals__ = True
_dynamic_dir.__pyinbin_dir__ = True
_dynamic_super.__pyinbin_super__ = True


def default_builtins(importer: object | None = None) -> dict[str, object]:
    """Return a fresh explicit builtin table for one runtime namespace."""
    result = {}
    result["__debug__"] = True
    result["print"] = _builtin_print
    result["len"] = _builtin_len
    result["sum"] = _builtin_sum
    result["range"] = _builtin_range
    result["repr"] = _builtin_repr
    result["getattr"] = _builtin_getattr
    result["setattr"] = _builtin_setattr
    result["hasattr"] = _builtin_hasattr
    result["isinstance"] = _builtin_isinstance
    result["issubclass"] = _builtin_issubclass
    result["any"] = _builtin_any
    result["all"] = _builtin_all
    result["abs"] = _builtin_abs
    result["round"] = _builtin_round
    result["pow"] = _builtin_pow
    result["sorted"] = _builtin_sorted
    result["reversed"] = _builtin_reversed
    result["iter"] = _builtin_iter
    result["next"] = _builtin_next
    result["str"] = str
    result["int"] = int
    result["float"] = float
    result["bool"] = bool
    result["bytes"] = bytes
    result["bytearray"] = bytearray
    result["object"] = object
    result["type"] = type
    result["slice"] = slice
    result["list"] = list
    result["tuple"] = tuple
    result["dict"] = dict
    result["set"] = set
    result["frozenset"] = frozenset
    result["staticmethod"] = staticmethod
    result["classmethod"] = classmethod
    result["property"] = property
    result["Exception"] = Exception
    result["BaseException"] = BaseException
    result["SystemExit"] = SystemExit
    result["KeyboardInterrupt"] = KeyboardInterrupt
    result["GeneratorExit"] = GeneratorExit
    result["RuntimeError"] = RuntimeError
    result["ArithmeticError"] = ArithmeticError
    result["OverflowError"] = OverflowError
    result["OSError"] = OSError
    result["IOError"] = OSError
    result["NameError"] = NameError
    result["ValueError"] = ValueError
    result["TypeError"] = TypeError
    result["SyntaxError"] = SyntaxError
    result["KeyError"] = KeyError
    result["IndexError"] = IndexError
    result["ZeroDivisionError"] = ZeroDivisionError
    result["StopIteration"] = StopIteration
    result["StopAsyncIteration"] = StopAsyncIteration
    result["ImportError"] = ImportError
    result["ModuleNotFoundError"] = ModuleNotFoundError
    result["AttributeError"] = AttributeError
    result["LookupError"] = LookupError
    result["NotImplementedError"] = NotImplementedError
    result["AssertionError"] = AssertionError
    result["eval"] = _dynamic_eval
    result["exec"] = _dynamic_exec
    result["compile"] = _dynamic_compile
    result["globals"] = _dynamic_globals
    result["locals"] = _dynamic_locals
    result["dir"] = _dynamic_dir
    result["super"] = _dynamic_super
    if importer is None:
        result["__import__"] = _missing_import
    else:
        result["__import__"] = importer
    result["__builtins__"] = result
    return result
