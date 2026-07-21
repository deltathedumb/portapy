"""Install the canonical standalone VM adapter into a generated environment.

The historical implementation of this module carried a second, scalar-only VM
bridge. The release path now delegates to ``rewrite_generated_full_runtime`` so
there is one adapter for execution, host callbacks, containers, opaque VM
objects, tracebacks, and lifecycle state.
"""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_full_runtime import rewrite_generated_full_runtime


_RUNTIME_CREATE = '''


def _portapy_runtime_create_impl() -> int:
    runtime = _core_portapy_runtime_create_impl()
    if runtime != 0:
        _full_ensure_runtime(runtime)
    return runtime
'''


def rewrite_generated_full_vm_environment(
    path: Path,
    *,
    host_module: str,
    target: str | None = None,
) -> Path:
    if not host_module.isidentifier():
        raise ValueError(f"invalid generated host module: {host_module!r}")
    selected = target
    if selected is None:
        selected = "windows" if host_module.endswith("_windows") else "linux"
    rewrite_generated_full_runtime(path, target=selected)
    source = path.read_text(encoding="utf-8")
    if "def _portapy_runtime_create_impl(" in source:
        raise ValueError("generated environment already defines runtime creation")
    path.write_text(source.rstrip() + _RUNTIME_CREATE + "\n", encoding="utf-8")
    return path


__all__ = ["rewrite_generated_full_vm_environment"]
