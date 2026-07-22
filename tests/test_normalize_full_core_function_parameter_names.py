from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_function_parameter_names as normalizer


_SPECIAL = '''            nested.posonly_names = [arg.arg for arg in node.args.posonlyargs]
            nested.kwonly_names = [arg.arg for arg in node.args.kwonlyargs]
            nested.vararg_name = node.args.vararg.arg if node.args.vararg else None
            nested.kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
'''

_SOURCE = '''class _Lowerer:
    def expr(self, node):
            lambda_arguments = list(node.args.posonlyargs)
            for argument in node.args.args:
                lambda_arguments.append(argument)
            nested = _Lowerer("<lambda>", [arg.arg for arg in lambda_arguments])
''' + _SPECIAL + '''    def stmt(self, node):
            function_arguments = list(node.args.posonlyargs)
            for argument in node.args.args:
                function_arguments.append(argument)
            nested = _Lowerer(node.name, [arg.arg for arg in function_arguments])
''' + _SPECIAL


def test_replaces_opaque_parameter_extraction(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "[arg.arg for arg in function_arguments]" not in source
    assert "[arg.arg for arg in lambda_arguments]" not in source
    assert "[arg.arg for arg in node.args.posonlyargs]" not in source
    assert "[arg.arg for arg in node.args.kwonlyargs]" not in source
    assert 'function_argument_name: str = getattr(argument, "arg")' in source
    assert 'lambda_argument_name: str = getattr(argument, "arg")' in source
    assert source.count('positional_only_name: str = getattr(argument, "arg")') == 2
    assert source.count('keyword_only_name: str = getattr(argument, "arg")') == 2
    assert source.count('variadic_positional = getattr(node.args, "vararg")') == 2
    assert source.count('variadic_positional_name: str = getattr(variadic_positional, "arg")') == 2
    assert source.count('variadic_keyword = getattr(node.args, "kwarg")') == 2
    assert source.count('variadic_keyword_name: str = getattr(variadic_keyword, "arg")') == 2
    assert "function_argument_name: str = argument.arg" not in source
    assert "lambda_argument_name: str = argument.arg" not in source


def test_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0
    first = path.read_text(encoding="utf-8")
    assert normalizer.main() == 0
    assert path.read_text(encoding="utf-8") == first


def test_fails_closed_for_unknown_shape(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text("class _Lowerer: pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "source shape changed" in str(error)
    else:
        raise AssertionError("normalizer accepted unknown parameter extraction")
