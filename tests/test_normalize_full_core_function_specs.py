from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_function_specs as normalizer


SOURCE = '''class Lowerer:
    def lower_lambda(self, node):
            for default in node.args.defaults:
                self.expr(default)
            self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), len(node.args.defaults), 0)))

    def lower_function(self, node):
            for default in node.args.defaults:
                self.expr(default)
            kw_default_count = 0
            for default in node.args.kw_defaults:
                if default is None:
                    continue
                self.expr(default)
                kw_default_count += 1
            self.emit(
                Op.MAKE_FUNCTION,
                self.constant((nested.finish(), len(node.args.defaults), kw_default_count, annotations)),
            )
'''


def test_counts_defaults_and_pins_ast_elements(
    tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert 'lambda_defaults: list[dict] = getattr(node.args, "defaults")' in source
    assert "lambda_default: dict = lambda_defaults[lambda_default_index]" in source
    assert "lambda_default_count += 1" in source
    assert "(nested.finish(), lambda_default_count, 0, {})" in source
    assert 'function_defaults: list[dict] = getattr(node.args, "defaults")' in source
    assert "function_default: dict = function_defaults[default_index]" in source
    assert "default_count += 1" in source
    assert 'keyword_defaults: list[dict] = getattr(node.args, "kw_defaults")' in source
    assert "keyword_default: dict = keyword_defaults[keyword_default_index]" in source
    assert "(nested.finish(), default_count, kw_default_count, annotations)" in source
    assert "len(node.args.defaults)" not in source
    assert "for default in node.args.defaults:" not in source
    assert "for default in node.args.kw_defaults:" not in source


def test_fails_closed_without_lambda_defaults_shape(
    tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(
        SOURCE.replace(
            '''            for default in node.args.defaults:
                self.expr(default)
            self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), len(node.args.defaults), 0)))
''',
            "            pass\n",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "lambda defaults" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing lambda defaults producer")
