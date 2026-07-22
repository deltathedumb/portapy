"""Give native VM string comparisons Python value semantics."""
from __future__ import annotations

import ast
from pathlib import Path

from tools.normalize_full_core_truthiness_safe_ast import main as normalize_truthiness


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
NATIVE_AST_PATH = Path("src/portapy/core/native_ast.py")
VM_PATH = Path("src/portapy/core/vm.py")

_MIXED_STRING_KIND = 8

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


def _is_source_node_test(node: ast.If, suffix: str) -> bool:
    test = node.test
    if not (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
        and len(test.args) == 2
        and isinstance(test.args[0], ast.Name)
        and test.args[0].id == "node"
    ):
        return False
    expected = test.args[1]
    if isinstance(expected, ast.Name):
        return expected.id.endswith(suffix)
    if isinstance(expected, ast.Attribute):
        return expected.attr == suffix
    return False


def _normalize_native_ast_metadata() -> int:
    module = ast.parse(NATIVE_AST_PATH.read_text(encoding="utf-8"))
    converter = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "_convert_expr"
        ),
        None,
    )
    if converter is None:
        raise RuntimeError("native AST expression converter is missing")

    name_count = 0
    integer_count = 0
    float_count = 0
    string_count = 0
    fstring_count = 0
    for node in ast.walk(converter):
        if not isinstance(node, ast.If):
            continue
        if _is_source_node_test(node, "Name"):
            node.body = ast.parse(
                "converted = Name(node.name)\n"
                "converted._native_name = node.name\n"
                "return converted\n"
            ).body
            name_count += 1
        elif _is_source_node_test(node, "IntLit"):
            node.body = ast.parse(
                "if node.is_none:\n"
                "    converted = Constant(None)\n"
                "    converted._native_kind = 7\n"
                "    return converted\n"
                "if node.is_bool:\n"
                "    converted = Constant(bool(node.value))\n"
                "    converted._native_kind = 1\n"
                "    return converted\n"
                "converted = Constant(node.value)\n"
                "converted._native_kind = 2\n"
                "return converted\n"
            ).body
            integer_count += 1
        elif _is_source_node_test(node, "FloatLit"):
            node.body = ast.parse(
                "converted = Constant(node.value)\n"
                "converted._native_kind = 3\n"
                "return converted\n"
            ).body
            float_count += 1
        elif _is_source_node_test(node, "StrLit"):
            node.body = ast.parse(
                "converted = Constant(node.value)\n"
                "converted._native_kind = 4\n"
                "return converted\n"
            ).body
            string_count += 1
        elif _is_source_node_test(node, "FString"):
            original = list(node.body)
            if not original:
                raise RuntimeError("native FString conversion body is empty")
            final_return = original[-1]
            if not isinstance(final_return, ast.Return):
                raise RuntimeError("native FString conversion has no final return")
            result_name = "converted_fstring"
            node.body = original[:-1]
            node.body.extend(
                [
                    ast.Assign(
                        targets=[ast.Name(id=result_name, ctx=ast.Store())],
                        value=final_return.value,
                    ),
                    ast.Assign(
                        targets=[
                            ast.Attribute(
                                value=ast.Name(id=result_name, ctx=ast.Load()),
                                attr="_native_kind",
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.Constant(4),
                    ),
                    ast.Return(value=ast.Name(id=result_name, ctx=ast.Load())),
                ]
            )
            fstring_count += 1

    actual = (
        name_count,
        integer_count,
        float_count,
        string_count,
        fstring_count,
    )
    if actual != (1, 1, 1, 1, 1):
        raise RuntimeError(
            "native AST comparison metadata expected one Name, IntLit, FloatLit, "
            f"StrLit, and FString conversion; found {actual}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    NATIVE_AST_PATH.write_text(source, encoding="utf-8")
    for marker in (
        "._native_kind = 1",
        "._native_kind = 2",
        "._native_kind = 3",
        "._native_kind = 4",
        "._native_kind = 7",
        "._native_name =",
    ):
        if marker not in source:
            raise RuntimeError(
                f"native comparison metadata stamping lost {marker!r}"
            )
    return 5


def _normalize_frontend() -> int:
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    old = '''            operands = [node.left]
            for comparator in node.comparators:
                operands.append(comparator)
            for index, op in enumerate(node.ops):
                self.expr(operands[index])
                self.expr(operands[index + 1])
                self.emit(_compare_opcode(op))
                if index:
                    self.emit(Op.BINARY_BOOL_AND)
'''
    new = f'''            left_operand: ast.expr = getattr(node, "left")
            index = 0
            while index < len(node.ops):
                op = node.ops[index]
                right_operand: ast.expr = node.comparators[index]
                self.expr(left_operand)
                self.expr(right_operand)
                left_kind: int = getattr(left_operand, "_native_kind", _TRUTH_UNKNOWN)
                left_name: str = getattr(left_operand, "_native_name", "")
                if left_kind == _TRUTH_UNKNOWN and left_name != "":
                    left_kind = self.kind_hint(left_name)
                right_kind: int = getattr(right_operand, "_native_kind", _TRUTH_UNKNOWN)
                right_name: str = getattr(right_operand, "_native_name", "")
                if right_kind == _TRUTH_UNKNOWN and right_name != "":
                    right_kind = self.kind_hint(right_name)
                comparison_kind = _TRUTH_UNKNOWN
                if left_kind == _TRUTH_STRING and right_kind == _TRUTH_STRING:
                    comparison_kind = _TRUTH_STRING
                elif (
                    left_kind == _TRUTH_STRING and right_kind != _TRUTH_UNKNOWN
                ) or (
                    right_kind == _TRUTH_STRING and left_kind != _TRUTH_UNKNOWN
                ):
                    comparison_kind = {_MIXED_STRING_KIND}
                self.emit(_compare_opcode(op), comparison_kind)
                if index:
                    self.emit(Op.BINARY_BOOL_AND)
                left_operand = right_operand
                index += 1
'''
    source = _replace(source, old, new, "frontend lowering")
    FRONTEND_PATH.write_text(source, encoding="utf-8")
    if "self.emit(_compare_opcode(op), comparison_kind)" not in source:
        raise RuntimeError("native string comparison kind was not emitted")
    if f"comparison_kind = {_MIXED_STRING_KIND}" not in source:
        raise RuntimeError("native mixed string comparison tag was not emitted")
    if "operands = [node.left]" in source:
        raise RuntimeError("native comparison still erases AST operand types in a list")
    if "isinstance(left_operand" in source or "isinstance(right_operand" in source:
        raise RuntimeError("native comparison still rediscovers erased AST classes")
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
    new = f'''                    if instr.arg == {_MIXED_STRING_KIND} and op is Op.COMPARE_EQ:
                        frame.stack.append(False)
                    elif instr.arg == {_MIXED_STRING_KIND} and op is Op.COMPARE_NE:
                        frame.stack.append(True)
                    elif instr.arg == {_MIXED_STRING_KIND} and op in (
                        Op.COMPARE_LT,
                        Op.COMPARE_LE,
                        Op.COMPARE_GT,
                        Op.COMPARE_GE,
                    ):
                        _raise_typed(
                            "TypeError: ordering comparison between string and non-string"
                        )
                    elif instr.arg == 4 and op in (
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
    if f"instr.arg == {_MIXED_STRING_KIND}" not in source:
        raise RuntimeError("native mixed string comparison VM dispatch is missing")
    if "ordering comparison between string and non-string" not in source:
        raise RuntimeError("native mixed string ordering error is missing")
    return 1


def main() -> int:
    normalize_truthiness()
    metadata_count = _normalize_native_ast_metadata()
    frontend_count = _normalize_frontend()
    vm_count = _normalize_vm()
    print(
        "NORMALIZED NATIVE STRING COMPARISONS",
        metadata_count,
        frontend_count,
        vm_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
