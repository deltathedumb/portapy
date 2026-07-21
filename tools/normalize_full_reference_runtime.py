"""Normalize host-only features in the native reference runtime."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/reference_api.py")

_TRACEBACK_IMPORT = "import traceback\n"
_TRACEBACK_FORMAT = '            "".join(traceback.format_exception(error)),\n'
_NATIVE_FORMAT = (
    '            type(error).__name__ + ": " + str(error),\n'
)
_SLOT = '''@dataclass
class _Slot:
    value: object
    refs: int = 1
'''
_NATIVE_SLOT = '''@dataclass
class _Slot:
    value: object
    kind: ValueKind = ValueKind.INT
    refs: int = 1
'''
_STORE = '''    def _store(self, value: object) -> int:
        handle = self._next
        self._next += 1
        self._values[handle] = _Slot(value)
        return handle
'''
_NATIVE_STORE = '''    def _store(
        self,
        value: object,
        kind: ValueKind = ValueKind.INT,
    ) -> int:
        handle = self._next
        self._next += 1
        self._values[handle] = _Slot(value, kind)
        return handle
'''
_BOX_METHODS = '''    def box_none(self) -> tuple[Status, int]:
        return Status.OK, self._store(None)

    def box_bool(self, value: bool) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_int(self, value: int) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_float(self, value: float) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_utf8(self, value: str) -> tuple[Status, int]:
        return Status.OK, self._store(value)

    def box_bytes(self, value: bytes) -> tuple[Status, int]:
        return Status.OK, self._store(value)
'''
_NATIVE_BOX_METHODS = '''    def box_none(self) -> tuple[Status, int]:
        return Status.OK, self._store(None, ValueKind.NONE)

    def box_bool(self, value: bool) -> tuple[Status, int]:
        return Status.OK, self._store(value, ValueKind.BOOL)

    def box_int(self, value: int) -> tuple[Status, int]:
        return Status.OK, self._store(value, ValueKind.INT)

    def box_float(self, value: float) -> tuple[Status, int]:
        return Status.OK, self._store(value, ValueKind.FLOAT)

    def box_utf8(self, value: str) -> tuple[Status, int]:
        return Status.OK, self._store(value, ValueKind.STRING)

    def box_bytes(self, value: bytes) -> tuple[Status, int]:
        return Status.OK, self._store(value, ValueKind.BYTES)
'''
_VALUE_KIND_METHOD = '''    def value_kind(self, handle: int) -> tuple[Status, ValueKind]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), ValueKind.OBJECT
        value = slot.value
        if value is None:
            kind = ValueKind.NONE
        elif type(value) is bool:
            kind = ValueKind.BOOL
        elif type(value) is int:
            kind = ValueKind.INT
        elif type(value) is float:
            kind = ValueKind.FLOAT
        elif type(value) is str:
            kind = ValueKind.STRING
        elif type(value) is bytes:
            kind = ValueKind.BYTES
        elif type(value) is tuple:
            kind = ValueKind.TUPLE
        elif type(value) is dict:
            kind = ValueKind.DICT
        elif type(value) is list:
            kind = ValueKind.LIST
        elif callable(value):
            kind = ValueKind.CALLABLE
        else:
            kind = ValueKind.OBJECT
        return Status.OK, kind
'''
_NATIVE_VALUE_KIND_METHOD = '''    def value_kind(self, handle: int) -> tuple[Status, ValueKind]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), ValueKind.OBJECT
        return Status.OK, slot.kind
'''
_AS_INT_METHOD = '''    def as_int(self, handle: int) -> tuple[Status, int]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), 0
        if type(slot.value) is not int:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not int")), 0
        return Status.OK, slot.value
'''
_NATIVE_AS_INT_METHOD = '''    def as_int(self, handle: int) -> tuple[Status, int]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), 0
        if slot.kind is not ValueKind.INT:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not int")), 0
        return Status.OK, slot.value
'''
_AS_FLOAT_METHOD = '''    def as_float(self, handle: int) -> tuple[Status, float]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), 0.0
        if type(slot.value) is not float:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not float")), 0.0
        return Status.OK, slot.value
'''
_NATIVE_AS_FLOAT_METHOD = '''    def as_float(self, handle: int) -> tuple[Status, float]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), 0.0
        if slot.kind is not ValueKind.FLOAT:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not float")), 0.0
        return Status.OK, slot.value
'''
_AS_UTF8_METHOD = '''    def as_utf8(self, handle: int) -> tuple[Status, bytes]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), b""
        if type(slot.value) is not str:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not str")), b""
        return Status.OK, slot.value.encode("utf-8")
'''
_NATIVE_AS_UTF8_METHOD = '''    def as_utf8(self, handle: int) -> tuple[Status, bytes]:
        slot = self._values.get(handle)
        if slot is None:
            return self._capture(Status.INVALID_HANDLE, KeyError(handle)), b""
        if slot.kind is not ValueKind.STRING:
            return self._capture(Status.TYPE_ERROR, TypeError("value is not str")), b""
        return Status.OK, slot.value.encode("utf-8")
'''
_VALUES_ANNOTATION = "self._values: dict[int, _Slot] = {}"
_NATIVE_VALUES_ANNOTATION = "self._values: dict[str, _Slot] = {}"
_HANDLE_SUBSCRIPT = "self._values[handle]"
_NATIVE_HANDLE_SUBSCRIPT = "self._values[str(handle)]"
_HANDLE_GET = "self._values.get(handle)"
_NATIVE_HANDLE_GET = "self._values.get(str(handle))"
_CALLABLE_HANDLE_GET = "self._values.get(callable_handle)"
_NATIVE_CALLABLE_HANDLE_GET = "self._values.get(str(callable_handle))"


def _replace_exact(
    source: str,
    old: str,
    new: str,
    *,
    label: str,
    expected: int,
) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(
            f"native reference {label} normalization expected {expected} matches, "
            f"found {count}"
        )
    return source.replace(old, new)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    replacements = (
        (_TRACEBACK_IMPORT, "", "traceback import"),
        (_TRACEBACK_FORMAT, _NATIVE_FORMAT, "traceback formatter"),
        (_SLOT, _NATIVE_SLOT, "value slot"),
        (_STORE, _NATIVE_STORE, "value store"),
        (_BOX_METHODS, _NATIVE_BOX_METHODS, "scalar boxing"),
        (_VALUE_KIND_METHOD, _NATIVE_VALUE_KIND_METHOD, "value kind"),
        (_AS_INT_METHOD, _NATIVE_AS_INT_METHOD, "integer conversion"),
        (_AS_FLOAT_METHOD, _NATIVE_AS_FLOAT_METHOD, "float conversion"),
        (_AS_UTF8_METHOD, _NATIVE_AS_UTF8_METHOD, "UTF-8 conversion"),
        (_VALUES_ANNOTATION, _NATIVE_VALUES_ANNOTATION, "value-table annotation"),
    )
    for old, new, label in replacements:
        source = _replace_exact(source, old, new, label=label, expected=1)
    source = _replace_exact(
        source,
        _HANDLE_SUBSCRIPT,
        _NATIVE_HANDLE_SUBSCRIPT,
        label="value-table subscript",
        expected=2,
    )
    source = _replace_exact(
        source,
        _HANDLE_GET,
        _NATIVE_HANDLE_GET,
        label="value-table lookup",
        expected=8,
    )
    source = _replace_exact(
        source,
        _CALLABLE_HANDLE_GET,
        _NATIVE_CALLABLE_HANDLE_GET,
        label="callable value-table lookup",
        expected=1,
    )
    PATH.write_text(source, encoding="utf-8")
    print("NORMALIZED NATIVE REFERENCE ERROR CAPTURE", 1)
    print("NORMALIZED NATIVE VALUE HANDLE KEYS", 11)
    print("NORMALIZED NATIVE VALUE KIND SLOTS", 9)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
