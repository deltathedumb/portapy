"""Recursive string-key mapping boxing for PortaPy's native Python facade."""
from __future__ import annotations

import ctypes
from collections.abc import Mapping

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
            "portapy_value_from_dict",
            [_native._U64, ctypes.POINTER(_native._U64)],
        )
        library._function(
            "portapy_dict_set_utf8",
            [
                _native._U64,
                _native._U64,
                ctypes.c_void_p,
                _native._SIZE,
                _native._U64,
            ],
        )
        library._function(
            "portapy_dict_get_size",
            [_native._U64, _native._U64, ctypes.POINTER(_native._SIZE)],
        )
        library._function(
            "portapy_dict_key_copy_utf8",
            [
                _native._U64,
                _native._U64,
                _native._SIZE,
                ctypes.POINTER(_native._BYTE),
                _native._SIZE,
                ctypes.POINTER(_native._SIZE),
            ],
        )
        library._function(
            "portapy_dict_get_item_utf8",
            [
                _native._U64,
                _native._U64,
                ctypes.c_void_p,
                _native._SIZE,
                ctypes.POINTER(_native._U64),
            ],
        )

    def box(environment: _native.NativeEnvironment, value: object) -> int:
        if not isinstance(value, Mapping):
            return original_box(environment, value)

        result = environment._new_value(environment._api.portapy_value_from_dict)
        try:
            for key, member in value.items():
                if not isinstance(key, str) or not key or not key.isascii():
                    raise _native.BindingError(
                        "native PortaPy dictionary keys must be non-empty ASCII strings"
                    )
                encoded = key.encode("ascii")
                storage, pointer = environment._buffer(encoded)
                child = environment._box(member)
                try:
                    environment._check(
                        int(
                            environment._api.portapy_dict_set_utf8(
                                environment._runtime,
                                _native._U64(result),
                                pointer,
                                len(encoded),
                                _native._U64(child),
                            )
                        ),
                        f"box dictionary key {key!r}",
                    )
                finally:
                    _ = storage
                    environment._api.portapy_value_release(
                        environment._runtime,
                        _native._U64(child),
                    )
            return result
        except BaseException:
            environment._api.portapy_value_release(
                environment._runtime,
                _native._U64(result),
            )
            raise

    def _copy_key(environment: _native.NativeEnvironment, handle: int, index: int) -> str:
        required = _native._SIZE(0)
        status = int(
            environment._api.portapy_dict_key_copy_utf8(
                environment._runtime,
                _native._U64(handle),
                index,
                None,
                0,
                ctypes.byref(required),
            )
        )
        if status not in (int(Status.OK), int(Status.INVALID_ARGUMENT)):
            environment._check(status, "inspect dictionary key")
        buffer = (_native._BYTE * required.value)()
        environment._check(
            int(
                environment._api.portapy_dict_key_copy_utf8(
                    environment._runtime,
                    _native._U64(handle),
                    index,
                    buffer,
                    required.value,
                    ctypes.byref(required),
                )
            ),
            "copy dictionary key",
        )
        return bytes(buffer).decode("ascii")

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
        if ValueKind(kind.value) is not ValueKind.DICT:
            return original_unbox(environment, handle)

        size = _native._SIZE(0)
        environment._check(
            int(
                environment._api.portapy_dict_get_size(
                    environment._runtime,
                    _native._U64(handle),
                    ctypes.byref(size),
                )
            ),
            "inspect dictionary size",
        )
        result: dict[str, object] = {}
        for index in range(size.value):
            key = _copy_key(environment, handle, index)
            encoded = key.encode("ascii")
            storage, pointer = environment._buffer(encoded)
            item = _native._U64(0)
            try:
                environment._check(
                    int(
                        environment._api.portapy_dict_get_item_utf8(
                            environment._runtime,
                            _native._U64(handle),
                            pointer,
                            len(encoded),
                            ctypes.byref(item),
                        )
                    ),
                    f"extract dictionary key {key!r}",
                )
            finally:
                _ = storage
            try:
                result[key] = environment._unbox(int(item.value))
            finally:
                status = int(
                    environment._api.portapy_value_release(
                        environment._runtime,
                        item,
                    )
                )
                if status != int(Status.OK):
                    environment._check(status, "release dictionary item")
        return result

    _native._NativeLibrary._bind = bind
    _native.NativeEnvironment._box = box
    _native.NativeEnvironment._unbox = unbox


install()


__all__ = ["install"]
