from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_pop_top as normalizer


def test_assigns_discarded_pop_result(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(
        '''def run(frame, op):
    if op is Op.LOAD_CONST:
        frame.stack.append(1)
    elif op is Op.POP_TOP:
        frame.stack.pop()
    elif op is Op.STORE_NAME:
        value = frame.stack.pop()
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "discarded = frame.stack.pop()" in source
    assert "value = frame.stack.pop()" in source
    assert source.count("discarded = frame.stack.pop()") == 1


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
