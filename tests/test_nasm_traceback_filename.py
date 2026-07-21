from __future__ import annotations

from tools.nasm_eval_abi import append_eval_abi
from tools.nasm_state_abi import append_state_abi


STATE_SOURCE = """
section .text
_portapy_last_status_impl:
    ret
_portapy_exec_span_impl:
    ret
_portapy_get_global_span_impl:
    ret
"""

EVAL_SOURCE = """
section .text
_portapy_last_status_impl:
    ret
_portapy_eval_span_impl:
    ret
"""


def test_linux_exec_wrapper_passes_filename_to_traceback_bridge() -> None:
    assembly = append_state_abi(STATE_SOURCE, target="linux")

    assert assembly.count("extern _portapy_traceback_set_filename_utf8_bridge") == 1
    assert "mov [rsp + 24], rcx" in assembly
    assert "mov [rsp + 32], r8" in assembly
    assert "call _portapy_traceback_set_filename_utf8_bridge" in assembly
    assert "jnz .exec_bridge_failed" in assembly


def test_windows_exec_wrapper_preserves_stack_filename_size() -> None:
    assembly = append_state_abi(STATE_SOURCE, target="windows")

    assert "mov r11, [rsp + 40]" in assembly
    assert "mov [rsp + 56], r9" in assembly
    assert "mov [rsp + 64], r11" in assembly
    assert "call _portapy_traceback_set_filename_utf8_bridge" in assembly


def test_linux_eval_wrapper_passes_filename_and_preserves_output() -> None:
    assembly = append_eval_abi(EVAL_SOURCE, target="linux")

    assert assembly.count("extern _portapy_traceback_set_filename_utf8_bridge") == 1
    assert "mov [rsp + 24], rcx" in assembly
    assert "mov [rsp + 32], r8" in assembly
    assert "mov [rsp + 40], r9" in assembly
    assert "call _portapy_traceback_set_filename_utf8_bridge" in assembly
    assert "jnz .eval_bridge_failed" in assembly


def test_windows_eval_wrapper_preserves_both_stack_arguments() -> None:
    assembly = append_eval_abi(EVAL_SOURCE, target="windows")

    assert "mov r10, [rsp + 48]" in assembly
    assert "mov r11, [rsp + 40]" in assembly
    assert "mov [rsp + 64], r11" in assembly
    assert "mov [rsp + 72], r10" in assembly
    assert "call _portapy_traceback_set_filename_utf8_bridge" in assembly


def test_bridge_declaration_is_not_duplicated() -> None:
    source = "extern _portapy_traceback_set_filename_utf8_bridge\n" + EVAL_SOURCE
    assembly = append_eval_abi(source, target="linux")

    assert assembly.count("extern _portapy_traceback_set_filename_utf8_bridge") == 1
