"""Use the normalized Runtime handle accessor when tagging native value kinds.

The full Runtime data-access pass stores opaque value slots in a list and exposes
``Runtime._value_slot(handle)`` as the canonical bounds-checked lookup.  The
source-kind pass historically reached into ``Runtime._values`` as though it were
a string-keyed dictionary, so the pinned compiler folded every lookup to
``None`` and all handles retained the default INT kind.
"""
from __future__ import annotations

import ast
from pathlib import Path


PATH = Path("src/portapy/native_full_reference_entry.py")
_FUNCTION = "_native_set_handle_kind"


_REPLACEMENT = '''def _native_set_handle_kind(
    instance: Runtime,
    handle: int,
    kind: int,
) -> bool:
    slot = instance._value_slot(handle)
    if slot is None:
        return False
    slot.kind = _native_kind_member(kind)
    return True
'''


def main() -> int:
    module = ast.parse(PATH.read_text(encoding="utf-8"), filename=str(PATH))
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == _FUNCTION
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"native handle-kind helper expected once, found {len(matches)}"
        )

    function = matches[0]
    original = ast.unparse(function)
    if "instance._values" not in original or ".get(str(handle))" not in original:
        raise RuntimeError(
            "native handle-kind helper no longer has the stale dict lookup"
        )

    replacement = ast.parse(_REPLACEMENT).body[0]
    replacement.decorator_list = function.decorator_list
    index = module.body.index(function)
    module.body[index] = replacement

    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    PATH.write_text(source, encoding="utf-8")

    verified = ast.parse(source, filename=str(PATH))
    repaired = next(
        node
        for node in verified.body
        if isinstance(node, ast.FunctionDef) and node.name == _FUNCTION
    )
    text = ast.unparse(repaired)
    required = (
        "slot = instance._value_slot(handle)",
        "slot.kind = _native_kind_member(kind)",
        "return True",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"native handle-kind repair was lost: {missing}")
    forbidden = ("instance._values", ".get(str(handle))")
    remaining = [marker for marker in forbidden if marker in text]
    if remaining:
        raise RuntimeError(f"stale native handle-kind lookup remains: {remaining}")

    print("REPAIRED NATIVE HANDLE KIND ACCESS", 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
