from __future__ import annotations

from pathlib import Path

from tools.native_surface import PUBLIC_EXPORTS, linux_version_script, windows_definition


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_public_exports_are_unique_and_declared_in_header() -> None:
    assert len(PUBLIC_EXPORTS) == len(set(PUBLIC_EXPORTS))
    header = (REPOSITORY_ROOT / "include" / "portapy.h").read_text(encoding="utf-8")
    for symbol in PUBLIC_EXPORTS:
        assert symbol in header


def test_linux_version_script_hides_everything_else() -> None:
    script = linux_version_script()
    for symbol in PUBLIC_EXPORTS:
        assert f"    {symbol};" in script
    assert "  local: *;" in script


def test_windows_definition_exports_exact_surface() -> None:
    definition = windows_definition()
    lines = [line.strip() for line in definition.splitlines()]
    assert lines[:2] == ["LIBRARY portapy", "EXPORTS"]
    assert tuple(lines[2:]) == PUBLIC_EXPORTS
