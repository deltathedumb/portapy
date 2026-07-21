from __future__ import annotations

from portapy.native_internal_globals import _is_public_global


def test_runtime_internal_globals_are_hidden() -> None:
    assert not _is_public_global("__pyinbin_import__")
    assert not _is_public_global("__pyinbin_future_state")
    assert not _is_public_global("__portapy_internal_cache")


def test_normal_dunder_and_user_globals_remain_public() -> None:
    assert _is_public_global("__name__")
    assert _is_public_global("answer")
    assert _is_public_global("_private_user_value")
