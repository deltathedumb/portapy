"""Hide PortaPy runtime-internal globals from the public native facade."""
from __future__ import annotations

from . import native_binary as _native


_INTERNAL_PREFIXES = ("__pyinbin_", "__portapy_internal_")
_installed = False


def _is_public_global(name: str) -> bool:
    return not any(name.startswith(prefix) for prefix in _INTERNAL_PREFIXES)


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    original_global_names = _native.NativeEnvironment._global_names

    def public_global_names(environment: _native.NativeEnvironment) -> tuple[str, ...]:
        return tuple(
            name
            for name in original_global_names(environment)
            if _is_public_global(name)
        )

    _native.NativeEnvironment._global_names = public_global_names


install()


__all__ = ["install"]
