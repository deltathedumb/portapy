from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_keyword_calls as normalizer


def test_frontend_keyword_fields_are_extracted_through_typed_locals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    frontend = tmp_path / "frontend.py"
    frontend.write_text(
        '''            for keyword in node.keywords:
                self.expr(keyword.value)
            names = tuple(keyword.arg for keyword in node.keywords)
            self.emit(Op.CALL_KW, self.constant((tuple(arg_specs), names)))
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "FRONTEND_PATH", frontend)

    normalizer._normalize_frontend()

    source = frontend.read_text(encoding="utf-8")
    assert 'keyword_value: ast.expr = getattr(keyword, "value")' in source
    assert 'keyword_name = getattr(keyword, "arg")' in source
    assert "keyword_names.append(keyword_name)" in source
    assert "self.expr(keyword.value)" not in source
    assert "keyword.arg for keyword" not in source
