"""Repair the pinned compiler's ExprStmt initializer parameter load.

The source-level explicit initializer is compiled consistently on Linux and Windows,
but asmpython replaces the dict-typed ``expr`` parameter with its static type token
(126 / 0x7e). The real parameter is already spilled at ``[rbp-16]`` on both ABIs,
so replace only the one bad load inside the uniquely named initializer block.
"""
from __future__ import annotations


_FUNCTION = "_npr_ast_nodes_ExprStmt____init__"
_BAD_LOAD = "    mov rax, 126"
_GOOD_LOAD = "    mov rax, [rbp-16]"


def fix_expr_stmt_initializer_assembly(
    source: str,
    *,
    target: str,
) -> tuple[str, int]:
    if target not in {"linux", "windows"}:
        raise ValueError(f"unsupported ExprStmt assembly target: {target}")

    start_marker = f"{_FUNCTION}:\n"
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError("native ExprStmt initializer assembly label is missing")
    next_function = source.find("\n_npr_ast_nodes_Pass____init__:\n", start)
    if next_function < 0:
        raise RuntimeError("native ExprStmt initializer assembly boundary is missing")

    block = source[start:next_function]
    expected_spills = (
        ("    mov [rbp-8], rdi", "    mov [rbp-16], rsi", "    mov [rbp-24], rdx")
        if target == "linux"
        else ("    mov [rbp-8], rcx", "    mov [rbp-16], rdx", "    mov [rbp-24], r8")
    )
    missing = [spill for spill in expected_spills if spill not in block]
    if missing:
        raise RuntimeError(
            f"native ExprStmt initializer parameter spills changed: {missing}"
        )

    count = block.count(_BAD_LOAD)
    if count != 1:
        raise RuntimeError(
            "native ExprStmt initializer expected one static dict-token load, "
            f"found {count}"
        )
    fixed_block = block.replace(_BAD_LOAD, _GOOD_LOAD, 1)
    if _BAD_LOAD in fixed_block or fixed_block.count(_GOOD_LOAD) < 1:
        raise RuntimeError("native ExprStmt initializer assembly repair failed")

    return source[:start] + fixed_block + source[next_function:], count
