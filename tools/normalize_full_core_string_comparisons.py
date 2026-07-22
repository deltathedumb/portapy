"""Give native VM string comparisons Python value semantics."""
from __future__ import annotations

from pathlib import Path

from tools.normalize_full_core_truthiness_safe_ast import main as normalize_truthiness


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
VM_PATH = Path("src/portapy/core/vm.py")

_HELPER = '''def _full_core_probe_compare_strings(left: str, right: str, operation: int) -> bool:
    if operation == 20:
        return left == right
    if operation == 21:
        return left < right
    if operation == 22:
        return left <= right
    if operation == 23:
        return left > right
    if operation == 24:
        return left >= right
    return left != right


'''


def _replace(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"native string comparison {label}: expected 1 match, found {count}"
        )
    return source.replace(old, new, 1)


def _normalize_frontend() -> int:
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    old = '''            operands = [node.left, *node.comparators]
            for index, op in enumerate(node.ops):
                self.expr(operands[index])
                self.expr(operands[index + 1])
                self.emit(_compare_opcode(op))
                if index:
                    self.emit(Op.BINARY_BOOL_AND)
'''
    new = '''            operands = [node.left, *node.comparators]
            for index, op in enumerate(node.ops):
                left_operand = operands[index]
                right_operand = operands[index + 1]
                self.expr(left_operand)
                self.expr(right_operand)
                comparison_kind = _TRUTH_UNKNOWN
                if (
                    self.expression_kind(left_operand) == _TRUTH_STRING
                    and self.expression_kind(right_operand) == _TRUTH_STRING
                ):
                    comparison_kind = _TRUTH_STRING
                self.emit(_compare_opcode(op), comparison_kind)
                if index:
                    self.emit(Op.BINARY_BOOL_AND)
'''
    source = _replace(source, old, new, "frontend lowering")
    FRONTEND_PATH.write_text(source, encoding="utf-8")
    if "self.emit(_compare_opcode(op), comparison_kind)" not in source:
        raise RuntimeError("native string comparison kind was not emitted")
    return 1


def _normalize_vm() -> int:
    source = VM_PATH.read_text(encoding="utf-8")
    class_anchor = "class VirtualMachine:"
    source = _replace(source, class_anchor, _HELPER + class_anchor, "helper insertion")
    old = '''                    if op is Op.COMPARE_EQ:
                        frame.stack.append(left == right)
                    elif op is Op.COMPARE_LT:
                        frame.stack.append(left < right)
                    elif op is Op.COMPARE_LE:
                        frame.stack.append(left <= right)
                    elif op is Op.COMPARE_GT:
                        frame.stack.append(left > right)
                    elif op is Op.COMPARE_GE:
                        frame.stack.append(left >= right)
                    elif op is Op.COMPARE_NE:
                        frame.stack.append(left != right)
'''
    new = '''                    if instr.arg == 4 and op in (
                        Op.COMPARE_EQ,
                        Op.COMPARE_LT,
                        Op.COMPARE_LE,
                        Op.COMPARE_GT,
                        Op.COMPARE_GE,
                        Op.COMPARE_NE,
                    ):
                        frame.stack.append(
                            _full_core_probe_compare_strings(left, right, op)
                        )
                    elif op is Op.COMPARE_EQ:
                        frame.stack.append(left == right)
                    elif op is Op.COMPARE_LT:
                        frame.stack.append(left < right)
                    elif op is Op.COMPARE_LE:
                        frame.stack.append(left <= right)
                    elif op is Op.COMPARE_GT:
                        frame.stack.append(left > right)
                    elif op is Op.COMPARE_GE:
                        frame.stack.append(left >= right)
                    elif op is Op.COMPARE_NE:
                        frame.stack.append(left != right)
'''
    source = _replace(source, old, new, "VM dispatch")
    VM_PATH.write_text(source, encoding="utf-8")
    if source.count("_full_core_probe_compare_strings") != 2:
        raise RuntimeError("native string comparison helper validation failed")
    return 1


def main() -> int:
    normalize_truthiness()
    frontend_count = _normalize_frontend()
    vm_count = _normalize_vm()
    print("NORMALIZED NATIVE STRING COMPARISONS", frontend_count, vm_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
