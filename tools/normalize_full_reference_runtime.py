"""Normalize host-only features in the native reference runtime."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/reference_api.py")

_TRACEBACK_IMPORT = "import traceback\n"
_TRACEBACK_FORMAT = '            "".join(traceback.format_exception(error)),\n'
_NATIVE_FORMAT = (
    '            type(error).__name__ + ": " + str(error),\n'
)
_VALUES_ANNOTATION = "self._values: dict[int, _Slot] = {}"
_NATIVE_VALUES_ANNOTATION = "self._values: dict[str, _Slot] = {}"
_HANDLE_SUBSCRIPT = "self._values[handle]"
_NATIVE_HANDLE_SUBSCRIPT = "self._values[str(handle)]"
_HANDLE_GET = "self._values.get(handle)"
_NATIVE_HANDLE_GET = "self._values.get(str(handle))"
_CALLABLE_HANDLE_GET = "self._values.get(callable_handle)"
_NATIVE_CALLABLE_HANDLE_GET = "self._values.get(str(callable_handle))"


def _replace_exact(
    source: str,
    old: str,
    new: str,
    *,
    label: str,
    expected: int,
) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(
            f"native reference {label} normalization expected {expected} matches, "
            f"found {count}"
        )
    return source.replace(old, new)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    source = _replace_exact(
        source,
        _TRACEBACK_IMPORT,
        "",
        label="traceback import",
        expected=1,
    )
    source = _replace_exact(
        source,
        _TRACEBACK_FORMAT,
        _NATIVE_FORMAT,
        label="traceback formatter",
        expected=1,
    )
    source = _replace_exact(
        source,
        _VALUES_ANNOTATION,
        _NATIVE_VALUES_ANNOTATION,
        label="value-table annotation",
        expected=1,
    )
    source = _replace_exact(
        source,
        _HANDLE_SUBSCRIPT,
        _NATIVE_HANDLE_SUBSCRIPT,
        label="value-table subscript",
        expected=2,
    )
    source = _replace_exact(
        source,
        _HANDLE_GET,
        _NATIVE_HANDLE_GET,
        label="value-table lookup",
        expected=8,
    )
    source = _replace_exact(
        source,
        _CALLABLE_HANDLE_GET,
        _NATIVE_CALLABLE_HANDLE_GET,
        label="callable value-table lookup",
        expected=1,
    )
    PATH.write_text(source, encoding="utf-8")
    print("NORMALIZED NATIVE REFERENCE ERROR CAPTURE", 1)
    print("NORMALIZED NATIVE VALUE HANDLE KEYS", 11)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
