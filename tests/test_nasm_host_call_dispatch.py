from __future__ import annotations

from pathlib import Path

from tools.nasm_host_call_dispatch import patch_host_call_dispatch
from tools.native_surface import ENVIRONMENT_GLUE_INTERNALS, HOST_CALL_GLUE_INTERNALS


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
"""


def test_linux_dispatch_and_generated_helper_adapters_preserve_sysv_state() -> None:
    rewritten = patch_host_call_dispatch(_MINIMAL_ASSEMBLY, target="linux")

    assert "call _portapy_host_dispatch_callback wrt ..plt" in rewritten
    adapters = HOST_CALL_GLUE_INTERNALS + ENVIRONMENT_GLUE_INTERNALS
    for adapter in adapters:
        assert f"{adapter}:" in rewritten
    assert rewritten.count("    push rbx") == len(adapters)
    assert rewritten.count("    push r12") == len(adapters)
    assert rewritten.count("    pop r15") == len(adapters)
    assert "call _portapy_host_pending_arg_impl" in rewritten
    assert "call _portapy_global_name_byte_impl" in rewritten


def test_windows_adapters_preserve_gprs_xmm_and_shadow_space() -> None:
    rewritten = patch_host_call_dispatch(_MINIMAL_ASSEMBLY, target="windows")

    assert "call _portapy_host_dispatch_callback" in rewritten
    adapters = HOST_CALL_GLUE_INTERNALS + ENVIRONMENT_GLUE_INTERNALS
    for adapter in adapters:
        assert f"{adapter}:" in rewritten
    assert rewritten.count("    push rdi") == len(adapters)
    assert rewritten.count("    push rsi") == len(adapters)
    assert rewritten.count("    sub rsp, 200") == len(adapters)
    assert rewritten.count("    movdqu [rsp + 32], xmm6") == len(adapters)
    assert rewritten.count("    movdqu [rsp + 176], xmm15") == len(adapters)
    assert rewritten.count("    movdqu xmm15, [rsp + 176]") == len(adapters)


def test_c_bridge_sources_use_adapter_symbols() -> None:
    root = Path(__file__).resolve().parents[1]
    host_call = (root / "native" / "host_call_glue.c").read_text(encoding="utf-8")
    environment = (root / "native" / "environment_glue.c").read_text(encoding="utf-8")

    assert "_portapy_cabi_host_pending_arg_impl" in host_call
    assert "_portapy_host_pending_arg_impl(runtime" not in host_call
    assert "_portapy_cabi_global_name_byte_impl" in environment
    assert "_portapy_global_name_byte_impl(" not in environment
