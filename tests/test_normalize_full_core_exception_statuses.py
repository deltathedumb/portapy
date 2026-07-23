from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_exception_statuses as normalizer


VM_SOURCE = '''class VirtualMachine:
    def _run_frame(self, frame):
        while True:
            try:
                run()
            except BaseException as exc:
                exc = _NativeCaughtException(exc)
                caught = False
                if frame.handlers:
                    frame.stack.append(exc)
                    frame.active_exception = exc
                    caught = True
                if caught:
                    continue
                raise
'''

REFERENCE_SOURCE = '''class Runtime:
    def exec_utf8(self, source):
        try:
            self._vm.run(source)
        except TypeError as error:
            return self._capture_native(Status.TYPE_ERROR, "TypeError", "PortaPy type error")
        except BaseException as error:
            return self._capture_native(Status.RUNTIME_ERROR, "RuntimeError", "PortaPy runtime error")
'''


def test_preserves_escape_identity_and_maps_name_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    vm_path = tmp_path / "vm.py"
    reference_path = tmp_path / "reference_api.py"
    vm_path.write_text(VM_SOURCE, encoding="utf-8")
    reference_path.write_text(REFERENCE_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "VM_PATH", vm_path)
    monkeypatch.setattr(normalizer, "REFERENCE_PATH", reference_path)

    assert normalizer.main() == 0

    vm_source = vm_path.read_text(encoding="utf-8")
    assert "exc = _NativeCaughtException(exc)" not in vm_source
    assert "native_exception = _NativeCaughtException(exc)" in vm_source
    assert "frame.stack.append(native_exception)" in vm_source
    assert "frame.active_exception = native_exception" in vm_source
    assert "raise" in vm_source

    reference_source = reference_path.read_text(encoding="utf-8")
    assert "except NameError as error:" in reference_source
    assert "Status.NOT_FOUND" in reference_source
    assert reference_source.index("except NameError") < reference_source.index(
        "except BaseException"
    )
    ast.parse(vm_source)
    ast.parse(reference_source)


def test_fails_closed_without_wrapper_assignment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    vm_path = tmp_path / "vm.py"
    reference_path = tmp_path / "reference_api.py"
    vm_path.write_text(
        VM_SOURCE.replace(
            "                exc = _NativeCaughtException(exc)\n",
            "",
        ),
        encoding="utf-8",
    )
    reference_path.write_text(REFERENCE_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "VM_PATH", vm_path)
    monkeypatch.setattr(normalizer, "REFERENCE_PATH", reference_path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "wrapper handler" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing exception wrapper")
