from __future__ import annotations

import ast
from pathlib import Path

from tools import normalize_full_core_runtime_specs as normalizer


BYTECODE = '''from __future__ import annotations

class CodeObject:
    pass
'''

FRONTEND = '''from .bytecode import CodeObject, Instruction, Op

class Lowerer:
    def lower(self, node, body, base_count, has_keywords, arg_specs):
        keyword_names: list[object] = []
        names = tuple(keyword_names)
        self.emit(Op.CALL_KW, self.constant((tuple(arg_specs), names)))
        spec = (node.name, body.finish(), base_count, has_keywords)
        self.emit(Op.MAKE_CLASS, self.constant(spec))
'''

VM = '''from .bytecode import CodeObject, Op

class VirtualMachine:
    def run(self, op, frame, instr):
        if op is Op.MAKE_CLASS:
            spec = frame.code.constants[instr.arg]
            if not isinstance(spec, tuple) or len(spec) not in (3, 4):
                _raise_typed("TypeError: invalid class constant")
            class_name, body, base_count = spec[:3]
            has_keywords = bool(spec[3]) if len(spec) == 4 else False
            if not isinstance(class_name, str) or not isinstance(body, CodeObject):
                _raise_typed("TypeError: invalid class constant")
            bases = _full_core_probe_pop_tail(frame.stack, base_count)
        elif op is Op.CALL_KW:
            spec = frame.code.constants[instr.arg]
            if not isinstance(spec, tuple) or len(spec) != 2:
                _raise_typed("RuntimeError: invalid keyword call")
            positional_spec, names = spec
            if isinstance(positional_spec, int):
                positional_spec = tuple(False for _ in range(positional_spec))
            if not isinstance(positional_spec, tuple):
                _raise_typed("RuntimeError: invalid positional call")
            positional_count = len(positional_spec)
'''


def test_converts_opcode_specs_to_typed_objects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bytecode = tmp_path / "bytecode.py"
    frontend = tmp_path / "frontend.py"
    vm = tmp_path / "vm.py"
    bytecode.write_text(BYTECODE, encoding="utf-8")
    frontend.write_text(FRONTEND, encoding="utf-8")
    vm.write_text(VM, encoding="utf-8")
    monkeypatch.setattr(normalizer, "BYTECODE_PATH", bytecode)
    monkeypatch.setattr(normalizer, "FRONTEND_PATH", frontend)
    monkeypatch.setattr(normalizer, "VM_PATH", vm)

    assert normalizer.main() == 0

    bytecode_source = bytecode.read_text(encoding="utf-8")
    frontend_source = frontend.read_text(encoding="utf-8")
    vm_source = vm.read_text(encoding="utf-8")
    assert "class _NativeKeywordCallSpec:" in bytecode_source
    assert "class _NativeClassSpec:" in bytecode_source
    assert "self.positional_spec = positional_spec" in bytecode_source
    assert "self.body = body" in bytecode_source
    assert "_NativeKeywordCallSpec(arg_specs, names)" in frontend_source
    assert (
        "_NativeClassSpec(node.name, body.finish(), base_count, has_keywords)"
        in frontend_source
    )
    assert "spec: _NativeKeywordCallSpec" in vm_source
    assert "positional_spec = spec.positional_spec" in vm_source
    assert "names = spec.names" in vm_source
    assert "spec: _NativeClassSpec" in vm_source
    assert "class_name = spec.class_name" in vm_source
    assert "body = spec.body" in vm_source
    assert "len(spec)" not in vm_source
    assert "isinstance(spec, tuple)" not in vm_source
    ast.parse(bytecode_source)
    ast.parse(frontend_source)
    ast.parse(vm_source)


def test_fails_closed_when_frontend_shape_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bytecode = tmp_path / "bytecode.py"
    frontend = tmp_path / "frontend.py"
    vm = tmp_path / "vm.py"
    bytecode.write_text(BYTECODE, encoding="utf-8")
    frontend.write_text(
        FRONTEND.replace("names = tuple(keyword_names)", "names = keyword_names"),
        encoding="utf-8",
    )
    vm.write_text(VM, encoding="utf-8")
    monkeypatch.setattr(normalizer, "BYTECODE_PATH", bytecode)
    monkeypatch.setattr(normalizer, "FRONTEND_PATH", frontend)
    monkeypatch.setattr(normalizer, "VM_PATH", vm)

    try:
        normalizer.main()
    except RuntimeError as error:
        assert "frontend runtime specs" in str(error)
    else:
        raise AssertionError("normalizer accepted an unknown frontend shape")
