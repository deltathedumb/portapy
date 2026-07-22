from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_native_argument_defaults as normalizer


_SOURCE = '''def _convert_arguments(node: A.FuncDef, lifted: dict[str, A.FuncDef]) -> arguments:
    all_args = [arg(name) for name in node.params]
    defaults: list[expr] = []
    first_default = len(node.defaults)
    index = 0
    while index < len(node.defaults):
        if node.defaults[index] is not None:
            first_default = index
            break
        index += 1
    if first_default < len(node.defaults):
        index = first_default
        while index < len(node.defaults):
            defaults.append(_convert_expr(node.defaults[index], lifted))
            index += 1
    return arguments([], all_args, None if node.vararg is None else arg(node.vararg), [], [], None if node.kwarg is None else arg(node.kwarg), defaults)
'''


def test_pins_default_elements_to_dict_backed_ast(
    tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert 'native_defaults: list[dict] = getattr(node, "defaults")' in source
    assert source.count("default_node: dict = native_defaults[index]") == 2
    assert "defaults.append(_convert_expr(default_node, lifted))" in source
    assert "_convert_expr(node.defaults[index], lifted)" not in source


def test_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0
    first = path.read_text(encoding="utf-8")
    assert normalizer.main() == 0
    assert path.read_text(encoding="utf-8") == first


def test_fails_closed_for_unknown_shape(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text("def _convert_arguments():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "source shape changed" in str(error)
    else:
        raise AssertionError("normalizer accepted an unknown default bridge")
