"""Encode CALL_KW and MAKE_CLASS constants as fixed native-safe lists.

The pinned compiler infers heterogeneous tuple constants as strings when they are
read back through ``CodeObject.constants``.  Keyword-call and class specs then
use ``strlen`` and string indexing instead of tuple semantics.  Emit fixed lists
and unpack their fields directly, matching the already-proven MAKE_FUNCTION
normalization.
"""
from __future__ import annotations

from pathlib import Path


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
VM_PATH = Path("src/portapy/core/vm.py")

_FRONTEND_CALL_OLD = '''            names = tuple(keyword_names)
            self.emit(Op.CALL_KW, self.constant((tuple(arg_specs), names)))
'''
_FRONTEND_CALL_NEW = '''            names: list[object] = keyword_names
            self.emit(Op.CALL_KW, self.constant([arg_specs, names]))
'''
_FRONTEND_CLASS_OLD = '''            spec = (node.name, body.finish(), base_count, has_keywords)
            self.emit(Op.MAKE_CLASS, self.constant(spec))
'''
_FRONTEND_CLASS_NEW = '''            spec: list[object] = [node.name, body.finish(), base_count, has_keywords]
            self.emit(Op.MAKE_CLASS, self.constant(spec))
'''

_VM_CLASS_OLD = '''                    spec = frame.code.constants[instr.arg]
                    if not isinstance(spec, tuple) or len(spec) not in (3, 4): _raise_typed("TypeError: invalid class constant")
                    class_name, body, base_count = spec[:3]
                    has_keywords = bool(spec[3]) if len(spec) == 4 else False
                    if not isinstance(class_name, str) or not isinstance(body, CodeObject): _raise_typed("TypeError: invalid class constant")
'''
_VM_CLASS_NEW = '''                    spec = frame.code.constants[instr.arg]
                    class_name: str = spec[0]
                    body: CodeObject = spec[1]
                    base_count: int = spec[2]
                    has_keywords: bool = spec[3]
'''

_VM_CALL_OLD = '''                    spec = frame.code.constants[instr.arg]
                    if not isinstance(spec, tuple) or len(spec) != 2: _raise_typed("RuntimeError: invalid keyword call")
                    positional_spec, names = spec
                    if isinstance(positional_spec, int):
                        positional_spec = tuple(False for _ in range(positional_spec))
                    if not isinstance(positional_spec, tuple): _raise_typed("RuntimeError: invalid positional call")
'''
_VM_CALL_NEW = '''                    spec = frame.code.constants[instr.arg]
                    positional_spec: list[bool] = spec[0]
                    names: list[object] = spec[1]
'''


def _replace_one(source: str, old: str, new: str, *, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source shape, found {count}")
    print("REPLACED", label, count)
    return source.replace(old, new, 1)


def main() -> int:
    frontend = FRONTEND_PATH.read_text(encoding="utf-8")
    frontend = _replace_one(
        frontend,
        _FRONTEND_CALL_OLD,
        _FRONTEND_CALL_NEW,
        label="native keyword-call list spec",
    )
    frontend = _replace_one(
        frontend,
        _FRONTEND_CLASS_OLD,
        _FRONTEND_CLASS_NEW,
        label="native class list spec",
    )
    FRONTEND_PATH.write_text(frontend, encoding="utf-8")

    vm = VM_PATH.read_text(encoding="utf-8")
    vm = _replace_one(
        vm,
        _VM_CLASS_OLD,
        _VM_CLASS_NEW,
        label="native class spec unpack",
    )
    vm = _replace_one(
        vm,
        _VM_CALL_OLD,
        _VM_CALL_NEW,
        label="native keyword-call spec unpack",
    )
    VM_PATH.write_text(vm, encoding="utf-8")

    required_frontend = (
        "self.constant([arg_specs, names])",
        "spec: list[object] = [node.name, body.finish(), base_count, has_keywords]",
    )
    required_vm = (
        "positional_spec: list[bool] = spec[0]",
        "names: list[object] = spec[1]",
        "class_name: str = spec[0]",
        "body: CodeObject = spec[1]",
        "base_count: int = spec[2]",
        "has_keywords: bool = spec[3]",
    )
    missing = [marker for marker in required_frontend if marker not in frontend]
    missing.extend(marker for marker in required_vm if marker not in vm)
    if missing:
        raise RuntimeError(f"native runtime spec validation failed: {missing}")

    forbidden = (
        "invalid keyword call",
        "invalid positional call",
        "invalid class constant",
        "self.constant((tuple(arg_specs), names))",
        "spec = (node.name, body.finish(), base_count, has_keywords)",
    )
    remaining = [marker for marker in forbidden if marker in vm or marker in frontend]
    if remaining:
        raise RuntimeError(f"unsafe native runtime specs remain: {remaining}")

    print("NORMALIZED NATIVE RUNTIME SPECS", 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
