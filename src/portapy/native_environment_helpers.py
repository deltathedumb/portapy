"""First-class helper methods for the native PortaPy Python facade."""
from __future__ import annotations

from typing import Mapping

from . import native_binary as _native
from .environment import BindingError


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    def add(
        environment: _native.NativeEnvironment,
        value: object,
        *,
        name: str | None = None,
        replace: bool = False,
    ) -> _native.NativeEnvironment:
        binding_name = name
        if binding_name is None:
            declared = getattr(value, "__name__", None)
            if not isinstance(declared, str) or not declared:
                raise BindingError("added object has no usable __name__")
            binding_name = declared.rsplit(".", 1)[-1]
        environment._bind(binding_name, value, replace=replace)
        return environment

    def add_all(
        environment: _native.NativeEnvironment,
        *sources: Mapping[str, object] | object,
        include_private: bool = False,
        replace: bool = False,
    ) -> _native.NativeEnvironment:
        return environment.expose(
            *sources,
            include_private=include_private,
            replace=replace,
        )

    _native.NativeEnvironment.add = add
    _native.NativeEnvironment.add_all = add_all


install()


__all__ = ["install"]
