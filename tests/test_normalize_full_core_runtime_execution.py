from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_runtime_execution as normalizer


SOURCE = '''class VirtualMachine:
    def _exception_matches(self, value, expected):
        return False

    def _run_frame(self, frame):
        while True:
            try:
                op = current_op
                if op is Op.GET_ITER:
                    value = frame.stack.pop()
                    frame.stack.append(iter(value))
                elif op is Op.FOR_ITER:
                    if not frame.stack:
                        frame.ip = instr.arg
                        continue
                    try:
                        frame.stack.append(next(frame.stack[-1]))
                    except StopIteration:
                        frame.stack.pop()
                        frame.ip = instr.arg
                elif op is Op.MAKE_FUNCTION:
                    closure = {}
                    for name in nested.free_names:
                        if name in frame.locals:
                            closure[name] = frame.locals[name]
                        elif frame.closure is not None and name in frame.closure:
                            closure[name] = frame.closure[name]
            except BaseException as exc:
                frame.stack.append(exc)
'''


def test_installs_explicit_native_execution_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "class _NativeSequenceIterator:" in source
    assert "class _NativeCaughtException:" in source
    assert "frame.stack.append(_NativeSequenceIterator(sequence))" in source
    assert "iterator: _NativeSequenceIterator = frame.stack[-1]" in source
    assert "value = iterator.values[iterator.index]" in source
    assert "while closure_index < len(nested.free_names):" in source
    assert "exc = _NativeCaughtException(exc)" in source
    assert "if isinstance(value, _NativeCaughtException):" in source
    assert "frame.stack.append(iter(value))" not in source
    assert "next(frame.stack[-1])" not in source
    assert "for name in nested.free_names" not in source
    ast.parse(source)


def test_fails_closed_without_closure_loop(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(
        SOURCE.replace("for name in nested.free_names:", "for name in []:"),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "closure loop" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing closure loop")
