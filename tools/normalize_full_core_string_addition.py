"""Give native VM string addition Python content semantics."""
from __future__ import annotations

import ast
from pathlib import Path
import re


FRONTEND_PATH = Path("src/portapy/core/frontend.py")
NATIVE_AST_PATH = Path("src/portapy/core/native_ast.py")
VM_PATH = Path("src/portapy/core/vm.py")

_STRING_KIND = 4
_MIXED_STRING_KIND = 8

_CONCAT_HELPER = '''def _full_core_probe_concat_strings(left: str, right: str) -> str:
    return f"{left}{right}"


'''


def _replace(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"native string addition {label}: expected 1 match, found {count}"
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

    count = 0
    for node in ast.walk(converter):
        if not isinstance(node, ast.If) or not _is_source_node_test(node, "BinOp"):
            continue
        node.body = ast.parse(
            "left: expr = _convert_expr(node.left, lifted)\n"
            "right: expr = _convert_expr(node.right, lifted)\n"
            "converted: expr = BinOp(left, _BIN_OPS[node.op], right)\n"
            "if node.op == '+':\n"
            "    left_kind: int = getattr(left, '_native_kind', 0)\n"
            "    right_kind: int = getattr(right, '_native_kind', 0)\n"
            "    if left_kind == 4 and right_kind == 4:\n"
            "        converted._native_kind = 4\n"
            "return converted\n"
        ).body
        count += 1

    if count != 1:
        raise RuntimeError(
            f"native AST string addition expected one BinOp conversion, found {count}"
        )
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + "\n"
    NATIVE_AST_PATH.write_text(source, encoding="utf-8")
    required = (
        "node.op == '+'",
        "converted._native_kind = 4",
        "left: expr = _convert_expr(node.left, lifted)",
        "right: expr = _convert_expr(node.right, lifted)",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(
            f"native AST string addition metadata validation failed: {missing}"
        )
    return count


def _normalize_frontend() -> int:
    source = FRONTEND_PATH.read_text(encoding="utf-8")
    old = '''        elif isinstance(node, ast.BinOp) and _binary_opcode(node.op) is not None:
            self.expr(node.left)
            self.expr(node.right)
            self.emit(_binary_opcode(node.op))
'''
    new = f'''        elif isinstance(node, ast.BinOp) and _binary_opcode(node.op) is not None:
            binary_opcode: int = _binary_opcode(node.op)
            left_operand: ast.expr = getattr(node, "left")
            right_operand: ast.expr = getattr(node, "right")
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
            binary_kind = _TRUTH_UNKNOWN
            if binary_opcode == Op.BINARY_ADD:
                if left_kind == _TRUTH_STRING and right_kind == _TRUTH_STRING:
                    binary_kind = _TRUTH_STRING
                elif (
                    left_kind == _TRUTH_STRING and right_kind != _TRUTH_UNKNOWN
                ) or (
                    right_kind == _TRUTH_STRING and left_kind != _TRUTH_UNKNOWN
                ):
                    binary_kind = {_MIXED_STRING_KIND}
            self.emit(binary_opcode, binary_kind)
'''
    source = _replace(source, old, new, "frontend lowering")
    FRONTEND_PATH.write_text(source, encoding="utf-8")
    required = (
        "self.emit(binary_opcode, binary_kind)",
        "binary_opcode == Op.BINARY_ADD",
        "binary_kind = _TRUTH_STRING",
        f"binary_kind = {_MIXED_STRING_KIND}",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(
            f"native frontend string addition validation failed: {missing}"
        )
    return 1


def _normalize_vm_dispatch(source: str) -> str:
    inline = re.compile(
        r"^(?P<indent>[ \t]+)if op is Op\.BINARY_ADD: "
        r"frame\.stack\.append\(left \+ right\)\n",
        re.MULTILINE,
    )
    expanded = re.compile(
        r"^(?P<indent>[ \t]+)if op is Op\.BINARY_ADD:\n"
        r"(?P<child>[ \t]+)frame\.stack\.append\(left \+ right\)\n",
        re.MULTILINE,
    )
    inline_matches = list(inline.finditer(source))
    expanded_matches = list(expanded.finditer(source))
    if len(inline_matches) + len(expanded_matches) != 1:
        raise RuntimeError(
            "native string addition VM dispatch: expected one source shape, "
            f"found [{len(inline_matches)}, {len(expanded_matches)}]"
        )

    if inline_matches:
        match = inline_matches[0]
        indent = match.group("indent")
        child = indent + "    "
    else:
        match = expanded_matches[0]
        indent = match.group("indent")
        child = match.group("child")
        if len(child) <= len(indent):
            raise RuntimeError("native string addition VM dispatch has invalid indentation")

    replacement = (
        f"{indent}if op is Op.BINARY_ADD:\n"
        f"{child}if instr.arg == {_STRING_KIND}:\n"
        f"{child}    frame.stack.append(\n"
        f"{child}        _full_core_probe_concat_strings(left, right)\n"
        f"{child}    )\n"
        f"{child}elif instr.arg == {_MIXED_STRING_KIND}:\n"
        f"{child}    _raise_typed(\n"
        f'{child}        "TypeError: can only concatenate string to string"\n'
        f"{child}    )\n"
        f"{child}else:\n"
        f"{child}    frame.stack.append(left + right)\n"
    )
    return source[: match.start()] + replacement + source[match.end() :]


def _normalize_vm() -> int:
    source = VM_PATH.read_text(encoding="utf-8")
    class_anchor = "class VirtualMachine:"
    source = _replace(
        source,
        class_anchor,
        _CONCAT_HELPER + class_anchor,
        "helper insertion",
    )
    source = _normalize_vm_dispatch(source)
    VM_PATH.write_text(source, encoding="utf-8")
    required = (
        "def _full_core_probe_concat_strings",
        f"instr.arg == {_STRING_KIND}",
        f"instr.arg == {_MIXED_STRING_KIND}",
        "can only concatenate string to string",
    )
    missing = [marker for marker in required if marker not in source]
    if missing:
        raise RuntimeError(
            f"native VM string addition validation failed: {missing}"
        )
    if source.count("_full_core_probe_concat_strings") != 2:
        raise RuntimeError("native string concatenation helper validation failed")
    return 1


def main() -> int:
    metadata_count = _normalize_native_ast_metadata()
    frontend_count = _normalize_frontend()
    vm_count = _normalize_vm()
    print(
        "NORMALIZED NATIVE STRING ADDITION",
        metadata_count,
        frontend_count,
        vm_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
