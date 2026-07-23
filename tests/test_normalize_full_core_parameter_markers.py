from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_parameter_markers as normalizer


SOURCE = '''class _npr_parser_Parser:
    def _parse_funcdef(self, decorators=None):
        start = self._peek().pos
        self._expect("KEYWORD", "def")
        name = self._expect("NAME").value
        self._expect("OP", "(")
        params = []
        defaults = []
        param_types = []
        vararg = None
        kwarg = None
        first = True
        while not self._check("OP", ")"):
            if not first:
                self._expect("OP", ",")
            first = False
            self._parse_param(params, defaults, param_types)
        self._expect("OP", ")")
        self._expect("OP", ":")
        body = self._parse_block()
        return _npr_ast_nodes_FuncDef(name=name, params=params, body=body)

def _convert_arguments(node, lifted):
    all_args = [AstArg(name) for name in node.params]
    defaults = []
    return arguments([], all_args, None if node.vararg is None else AstArg(node.vararg), [], [], None if node.kwarg is None else AstArg(node.kwarg), defaults)
'''


def test_preserves_slash_and_star_partitions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "self._check('OP', '/')" in source
    assert "__portapy_posonly_marker__" in source
    assert "__portapy_kwonly_marker__" in source
    assert "positional_only.append(parameter)" in source
    assert "keyword_only.append(parameter)" in source
    assert "keyword_defaults.append(None)" in source
    assert "return arguments(positional_only, regular, vararg_node" in source
    assert "return arguments([], all_args" not in source
    ast.parse(source)


def test_fails_closed_for_unknown_bridge_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(
        SOURCE.replace(
            "return arguments([], all_args, None if node.vararg is None else AstArg(node.vararg), [], [], None if node.kwarg is None else AstArg(node.kwarg), defaults)",
            "return arguments([], all_args, None, [], [], None, defaults)",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "flattened source shape" in str(error)
    else:
        raise AssertionError("normalizer accepted an unexpected argument bridge")
