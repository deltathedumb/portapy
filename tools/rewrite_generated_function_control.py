"""Splice shared function-control semantics into a generated function module."""
from __future__ import annotations

from pathlib import Path

from tools.rewrite_generated_parser import _replace_function


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTROL_OVERLAY = (
    REPOSITORY_ROOT / "src" / "portapy" / "native_api_function_control.py"
)
_START = "# BEGIN SHARED FUNCTION CONTROL"
_END = "# END SHARED FUNCTION CONTROL"


def _shared_source() -> str:
    source = CONTROL_OVERLAY.read_text(encoding="utf-8")
    start = source.find(_START)
    end = source.find(_END)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("function-control overlay has invalid shared markers")
    shared = source[start + len(_START):end].strip()
    shared = shared.replace("_functions.", "")
    shared = shared.replace("_truthy(", "_expr_truthy(")
    if "_functions." in shared:
        raise ValueError("generated function-control source retains module access")
    return shared


def rewrite_generated_function_control(path: Path) -> Path:
    source = path.read_text(encoding="utf-8")
    if "_expr_truthy" not in source:
        raise ValueError("generated function entry is missing namespaced truthiness")
    source = _replace_function(
        source,
        "_execute_function_body",
        _shared_source(),
    )
    path.write_text(source, encoding="utf-8")
    return path


__all__ = ["rewrite_generated_function_control"]
