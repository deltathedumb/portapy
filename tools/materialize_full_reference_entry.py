"""Materialize the generated full Runtime ABI entry from its verified payload."""
from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path


PAYLOAD = Path("tools/full_reference_payload/entry.py.gz.b64")
OUTPUT = Path("src/portapy/native_full_reference_entry.py")
EXPECTED_SHA256 = "907b729049b38ce3bbe6ca241a7b5530a705c046330e0a36aa0cae89ad6bc528"
_LEGACY_VALUE_LOOKUP = "slot = instance._values.get(handle)"
_NATIVE_VALUE_LOOKUP = "slot = instance._value_slot(handle)"


def main() -> int:
    encoded = PAYLOAD.read_text(encoding="ascii").strip()
    payload = gzip.decompress(base64.b64decode(encoded))
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            f"full Runtime ABI payload digest mismatch: {digest}"
        )
    source = payload.decode("utf-8")
    lookup_count = source.count(_LEGACY_VALUE_LOOKUP)
    if lookup_count != 1:
        raise RuntimeError(
            "full Runtime ABI payload value lookup expected 1 match, "
            f"found {lookup_count}"
        )
    source = source.replace(_LEGACY_VALUE_LOOKUP, _NATIVE_VALUE_LOOKUP, 1)
    OUTPUT.write_text(source, encoding="utf-8")
    print(
        "MATERIALIZED FULL RUNTIME ABI",
        len(payload),
        digest,
        "NATIVE VALUE LOOKUPS",
        lookup_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
