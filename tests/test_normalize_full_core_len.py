from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_len as normalizer


LOADER_SOURCE = '''def _builtin_len(value: object) -> int:
    return len(value)
'''

FRONTEND_SOURCE = '''class _Lowerer:
    def expr(self, node):
        if isinstance(node, ast.Constant):
            pass
        elif isinstance(node, ast.Call) and not node.keywords and all(not isinstance(arg, ast.Starred) for arg in node.args):
            self.expr(node.func)
            for arg in node.args:
                self.expr(arg)
            self.emit(Op.CALL, len(node.args))
        elif isinstance(node, ast.Call):
            pass
'''


def test_threads_expression_kind_into_native_len(
    tmp_path: Path,
    monkeypatch,
) -> None:
    loader = tmp_path / "loader.py"
    frontend = tmp_path / "frontend.py"
    loader.write_text(LOADER_SOURCE, encoding="utf-8")
    frontend.write_text(FRONTEND_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "LOADER_PATH", loader)
    monkeypatch.setattr(normalizer, "FRONTEND_PATH", frontend)

    assert normalizer.main() == 0

    loader_source = loader.read_text(encoding="utf-8")
    assert "def _builtin_len(value: object, kind: int=0) -> int:" in loader_source
    assert "text_value: str = value" in loader_source
    assert "container_value: list = value" in loader_source
    assert "kind == 5 or kind == 6" in loader_source

    frontend_source = frontend.read_text(encoding="utf-8")
    assert "node.func.id == 'len'" in frontend_source
    assert "self.constant(self.expression_kind(node.args[0]))" in frontend_source
    assert "self.emit(Op.CALL, 2)" in frontend_source
    assert frontend_source.count("self.emit(Op.CALL, 2)") == 1
    ast.parse(loader_source)
    ast.parse(frontend_source)


def test_fails_closed_when_len_builtin_shape_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    loader = tmp_path / "loader.py"
    frontend = tmp_path / "frontend.py"
    loader.write_text(
        LOADER_SOURCE.replace("return len(value)", "return 0"),
        encoding="utf-8",
    )
    frontend.write_text(FRONTEND_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "LOADER_PATH", loader)
    monkeypatch.setattr(normalizer, "FRONTEND_PATH", frontend)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "unsafe object shape" in str(error)
    else:
        raise AssertionError("normalizer accepted an unexpected len builtin")
