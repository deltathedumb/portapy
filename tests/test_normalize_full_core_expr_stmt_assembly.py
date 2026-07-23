from __future__ import annotations

from tools.normalize_full_core_expr_stmt_assembly import (
    fix_expr_stmt_initializer_assembly,
)


LINUX = '''_npr_ast_nodes_ExprStmt____init__:
    push rbp
    mov rbp, rsp
    mov [rbp-8], rdi
    mov [rbp-16], rsi
    mov [rbp-24], rdx
    mov rax, 126
    push rax
    ret
_npr_ast_nodes_Pass____init__:
    ret
'''

WINDOWS = '''_npr_ast_nodes_ExprStmt____init__:
    push rbp
    mov rbp, rsp
    mov [rbp-8], rcx
    mov [rbp-16], rdx
    mov [rbp-24], r8
    mov rax, 126
    push rax
    ret
_npr_ast_nodes_Pass____init__:
    ret
'''


def test_repairs_linux_parameter_load() -> None:
    source, count = fix_expr_stmt_initializer_assembly(LINUX, target="linux")
    assert count == 1
    assert "mov rax, 126" not in source
    assert "mov rax, [rbp-16]" in source


def test_repairs_windows_parameter_load() -> None:
    source, count = fix_expr_stmt_initializer_assembly(WINDOWS, target="windows")
    assert count == 1
    assert "mov rax, 126" not in source
    assert "mov rax, [rbp-16]" in source


def test_accepts_already_correct_parameter_load() -> None:
    correct = LINUX.replace("mov rax, 126", "mov rax, [rbp-16]")
    source, count = fix_expr_stmt_initializer_assembly(correct, target="linux")

    assert count == 0
    assert source == correct


def test_fails_closed_when_bad_load_changes() -> None:
    try:
        fix_expr_stmt_initializer_assembly(
            LINUX.replace("mov rax, 126", "mov rax, 125"),
            target="linux",
        )
    except RuntimeError as error:
        assert "neither the static dict-token load" in str(error)
    else:
        raise AssertionError("assembly transform accepted a changed bad load")


def test_fails_closed_when_parameter_spill_changes() -> None:
    try:
        fix_expr_stmt_initializer_assembly(
            WINDOWS.replace("mov [rbp-16], rdx", "mov [rbp-32], rdx"),
            target="windows",
        )
    except RuntimeError as error:
        assert "parameter spills changed" in str(error)
    else:
        raise AssertionError("assembly transform accepted changed parameter spills")
