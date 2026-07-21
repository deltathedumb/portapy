"""Recursive tuple boxing/unboxing for PortaPy's native Python facade."""
from __future__ import annotations

import ctypes

from . import native_binary as _native
from .reference_api import Status, ValueKind


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    original_bind = _native._NativeLibrary._bind
    original_box = _native.NativeEnvironment._box
    original_unbox = _native.NativeEnvironment._unbox

    def bind(library: _native._NativeLibrary) -> None:
        original_bind(library)
        library._function(
            "portapy_value_from_tuple",
            [
                _native._U64,
                ctypes.POINTER(_native._U64),
                _native._SIZE,
                ctypes.POINTER(_native._U64),
            ],
        )
        library._function(
            "portapy_tuple_get_size",
            [_native._U64, _native._U64, ctypes.POINTER(_native._SIZE)],
        )
        library._function(
            "portapy_tuple_get_item",
            [
                _native._U64,
                _native._U64,
                _native._SIZE,
                ctypes.POINTER(_native._U64),
            ],
        )

    def box(environment: _native.NativeEnvironment, value: object) -> int:
        if not isinstance(value, tuple):
            return original_box(environment, value)

        handles: list[int] = []
        try:
            for item in value:
                handles.append(environment._box(item))
            pointer = None
            storage = None
            if handles:
                array_type = _native._U64 * len(handles)
                storage = array_type(*handles)
                pointer = ctypes.cast(storage, ctypes.POINTER(_native._U64))
            result = environment._new_value(
                environment._api.portapy_value_from_tuple,
                pointer,
                len(handles),
            )
            _ = storage
            return result
        finally:
            for handle in handles:
                environment._api.portapy_value_release(
                    environment._runtime,
                    _native._U64(handle),
                )

    def unbox(environment: _native.NativeEnvironment, handle: int) -> object:
        kind = _native._STATUS(0)
        environment._check(
            int(
                environment._api.portapy_value_get_kind(
                    environment._runtime,
                    _native._U64(handle),
                    ctypes.byref(kind),
                )
            ),
            "inspect value kind",
        )
        if ValueKind(kind.value) is not ValueKind.TUPLE:
            return original_unbox(environment, handle)

        size = _native._SIZE(0)
        environment._check(
            int(
                environment._api.portapy_tuple_get_size(
                    environment._runtime,
                    _native._U64(handle),
                    ctypes.byref(size),
                )
            ),
            "inspect tuple size",
        )
        values: list[object] = []
        for index in range(size.value):
            item = _native._U64(0)
            environment._check(
                int(
                    environment._api.portapy_tuple_get_item(
                        environment._runtime,
                        _native._U64(handle),
                        index,
                        ctypes.byref(item),
                    )
                ),
                "extract tuple item",
            )
            try:
                values.append(environment._unbox(int(item.value)))
            finally:
                status = int(
                    environment._api.portapy_value_release(
                        environment._runtime,
                        item,
                    )
                )
                if status != int(Status.OK):
                    environment._check(status, "release tuple item")
        return tuple(values)

    _native._NativeLibrary._bind = bind
    _native.NativeEnvironment._box = box
    _native.NativeEnvironment._unbox = unbox


install()


__all__ = ["install"]
