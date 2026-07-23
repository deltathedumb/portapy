from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_native_argument_defaults as normalizer


_SOURCE = '''class AST:
    pass

class expr(AST):
    pass

class arg(AST):
    def __init__(self, arg: str) -> None:
        self.arg = arg

class arguments(AST):
    def __init__(self, posonlyargs: list[arg], args: list[arg], vararg: arg | None,
                 kwonlyargs: list[arg], kw_defaults: list[expr | None],
                 kwarg: arg | None, defaults: list[expr]) -> None:
        self.posonlyargs = posonlyargs
        self.args = args
        self.vararg = vararg
        self.kwonlyargs = kwonlyargs
        self.kw_defaults = kw_defaults
        self.kwarg = kwarg
        self.defaults = defaults

def _convert_arguments(node: A.FuncDef, lifted: dict[str, A.FuncDef]) -> arguments:
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


def _module(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(path: Path) -> ast.FunctionDef:
    functions = [
        node
        for node in _module(path).body
        if isinstance(node, ast.FunctionDef) and node.name == "_convert_arguments"
    ]
    assert len(functions) == 1
    return functions[0]


def _arguments_initializer(path: Path) -> ast.FunctionDef:
    classes = [
        node
        for node in _module(path).body
        if isinstance(node, ast.ClassDef) and node.name == "arguments"
    ]
    assert len(classes) == 1
    initializers = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    ]
    assert len(initializers) == 1
    return initializers[0]


def _isolate(path: Path, monkeypatch) -> None:
    monkeypatch.setattr(normalizer, "PATH", path)
    monkeypatch.setattr(normalizer, "normalize_default_expressions", lambda: 0)


def test_pins_default_elements_and_storage_to_dict_backed_ast(
    tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(_SOURCE, encoding="utf-8")
    _isolate(path, monkeypatch)

    assert normalizer.main() == 0

    function = _function(path)
    source = ast.unparse(function)
    annotated_getattrs = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "native_defaults"
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "getattr"
        and len(node.value.args) == 2
        and isinstance(node.value.args[1], ast.Constant)
        and node.value.args[1].value == "defaults"
    ]
    assert len(annotated_getattrs) == 1
    assert "defaults: list[dict] = []" in source
    assert source.count("default_node: dict = native_defaults[index]") == 2
    assert "converted_default: dict = _convert_expr(default_node, lifted)" in source
    assert "defaults.append(converted_default)" in source
    assert "_convert_expr(node.defaults[index], lifted)" not in source

    initializer = _arguments_initializer(path)
    annotations = {
        argument.arg: ast.unparse(argument.annotation)
        for argument in initializer.args.args
        if argument.annotation is not None
    }
    assert annotations["defaults"] == "list[dict]"
    assert annotations["kw_defaults"] == "list[dict | None]"


def test_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text(_SOURCE, encoding="utf-8")
    _isolate(path, monkeypatch)

    assert normalizer.main() == 0
    first = path.read_text(encoding="utf-8")
    assert normalizer.main() == 0
    assert path.read_text(encoding="utf-8") == first


def test_fails_closed_for_unknown_shape(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "native_ast.py"
    path.write_text("def _convert_arguments():\n    pass\n", encoding="utf-8")
    _isolate(path, monkeypatch)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "native default" in str(error)
    else:
        raise AssertionError("normalizer accepted an unknown default bridge")
