"""Opaque PortaPy-owned object support for the native Python facade."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from . import native_binary as _native
from .reference_api import Status, ValueKind


@dataclass(frozen=True)
class NativeObjectReference:
    """Opaque reference to an object owned by the native PortaPy VM.

    The public ABI intentionally exposes host IDs only for host-owned objects.
    PortaPy-created classes and instances therefore remain opaque when they are
    read through the Python binary facade instead of being misidentified as
    host objects.
    """


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    original_unbox = _native.NativeEnvironment._unbox

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
        if ValueKind(kind.value) is not ValueKind.OBJECT:
            return original_unbox(environment, handle)

        host_id = _native._U64(0)
        status = int(
            environment._api.portapy_value_get_host_id(
                environment._runtime,
                _native._U64(handle),
                ctypes.byref(host_id),
            )
        )
        if status == int(Status.OK):
            return environment._objects.get(
                int(host_id.value),
                _native.NativeHostReference(int(host_id.value)),
            )
        if status == int(Status.TYPE_ERROR):
            environment._api.portapy_error_clear(environment._runtime)
            return NativeObjectReference()
        environment._check(status, "recover host object")
        raise AssertionError("unreachable native object status")

    _native.NativeEnvironment._unbox = unbox


install()


__all__ = ["NativeObjectReference", "install"]
