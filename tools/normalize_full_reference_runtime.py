"""Remove host-only traceback formatting from the native reference runtime."""
from __future__ import annotations

from pathlib import Path


PATH = Path("src/portapy/reference_api.py")

_TRACEBACK_IMPORT = "import traceback\n"
_TRACEBACK_FORMAT = '            "".join(traceback.format_exception(error)),\n'
_NATIVE_FORMAT = (
    '            type(error).__name__ + ": " + str(error),\n'
)


def main() -> int:
    source = PATH.read_text(encoding="utf-8")
    import_count = source.count(_TRACEBACK_IMPORT)
    format_count = source.count(_TRACEBACK_FORMAT)
    if import_count != 1 or format_count != 1:
        raise RuntimeError(
            "native reference traceback normalization expected one import and "
            f"one formatter; imports={import_count}, formatters={format_count}"
        )
    source = source.replace(_TRACEBACK_IMPORT, "", 1)
    source = source.replace(_TRACEBACK_FORMAT, _NATIVE_FORMAT, 1)
    PATH.write_text(source, encoding="utf-8")
    print("NORMALIZED NATIVE REFERENCE ERROR CAPTURE", format_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
