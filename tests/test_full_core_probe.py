from __future__ import annotations

import importlib
from pathlib import Path
import sys

from tools.materialize_full_reference_entry import main as materialize_reference_entry
from tools.normalize_full_reference_abi_helpers import (
    main as normalize_reference_abi_helpers,
)
from tools.normalize_full_reference_runtime import (
    PATH as REFERENCE_RUNTIME_PATH,
    main as normalize_reference_runtime,
)


_TEMPORARY_MODULES = (
    "portapy.native_full_core_probe",
    "portapy.native_full_reference_entry",
    "portapy.reference_api",
)
_NATIVE_ENTRY_PATH = (
    Path(__file__).parents[1] / "src" / "portapy" / "native_full_reference_entry.py"
)


def _unload_temporary_modules() -> None:
    for name in _TEMPORARY_MODULES:
        sys.modules.pop(name, None)
    importlib.invalidate_caches()


def test_full_core_probe_executes_reference_abi_path() -> None:
    original_reference_runtime = REFERENCE_RUNTIME_PATH.read_text(encoding="utf-8")
    original_native_entry = _NATIVE_ENTRY_PATH.read_text(encoding="utf-8")
    try:
        _unload_temporary_modules()
        normalize_reference_runtime()
        materialize_reference_entry()
        normalize_reference_abi_helpers()
        _unload_temporary_modules()
        from portapy.native_full_core_probe import portapy_full_core_probe
        from portapy.native_full_reference_entry import _runtimes

        result = portapy_full_core_probe()
        errors = [
            runtime.last_error()
            for runtime in _runtimes
            if runtime is not None and runtime.last_error() is not None
        ]
        assert result == 42, errors
    finally:
        REFERENCE_RUNTIME_PATH.write_text(
            original_reference_runtime,
            encoding="utf-8",
        )
        _NATIVE_ENTRY_PATH.write_text(original_native_entry, encoding="utf-8")
        _unload_temporary_modules()
