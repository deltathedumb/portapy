from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_native_keyword_transport as normalizer
from tools import normalize_full_core_validation as validation


_SOURCE = '''def _raise_typed(message: str) -> None:
    raise TypeError(message)


class SuperProxy:
    pass


class VirtualMachine:
    def _call(self, target: object, args: list[object], kwargs: dict[str, object] | None = None) -> object:
        kwargs = kwargs or {}
        return kwargs

    def _run_frame(self, frame: object) -> object:
        target = object()
        positional: list[object] = []
        names: list[object] = []
        values: list[object] = []
        if True:
            if True:
                    kwargs: dict[str, object] = {}
                    for name, value in zip(names, values):
                        if name is None:
                            if not isinstance(value, dict): _raise_typed("TypeError: ** argument must be a mapping")
                            kwargs.update(value)
                        else:
                            kwargs[name] = value
                    if getattr(target, "__pyinbin_super__", False) and not positional and not kwargs:
                        instance = frame.locals.get("self")
                        cls = self._lexical_super_class(frame, instance)
                        frame.stack.append(SuperProxy(self, cls, instance))
                    else:
                        frame.stack.append(self._call(target, positional, kwargs))
'''


def _normalize(tmp_path: Path, monkeypatch) -> str:
    path = tmp_path / "vm.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "VM_PATH", path)
    assert normalizer.main() == 0
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    return source


def _vm(source: str) -> object:
    namespace: dict[str, object] = {}
    exec(source, namespace)
    return namespace["VirtualMachine"]()


def _expect_type_error(callback, message: str) -> None:
    try:
        callback()
    except TypeError as error:
        assert message in str(error)
    else:
        raise AssertionError("expected TypeError")


def test_transports_typed_keyword_names_and_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = _normalize(tmp_path, monkeypatch)

    assert "keyword_names: list[str] | None = None" in source
    assert "keyword_values: list[object] | None = None" in source
    assert "transported_kwargs: dict[str, object] = {}" in source
    assert "keyword_name: str = keyword_names[keyword_index]" in source
    assert "mapping_name: str = raw_mapping_name" in source
    assert "kwargs = transported_kwargs" in source
    assert "keyword_names: list[str] = []" in source
    assert 'keyword_names.append("")' in source
    assert "keyword_name: str = name" in source
    assert "self._call(target, positional, None, keyword_names, values)" in source
    assert "keyword_names: list[object]" not in source
    assert "for name, value in zip(names, values):" not in source

    vm = _vm(source)
    result = vm._call(
        object(),
        [],
        None,
        ["direct", ""],
        [1, {"mapped": 2, "": 3}],
    )
    assert result == {"direct": 1, "mapped": 2, "": 3}


def test_rejects_invalid_or_duplicate_mapping_keywords(
    tmp_path: Path,
    monkeypatch,
) -> None:
    vm = _vm(_normalize(tmp_path, monkeypatch))

    _expect_type_error(
        lambda: vm._call(object(), [], None, [""], [{1: "bad"}]),
        "keywords must be strings",
    )
    _expect_type_error(
        lambda: vm._call(
            object(),
            [],
            None,
            ["direct", ""],
            [1, {"direct": 2}],
        ),
        "multiple values for keyword argument",
    )


def test_empty_keyword_unpack_preserves_lexical_super(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = _normalize(tmp_path, monkeypatch)

    assert "has_effective_keywords = False" in source
    assert "if len(value) > 0:" in source
    assert "and not has_effective_keywords" in source
    assert "and not keyword_names" not in source


def test_fails_closed_when_call_shape_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "vm.py"
    path.write_text("class VirtualMachine:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "VM_PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "native keyword receiver" in str(error)
    else:
        raise AssertionError("normalizer accepted an unknown VM call shape")


def test_keyword_transport_runs_before_every_other_normalizer() -> None:
    module = ast.parse(Path(validation.__file__).read_text(encoding="utf-8"))
    main = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    assignment = next(
        node
        for node in main.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "steps"
    )
    assert isinstance(assignment.value, ast.Tuple)
    names = [
        item.elts[0].value
        for item in assignment.value.elts
        if isinstance(item, ast.Tuple)
        and len(item.elts) == 2
        and isinstance(item.elts[0], ast.Constant)
    ]
    assert names[0] == "native_keyword_transport"
