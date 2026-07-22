from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_make_function as normalizer


_ORIGINAL = '''def run(frame, op, instr):
    if op is Op.LOAD_CONST:
        pass
    elif op is Op.MAKE_FUNCTION:
        spec = frame.code.constants[instr.arg]
        default_count = 0
        kw_default_count = 0
        annotations: dict[str, object] = {}
        if isinstance(spec, tuple) and len(spec) == 4:
            nested, default_count, kw_default_count, annotations = spec
        elif isinstance(spec, tuple) and len(spec) == 2:
            nested, default_count = spec
        elif isinstance(spec, tuple) and len(spec) == 3:
            nested, default_count, kw_default_count = spec
        else:
            nested = spec
        if not isinstance(nested, CodeObject): _raise_typed("TypeError: invalid function constant")
        count = default_count + kw_default_count
        if len(frame.stack) < count: _raise_typed("RuntimeError: default stack underflow")
        values = frame.stack[-count:] if count else []
        if count: del frame.stack[-count:]
        defaults = values[:default_count]
        kw_defaults = {
            name: value for name, value in zip(nested.kwonly_names[-kw_default_count:], values[default_count:])
        }
        closure = {
            name: (frame.locals[name] if name in frame.locals else frame.closure[name])
            for name in nested.free_names
            if name in frame.locals or (frame.closure is not None and name in frame.closure)
        }
        nested.validate()
        function = Function(nested, frame.globals, defaults, kw_defaults, closure, self)
        if annotations:
            function._metadata["__annotations__"] = dict(annotations)
        frame.stack.append(function)
    elif op is Op.MAKE_CLASS:
        pass
'''


def test_removes_runtime_class_introspection_and_slices(
    tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "vm.py"
    path.write_text(_ORIGINAL, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "nested: CodeObject = spec" in source
    assert "if nested is None:" in source
    assert "while default_index < default_count:" in source
    assert "while kw_index < kw_default_count:" in source
    assert "for name in nested.free_names:" in source
    assert "isinstance(nested, CodeObject)" not in source
    assert "frame.stack[-count:]" not in source
    assert "values[:default_count]" not in source


def test_preserves_make_class_boundary(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(_ORIGINAL, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0
    source = path.read_text(encoding="utf-8")
    assert source.count("elif op is Op.MAKE_FUNCTION:") == 1
    assert source.count("elif op is Op.MAKE_CLASS:") == 1


def test_fails_closed_when_source_shape_changes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(
        '''def run(frame, op):
    if op is Op.MAKE_FUNCTION:
        frame.stack.append(1)
    elif op is Op.MAKE_CLASS:
        pass
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "source shape changed" in str(error)
    else:
        raise AssertionError("normalizer accepted an unknown MAKE_FUNCTION shape")
