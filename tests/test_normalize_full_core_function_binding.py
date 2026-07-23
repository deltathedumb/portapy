from __future__ import annotations

from pathlib import Path

from tools import normalize_full_core_function_binding as normalizer


_SOURCE = '''class VirtualMachine:
    def _call(self, target, args, kwargs=None):
            positional = list(args[:total])
            locals_ = dict(zip(target.code.arg_names, positional))
            if target.code.kwarg_name:
                locals_[target.code.kwarg_name] = {
                    name: value for name, value in kwargs.items()
                    if name in target.code.posonly_names or (
                        name not in target.code.arg_names and name not in target.code.kwonly_names
                    )
                }
            return locals_
'''


def test_replaces_zip_and_kwargs_comprehension(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0

    source = path.read_text(encoding="utf-8")
    assert "dict(zip(" not in source
    assert "for name, value in kwargs.items()" not in source
    assert "argument_names: list[str] = target.code.arg_names" in source
    assert "argument_name: str = argument_names[bind_index]" in source
    assert "locals_[argument_name] = positional[bind_index]" in source
    assert "extra_kwargs[name] = kwargs[name]" in source


def test_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text(_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    assert normalizer.main() == 0
    first = path.read_text(encoding="utf-8")
    assert normalizer.main() == 0
    assert path.read_text(encoding="utf-8") == first


def test_fails_closed_when_binding_shape_changes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "vm.py"
    path.write_text("class VirtualMachine: pass\n", encoding="utf-8")
    monkeypatch.setattr(normalizer, "PATH", path)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "source shape changed" in str(error)
    else:
        raise AssertionError("normalizer accepted an unknown function binding shape")
