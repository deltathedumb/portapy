"""Replace host-style function argument binding with compiler-safe loops.

The pinned native compiler lowers ``dict(zip(names, positional))`` by replacing
``zip(...)`` with a null value and then dereferencing it as a list. This crashes
as soon as an interpreted function is called. Dict comprehensions used for
``**kwargs`` have the same unsafe lowering shape, so normalize both operations
into explicit loops before native semantic rewriting.
"""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/core/vm.py")

_POSITIONAL_OLD = '''            positional = list(args[:total])
            locals_ = dict(zip(target.code.arg_names, positional))
'''

_POSITIONAL_NEW = '''            positional = list(args[:total])
            locals_: dict[str, object] = {}
            bind_index = 0
            while bind_index < len(positional) and bind_index < len(target.code.arg_names):
                locals_[target.code.arg_names[bind_index]] = positional[bind_index]
                bind_index += 1
'''

_KWARGS_OLD = '''            if target.code.kwarg_name:
                locals_[target.code.kwarg_name] = {
                    name: value for name, value in kwargs.items()
                    if name in target.code.posonly_names or (
                        name not in target.code.arg_names and name not in target.code.kwonly_names
                    )
                }
'''

_KWARGS_NEW = '''            if target.code.kwarg_name:
                extra_kwargs: dict[str, object] = {}
                for name in kwargs:
                    if name in target.code.posonly_names or (
                        name not in target.code.arg_names and name not in target.code.kwonly_names
                    ):
                        extra_kwargs[name] = kwargs[name]
                locals_[target.code.kwarg_name] = extra_kwargs
'''


def _state(source: str, old: str, new: str, label: str) -> str:
    old_count = source.count(old)
    new_count = source.count(new)
    if old_count == 1 and new_count == 0:
        return "original"
    if old_count == 0 and new_count == 1:
        return "normalized"
    raise RuntimeError(
        f"native function {label} binding source shape changed: "
        f"old={old_count}, normalized={new_count}"
    )


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    positional_state = _state(source, _POSITIONAL_OLD, _POSITIONAL_NEW, "positional")
    kwargs_state = _state(source, _KWARGS_OLD, _KWARGS_NEW, "kwargs")

    positional_count = 0
    kwargs_count = 0
    if positional_state == "original":
        source = source.replace(_POSITIONAL_OLD, _POSITIONAL_NEW, 1)
        positional_count = 1
    if kwargs_state == "original":
        source = source.replace(_KWARGS_OLD, _KWARGS_NEW, 1)
        kwargs_count = 1
    PATH.write_text(source, encoding="utf-8")

    required = (
        "locals_: dict[str, object] = {}",
        "while bind_index < len(positional)",
        "extra_kwargs: dict[str, object] = {}",
        "extra_kwargs[name] = kwargs[name]",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(f"native function binding validation failed: {missing}")
    if _POSITIONAL_OLD in source or _KWARGS_OLD in source:
        raise RuntimeError("unsafe native function binding source block remains")
    print("NORMALIZED NATIVE FUNCTION BINDING", positional_count, kwargs_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
