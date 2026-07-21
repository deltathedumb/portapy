from __future__ import annotations

import pytest

from tools.nasm_direct_float_abi import append_direct_float_abi


_SOURCE = '''
_portapy_last_status_impl:
    ret
_portapy_value_from_f64_bits_impl:
    ret
_portapy_value_as_f64_bits_impl:
    ret
'''


def test_linux_float_wrappers_move_ieee_bits_through_gprs() -> None:
    result = append_direct_float_abi(_SOURCE, target="linux")
    assert "movq rsi, xmm0" in result
    assert "call _portapy_value_from_f64_bits_impl" in result
    assert "call _portapy_value_as_f64_bits_impl" in result
    assert "movsd" not in result
    assert "mov rcx, [rsp + 8]" in result
    assert "mov [rdx], rcx" in result
    assert "mov [rdx], rax" not in result


def test_windows_float_wrappers_move_ieee_bits_through_gprs() -> None:
    result = append_direct_float_abi(_SOURCE, target="windows")
    assert "movq rdx, xmm1" in result
    assert "call _portapy_value_from_f64_bits_impl" in result
    assert "call _portapy_value_as_f64_bits_impl" in result
    assert "movsd" not in result
    assert "mov [r8], r9" in result


def test_rejects_old_float_implementation_labels() -> None:
    with pytest.raises(ValueError, match="f64_bits"):
        append_direct_float_abi(
            "_portapy_last_status_impl:\n_portapy_value_from_f64_impl:\n"
            "_portapy_value_as_f64_impl:\n",
            target="linux",
        )
