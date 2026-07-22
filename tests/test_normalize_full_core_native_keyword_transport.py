from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_native_keyword_transport as normalizer
from tools import normalize_full_core_validation as validation


_SOURCE = '''class VirtualMachine:
    def _call(self, target: object, args: list[object], kwargs: dict[str, object] | None = None) -> object:
        kwargs = kwargs or {}
        return target

    def _run_frame(self, frame: object) -> object:
        target = object()
        positional: list[object] = []
        names: list[object] = []
        values: list[object] = []
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


def test_transports_keyword_names_and_values_as_lists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "VM_PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "keyword_names: list[object] | None = None" in source
    assert "keyword_values: list[object] | None = None" in source
    assert "self._call(target, positional, None, keyword_names, values)" in source
    assert "kwargs: dict[str, object] = {}" not in source
    assert "for name, value in zip(names, values):" not in source


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
