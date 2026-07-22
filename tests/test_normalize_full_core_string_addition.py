from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tools import normalize_full_core_string_addition as normalizer


NATIVE_AST_SOURCE = '''
class A:
    class BinOp: pass
class expr: pass
class BinOp(expr):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right
_BIN_OPS = {"+": object()}
def _convert_expr(node, lifted):
    if isinstance(node, A.BinOp):
        return BinOp(_convert_expr(node.left, lifted), _BIN_OPS[node.op], _convert_expr(node.right, lifted))
    return expr()
'''

FRONTEND_SOURCE = '''
class Lowerer:
    def expr(self, node):
        if False:
            pass
        elif isinstance(node, ast.BinOp) and _binary_opcode(node.op) is not None:
            self.expr(node.left)
            self.expr(node.right)
            self.emit(_binary_opcode(node.op))
'''

VM_SOURCE = '''
class VirtualMachine:
    def run(self, frame, instr, op):
        left = None
        right = None
        if op is Op.BINARY_ADD: frame.stack.append(left + right)
'''


def test_installs_typed_native_string_addition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    native_ast = tmp_path / "native_ast.py"
    frontend = tmp_path / "frontend.py"
    vm = tmp_path / "vm.py"
    native_ast.write_text(NATIVE_AST_SOURCE, encoding="utf-8")
    frontend.write_text(FRONTEND_SOURCE, encoding="utf-8")
    vm.write_text(VM_SOURCE, encoding="utf-8")
    monkeypatch.setattr(normalizer, "NATIVE_AST_PATH", native_ast)
    monkeypatch.setattr(normalizer, "FRONTEND_PATH", frontend)
    monkeypatch.setattr(normalizer, "VM_PATH", vm)

    assert normalizer.main() == 0

    native_text = native_ast.read_text(encoding="utf-8")
    assert "converted._native_kind = 4" in native_text
    assert "node.op == '+'" in native_text

    frontend_text = frontend.read_text(encoding="utf-8")
    assert "self.emit(binary_opcode, binary_kind)" in frontend_text
    assert "binary_kind = _TRUTH_STRING" in frontend_text
    assert "binary_kind = 8" in frontend_text

    vm_text = vm.read_text(encoding="utf-8")
    assert "def _full_core_probe_concat_strings" in vm_text
    assert 'return f"{left}{right}"' in vm_text
    assert "instr.arg == 4" in vm_text
    assert "instr.arg == 8" in vm_text
    assert "can only concatenate string to string" in vm_text

    ast.parse(native_text)
    ast.parse(frontend_text)
    ast.parse(vm_text)
