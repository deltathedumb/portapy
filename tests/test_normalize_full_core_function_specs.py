from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_function_specs as normalizer


SOURCE = '''def lower_function(node):
    self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), len(node.args.defaults), kw_default_count, annotations)))

def lower_lambda(node):
    self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), len(node.args.defaults), 0)))
'''


def test_canonicalizes_lambda_to_four_fields(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "(nested.finish(), len(node.args.defaults), 0, {})" in source
    assert "(nested.finish(), len(node.args.defaults), 0))" not in source
    assert "kw_default_count, annotations" in source


def test_fails_closed_without_lambda_producer(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(SOURCE.replace("def lower_lambda", "def other_lambda").replace(
        "    self.emit(Op.MAKE_FUNCTION, self.constant((nested.finish(), len(node.args.defaults), 0)))\n",
        "    pass\n",
    ), encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "lambda function spec" in str(error)
    else:
        raise AssertionError("normalizer accepted a missing lambda function spec")
