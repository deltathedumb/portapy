"""Materialize the generated full Runtime ABI entry from its verified payload."""
from __future__ import annotations

import base64
import gzip
import hashlib
from pathlib import Path


PAYLOAD = Path("tools/full_reference_payload/entry.py.gz.b64")
OUTPUT = Path("src/portapy/native_full_reference_entry.py")
EXPECTED_SHA256 = "907b729049b38ce3bbe6ca241a7b5530a705c046330e0a36aa0cae89ad6bc528"


def main() -> int:
    encoded = PAYLOAD.read_text(encoding="ascii").strip()
    source = gzip.decompress(base64.b64decode(encoded))
    digest = hashlib.sha256(source).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(
            f"full Runtime ABI payload digest mismatch: {digest}"
        )
    OUTPUT.write_bytes(source)
    print("MATERIALIZED FULL RUNTIME ABI", len(source), digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
