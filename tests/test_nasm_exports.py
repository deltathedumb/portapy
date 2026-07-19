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


def test_alias_points_at_existing_initializer_label() -> None:
    source = """\
BITS 64
default rel
global main
section .text
main:
    mov rax, 0
    ret
"""
    rewritten = declare_exports(
        source,
        [],
        {"portapy_initialize": "main"},
    )
    assert rewritten.count("global portapy_initialize") == 1
    assert "portapy_initialize:\nmain:\n" in rewritten


def test_missing_requested_label_fails_closed() -> None:
    with pytest.raises(ValueError, match="not found"):
        declare_exports("BITS 64\nmain:\n    ret\n", ["portapy_missing"])


def test_missing_alias_target_fails_closed() -> None:
    with pytest.raises(ValueError, match="alias target not found"):
        declare_exports(
            "BITS 64\nmain:\n    ret\n",
            [],
            {"portapy_initialize": "missing"},
        )
