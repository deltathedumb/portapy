from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_pop_top as normalizer


VM_SOURCE = '''class VirtualMachine:
    def __init__(self) -> None:
        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}
        self._current_frame: Frame | None = None

    def run(self, frame, op):
        if op is Op.LOAD_CONST:
            frame.stack.append(1)
        elif op is Op.POP_TOP:
            frame.stack.pop()
        elif op is Op.STORE_NAME:
            value = frame.stack.pop()
'''


def test_stores_discarded_pop_on_vm(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(VM_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "self._discarded: object = None" in source
    assert "self._discarded = frame.stack.pop()" in source
    assert "value = frame.stack.pop()" in source
    assert source.count("self._discarded = frame.stack.pop()") == 1


def test_fails_closed_without_unique_handler(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(
        '''class VirtualMachine:
    def __init__(self) -> None:
        self._synthetic_tracebacks: dict[int, "_PyTBProxy"] = {}
        self._current_frame: Frame | None = None
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "handler normalization" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing POP_TOP handler")
