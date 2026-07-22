from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_function_parameter_names as normalizer


_SOURCE = '''class _Lowerer:
    def stmt(self, node):
            function_arguments = list(node.args.posonlyargs)
            for argument in node.args.args:
                function_arguments.append(argument)
            nested = _Lowerer(node.name, [arg.arg for arg in function_arguments])
            nested.posonly_names = [arg.arg for arg in node.args.posonlyargs]
            nested.kwonly_names = [arg.arg for arg in node.args.kwonlyargs]
            nested.vararg_name = node.args.vararg.arg if node.args.vararg else None
            nested.kwarg_name = node.args.kwarg.arg if node.args.kwarg else None
'''


def test_replaces_opaque_parameter_extraction(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "frontend.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "[arg.arg for arg in function_arguments]" not in source
    assert "[arg.arg for arg in node.args.posonlyargs]" not in source
    assert "[arg.arg for arg in node.args.kwonlyargs]" not in source
    assert "function_argument_name: str = argument.arg" in source
    assert "positional_only_name: str = argument.arg" in source
    assert "keyword_only_name: str = argument.arg" in source
    assert "variadic_positional_name: str = node.args.vararg.arg" in source
    assert "variadic_keyword_name: str = node.args.kwarg.arg" in source


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
