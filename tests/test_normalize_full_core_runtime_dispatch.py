from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_runtime_dispatch as normalizer


SOURCE = '''class VirtualMachine:
    def _call(self, target, args):
        return target(*args)

    def run(self, op, frame, instr):
        if op is Op.GET_ITER:
            value = frame.stack.pop()
            if isinstance(value, dict) or type(value).__name__ in {"dict_keys"}:
                value = list(value)
            frame.stack.append(iter(value))
        elif op is Op.IMPORT_NAME:
            loader = frame.globals.get("__pyinbin_import__")
            if not callable(loader):
                _raise_typed("ImportError: loader is not configured")
            imported = frame.code.names[instr.arg]
            top_level = imported.split(".", 1)[0]
            loader(top_level)
            frame.stack.append(loader(imported))
        elif op is Op.IMPORT_FROM:
            module = frame.stack.pop()
            member = frame.code.names[instr.arg]
            loader = frame.globals.get("__pyinbin_import__")
            module_name = getattr(module, "__name__", None)
            if not callable(loader) or not isinstance(module_name, str):
                raise AttributeError(member)
            value = loader(module_name)
            frame.stack.append(value)
        elif op is Op.IMPORT_ROOT:
            loader = frame.globals.get("__pyinbin_import__")
            if not callable(loader):
                _raise_typed("ImportError: loader is not configured")
            imported = frame.code.names[instr.arg]
            top_level = imported.split(".", 1)[0]
            loader(top_level)
            loader(imported)
            loader("sys")
            frame.stack.append(loader(top_level))
        elif op is Op.IMPORT_RELATIVE_FROM:
            loader = frame.globals.get("__pyinbin_import__")
            if not callable(loader):
                _raise_typed("ImportError: loader is not configured")
            base = "pkg"
            member = "item"
            loader(base)
            loader(base + "." + member)
            loader(base)
            loader(base + "." + member)
'''


def test_removes_native_iteration_and_loader_hazards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "frame.stack.append(iter(value))" in source
    assert "type(value).__name__" not in source
    assert "callable(loader)" not in source
    assert "loader is None" in source
    assert "self._call(loader, [imported])" in source
    assert "self._call(loader, [top_level])" in source
    ast.parse(source)


def test_fails_closed_without_all_import_branches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(
        SOURCE.replace("elif op is Op.IMPORT_RELATIVE_FROM:", "elif op is Op.OTHER:"),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "four import branches" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing import branch")
