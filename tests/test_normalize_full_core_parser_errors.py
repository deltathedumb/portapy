from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_parser_errors as normalizer


SOURCE = '''class _npr_parser_Parser:
    def _parse_primary(self):
        t = self._peek()
        if t.kind == "INT":
            return t
        raise _npr_errors_ParseError(
            f"unexpected token {t.kind} {t.value!r}",
            t.pos,
            ErrorCode.P_UNEXPECTED_TOKEN,
        )
'''


def test_replaces_dynamic_unexpected_token_message(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "raise _npr_errors_ParseError('unexpected token'," in source
    assert "t.pos" in source
    assert "ErrorCode.P_UNEXPECTED_TOKEN" in source
    assert "t.value" not in source
    ast.parse(source)


def test_fails_closed_without_target_message(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        SOURCE.replace("unexpected token", "different diagnostic"),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "expected one rewrite" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing target diagnostic")
