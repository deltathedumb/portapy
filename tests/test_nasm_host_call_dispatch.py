from __future__ import annotations

from pathlib import Path

from tools.nasm_host_call_dispatch import patch_host_call_dispatch
from tools.native_surface import (
    DICT_GLUE_INTERNALS,
    ENVIRONMENT_GLUE_INTERNALS,
    HOST_CALL_GLUE_INTERNALS,
    LIST_GLUE_INTERNALS,
    TUPLE_GLUE_INTERNALS,
)


_MINIMAL_ASSEMBLY = """section .text
_portapy_host_dispatch_impl:
    push rbp
    mov rbp, rsp
    xor eax, eax
    mov rsp, rbp
    pop rbp
    ret
_after_dispatch:
    ret
portapy_value_release:
    call _portapy_value_release_impl
    ret
_after_release:
    ret
"""


def _adapters() -> tuple[str, ...]:
    return (
        HOST_CALL_GLUE_INTERNALS
        + ENVIRONMENT_GLUE_INTERNALS
        + TUPLE_GLUE_INTERNALS
        + DICT_GLUE_INTERNALS
        + LIST_GLUE_INTERNALS
    )


def test_linux_dispatch_and_generated_helper_adapters_preserve_sysv_state() -> None:
    rewritten = patch_host_call_dispatch(_MINIMAL_ASSEMBLY, target="linux")

    assert "call _portapy_host_dispatch_callback wrt ..plt" in rewritten
    adapters = _adapters()
    for adapter in adapters:
        assert f"{adapter}:" in rewritten
    assert rewritten.count("    push rbx") == len(adapters)
    assert rewritten.count("    push r12") == len(adapters)
    assert rewritten.count("    pop r15") == len(adapters)
    assert "call _portapy_host_pending_arg_impl" in rewritten
    assert "call _portapy_global_name_byte_impl" in rewritten
    assert "call _portapy_tuple_get_item_impl" in rewritten
    assert "call _portapy_dict_get_item_span_impl" in rewritten
    assert "call _portapy_list_append_impl" in rewritten
    assert "call _portapy_cabi_tuple_release_impl" in rewritten
    assert "call _portapy_value_release_impl" not in rewritten


def test_windows_adapters_preserve_state_and_forward_fifth_argument() -> None:
    rewritten = patch_host_call_dispatch(_MINIMAL_ASSEMBLY, target="windows")

    assert "call _portapy_host_dispatch_callback" in rewritten
    adapters = _adapters()
    for adapter in adapters:
        assert f"{adapter}:" in rewritten
    assert rewritten.count("    push rdi") == len(adapters)
    assert rewritten.count("    push rsi") == len(adapters)
    assert rewritten.count("    sub rsp, 200") == len(adapters) - 1
    assert rewritten.count("    sub rsp, 216") == 1
    assert rewritten.count("    movdqu [rsp + 32], xmm6") == len(adapters) - 1
    assert rewritten.count("    movdqu [rsp + 176], xmm15") == len(adapters) - 1
    assert "    movdqu [rsp + 40], xmm6" in rewritten
    assert "    movdqu [rsp + 184], xmm15" in rewritten
    assert "    mov r10, [rsp + 40]" in rewritten
    assert "    mov [rsp + 32], r10" in rewritten
    assert "call _portapy_cabi_tuple_release_impl" in rewritten


def test_c_bridge_sources_use_adapter_symbols() -> None:
    root = Path(__file__).resolve().parents[1]
    host_call = (root / "native" / "host_call_glue.c").read_text(encoding="utf-8")
    environment = (root / "native" / "environment_glue.c").read_text(encoding="utf-8")
    tuples = (root / "native" / "tuple_glue.c").read_text(encoding="utf-8")
    dictionaries = (root / "native" / "dict_glue.c").read_text(encoding="utf-8")
    lists = (root / "native" / "list_glue.c").read_text(encoding="utf-8")

    assert "_portapy_cabi_host_pending_arg_impl" in host_call
    assert "_portapy_host_pending_arg_impl(runtime" not in host_call
    assert "_portapy_cabi_global_name_byte_impl" in environment
    assert "_portapy_global_name_byte_impl(" not in environment
    assert "_portapy_cabi_tuple_begin_impl" in tuples
    assert "_portapy_tuple_begin_impl(" not in tuples
    assert "_portapy_cabi_tuple_release_impl" in tuples
    assert "_portapy_cabi_dict_begin_impl" in dictionaries
    assert "_portapy_dict_begin_impl(" not in dictionaries
    assert "_portapy_cabi_dict_set_span_impl" in dictionaries
    assert "_portapy_cabi_list_begin_impl" in lists
    assert "_portapy_list_begin_impl(" not in lists
    assert "_portapy_cabi_list_append_impl" in lists
