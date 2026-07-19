from __future__ import annotations

import pytest

from tools.nasm_exports import declare_exports


def test_requested_labels_become_global_once() -> None:
    source = """\
BITS 64
default rel
global main
section .text
main:
    ret
portapy_abi_version:
    mov rax, 1
    ret
portapy_opcode_probe:
    mov rax, 10
    ret
"""
    rewritten = declare_exports(
        source,
        ["portapy_abi_version", "portapy_opcode_probe", "portapy_abi_version"],
    )
    assert rewritten.count("global portapy_abi_version") == 1
    assert rewritten.count("global portapy_opcode_probe") == 1
    assert rewritten.count("global main") == 1


def test_missing_requested_label_fails_closed() -> None:
    with pytest.raises(ValueError, match="not found"):
        declare_exports("BITS 64\nmain:\n    ret\n", ["portapy_missing"])
