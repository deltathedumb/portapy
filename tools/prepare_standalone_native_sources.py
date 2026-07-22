"""Prepare PortaPy's full VM sources for the pinned native asmpython compiler.

The hosted source remains the source of truth. This applies the existing
fail-closed normalization passes to ``vm_impl.py`` while temporarily exposing
that implementation through ``vm.py``. ``frontend.py`` is normalized only while
the passes run and is restored before this function returns; the standalone
runtime itself uses ``portable_frontend.py``.
"""
from __future__ import annotations

from pathlib import Path
import shutil


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE = REPOSITORY_ROOT / "src" / "portapy" / "core"
FRONTEND = CORE / "frontend.py"
VM = CORE / "vm.py"
VM_IMPL = CORE / "vm_impl.py"
_MARKERS = (
    "def _full_core_probe_noop()",
    "def _full_core_probe_pop_tail(",
    "def _full_core_probe_call_host(",
)


def is_prepared() -> bool:
    source = VM_IMPL.read_text(encoding="utf-8")
    return all(marker in source for marker in _MARKERS)


def prepare() -> bool:
    """Prepare sources and return True when this call changed the checkout."""
    if is_prepared():
        print("standalone native sources already prepared")
        return False
    if not FRONTEND.is_file() or not VM_IMPL.is_file():
        raise RuntimeError("standalone frontend or VM implementation is missing")

    frontend_original = FRONTEND.read_bytes()
    vm_original = VM.read_bytes()
    try:
        shutil.copyfile(VM_IMPL, VM)

        from tools.normalize_full_core_lambdas import main as normalize_lambdas
        from tools.normalize_full_core_native_semantics import main as normalize_semantics
        from tools.normalize_full_core_opcode_maps import main as normalize_opcodes
        from tools.normalize_full_core_validation import main as normalize_validation

        passes = (
            ("lambdas", normalize_lambdas),
            ("native semantics", normalize_semantics),
            ("opcode maps", normalize_opcodes),
            ("validation", normalize_validation),
        )
        for label, function in passes:
            status = function()
            if status not in (None, 0):
                raise RuntimeError(f"standalone {label} normalization failed: {status}")
        shutil.copyfile(VM, VM_IMPL)
        if not is_prepared():
            raise RuntimeError("standalone VM normalization markers are missing")
        print(f"prepared standalone native VM: {VM_IMPL}")
        return True
    finally:
        FRONTEND.write_bytes(frontend_original)
        VM.write_bytes(vm_original)


def main() -> int:
    prepare()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
