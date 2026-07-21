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
_SEED_MARKER = "    machine = _FullTracingVirtualMachine(runtime)\n"
_SEED_REPLACEMENT = (
    "    machine = _FullTracingVirtualMachine(runtime)\n"
    "    machine._seed_builtins(namespace)\n"
)
_TYPED_REPLACEMENTS = (
    ("_full_runtime_machines = [None]", "_full_runtime_machines: list[object] = [None]"),
    (
        "_full_runtime_namespaces = [None]",
        "_full_runtime_namespaces: list[dict[str, object]] = [{}]",
    ),
    (
        "_full_runtime_reserved = [None]",
        "_full_runtime_reserved: list[dict[str, object]] = [{}]",
    ),
    ("_full_runtime_users = [None]", "_full_runtime_users: list[list[str]] = [[]]"),
    ("_full_object_value = [None]", "_full_object_value: list[object] = [None]"),
    (
        "def _full_ensure_runtime(runtime: int) -> int:\n"
        "    if not _runtime_is_valid(runtime):\n"
        "        return 0\n"
        "    existing = _full_runtime_slot(runtime)\n"
        "    if existing != 0:\n"
        "        return existing\n"
        "    namespace = {\n",
        "def _full_ensure_runtime(runtime: int) -> int:\n"
        "    if not _runtime_is_valid(runtime):\n"
        "        return 0\n"
        "    existing = _full_runtime_slot(runtime)\n"
        "    if existing != 0:\n"
        "        return existing\n"
        "    namespace: dict[str, object] = {\n",
    ),
    (
        "        self.runtime = runtime\n        self.trace_frames = []",
        "        self.runtime = runtime\n        self.trace_frames: list[object] = []",
    ),
    (
        "    if kind == PORTAPY_VALUE_TUPLE:\n        result = []",
        "    if kind == PORTAPY_VALUE_TUPLE:\n        result: list[object] = []",
    ),
    (
        "    if kind == PORTAPY_VALUE_LIST:\n        result = []",
        "    if kind == PORTAPY_VALUE_LIST:\n        result: list[object] = []",
    ),
    (
        "    if kind == PORTAPY_VALUE_DICT:\n        result = {}",
        "    if kind == PORTAPY_VALUE_DICT:\n        result: dict[str, object] = {}",
    ),
    ("        _full_runtime_namespaces[slot] = None", "        _full_runtime_namespaces[slot] = {}"),
    ("        _full_runtime_reserved[slot] = None", "        _full_runtime_reserved[slot] = {}"),
    ("        _full_runtime_users[slot] = None", "        _full_runtime_users[slot] = []"),
)
_SOURCE_SIZE_REPLACEMENTS = (
    (
        "def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:\n"
        "    if not _runtime_is_valid(runtime):\n"
        "        return _set_status(PORTAPY_INVALID_HANDLE)\n"
        "    if source_size < 0 or source_size > len(source):",
        "def _portapy_exec_span_impl(runtime: int, source: str, source_size: int) -> int:\n"
        "    if not _runtime_is_valid(runtime):\n"
        "        return _set_status(PORTAPY_INVALID_HANDLE)\n"
        "    if source_size < 0:",
    ),
    (
        "def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:\n"
        "    if not _runtime_is_valid(runtime):\n"
        "        _set_status(PORTAPY_INVALID_HANDLE)\n"
        "        return 0\n"
        "    if source_size < 0 or source_size > len(source):",
        "def _portapy_eval_span_impl(runtime: int, source: str, source_size: int) -> int:\n"
        "    if not _runtime_is_valid(runtime):\n"
        "        _set_status(PORTAPY_INVALID_HANDLE)\n"
        "        return 0\n"
        "    if source_size < 0:",
    ),
)


def _replace_exactly_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"generated full runtime {label} has {count} matches: {old!r}")
    return source.replace(old, new, 1)


def _apply_replacements(source: str) -> str:
    for old, new in _TYPED_REPLACEMENTS:
        source = _replace_exactly_once(source, old, new, "typing target")
    for old, new in _SOURCE_SIZE_REPLACEMENTS:
        source = _replace_exactly_once(source, old, new, "source-size target")
    return source


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
    source = _apply_replacements(source)
    if source.count(_SEED_MARKER) != 1:
        raise ValueError("generated full runtime has an unexpected VM seed point")
    source = source.replace(_SEED_MARKER, _SEED_REPLACEMENT, 1)
    if "def _portapy_runtime_create_impl(" in source:
        raise ValueError("generated environment already defines runtime creation")
    path.write_text(source.rstrip() + _RUNTIME_CREATE + "\n", encoding="utf-8")
    return path


__all__ = ["rewrite_generated_full_vm_environment"]
