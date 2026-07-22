from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_pop_top as normalizer


VM_SOURCE = '''def run(frame, op):
    if op is Op.LOAD_CONST:
        frame.stack.append(1)
    elif op is Op.POP_TOP:
        frame.stack.pop()
    elif op is Op.STORE_NAME:
        value = frame.stack.pop()
'''


def test_replaces_pop_top_with_stack_slice(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(VM_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "frame.stack = frame.stack[:-1]" in source
    assert "value = frame.stack.pop()" in source
    assert source.count("frame.stack = frame.stack[:-1]") == 1


def test_fails_closed_without_unique_handler(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text("def run():\n    return\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "expected one handler" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing POP_TOP handler")
